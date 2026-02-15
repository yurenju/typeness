# 實作計畫

## 參考文件

**PRD 文件路徑：** 無
**研究文件路徑：** `docs/research/2026-02-15-regression-testing-workflow.md`

## 任務概要

- [x] 建立測試案例格式與 fixtures 目錄
- [x] 實作重播引擎 replay.py
- [x] 建立 CLI 入口與報告輸出
- [x] 撰寫 /fix-transcription skill
- [x] 撰寫 /run-regression skill
- [x] 從現有 debug 案例建立初始測試集
- [ ] 執行驗收測試
- [ ] 更新專案文件

## 任務細節

### 建立測試案例格式與 fixtures 目錄

**實作要點**
- 建立 `tests/fixtures/` 目錄
- 建立 `tests/fixtures/cases.json`，初始為空的案例清冊結構：
  ```json
  {
    "cases": []
  }
  ```
- 每個案例的欄位定義如下：
  - `id`：時間戳 ID（如 `20260215_105248`），與音頻檔名前綴一致
  - `audio_file`：音頻檔名（如 `20260215_105248_audio.wav`）
  - `description`：人工描述這段語音的內容摘要
  - `whisper_expected`：Whisper 預期輸出文字（可選，設為 `null` 表示不檢查）
  - `processed_expected`：LLM 後處理預期輸出文字（必填）
  - `tags`：標籤陣列，用於分類和篩選（如 `["short", "technical", "mixed-lang"]`）
  - `notes`：人工備註，當裁判時提供額外判斷準則（可選，設為 `null`）
- 音頻 WAV 檔案直接放在 `tests/fixtures/` 目錄下，與 `cases.json` 同層
- 在 `.gitignore` 中確認 `tests/fixtures/*.wav` **不被排除**（這些是需要版控的測試資產）

**相關檔案**
- `tests/fixtures/cases.json` — 新建，案例清冊
- `.gitignore` — 檢查並確保 wav 不被排除

**完成檢查**
- `tests/fixtures/cases.json` 存在且結構為合法 JSON
- 目錄結構 `tests/fixtures/` 已建立

**實作備註**
照預期開發

---

### 實作重播引擎 replay.py

**實作要點**
- 建立 `src/typeness/replay.py` 模組
- 重用現有的 `load_whisper()` / `transcribe()` 和 `load_llm()` / `process_text()` 函式，不重複實作推論邏輯
- 實作以下核心函式：

  **`load_cases(case_id=None, tag=None)`**：
  - 讀取 `tests/fixtures/cases.json`
  - 支援依 `case_id` 篩選單一案例
  - 支援依 `tag` 篩選包含該標籤的案例
  - 回傳案例列表

  **`replay_whisper(asr_pipeline, processor, audio_path)`**：
  - 用 `wave` 模組讀取 WAV 檔案，轉換回 float32 numpy array（與 `debug.py` 中的 int16→float32 相反）
  - 呼叫 `transcribe()` 函式取得文字
  - 回傳轉錄文字和延遲時間

  **`replay_llm(llm_model, tokenizer, whisper_text)`**：
  - 呼叫 `process_text()` 函式處理文字
  - 回傳處理後文字和延遲時間

  **`replay_full(asr_pipeline, processor, llm_model, tokenizer, audio_path)`**：
  - 串接 Whisper → LLM 完整管線
  - 回傳 dict，包含 `whisper_text`, `processed_text`, `whisper_latency`, `llm_latency`

  **`run_all_cases(stage, ...models, case_id=None, tag=None)`**：
  - `stage` 參數：`"whisper"` / `"llm"` / `"full"`
  - 根據 stage 決定載入哪些模型（避免不必要的 VRAM 佔用）
  - 遍歷所有案例，逐一執行重播
  - 對每個案例比對預期結果，紀錄 `"exact"`（完全一致）或 `"different"`（有差異）
  - 計算 `char_diff_ratio`：diff 字元數 / max(len(expected), len(actual))，提供定量參考
  - 回傳結構化結果列表

- 讀取 WAV 時的轉換邏輯：`int16 PCM → float32`（除以 32767.0），與 `debug.py` 中 `save_capture()` 的存檔邏輯互為反操作
- 注意：`transcribe()` 和 `process_text()` 內部有 `print()` 輸出，重播時會顯示在 console，這是預期行為（便於觀察進度）

**相關檔案**
- `src/typeness/replay.py` — 新建，重播引擎核心
- `src/typeness/transcribe.py` — 引用 `load_whisper()`, `transcribe()`
- `src/typeness/postprocess.py` — 引用 `load_llm()`, `process_text()`
- `src/typeness/debug.py` — 參考 WAV 存檔格式（int16 PCM, 16kHz, mono）

**完成檢查**
- 能成功 `from typeness.replay import run_all_cases` 不報錯
- 手動建立一個簡單的測試案例（用現有 debug 音頻），執行 `replay_llm` 確認能產生結果

**實作備註**
照預期開發

---

### 建立 CLI 入口與報告輸出

**實作要點**
- 在 `src/typeness/replay.py` 底部（或獨立的 `__main__` 區塊）建立 CLI 入口，讓模組可以直接執行：`uv run python -m typeness.replay`
- 使用 `argparse` 解析以下參數：
  - `--stage`：`whisper` / `llm` / `full`（預設 `full`）
  - `--case`：指定單一案例 ID（如 `20260215_105248`）
  - `--tag`：篩選特定標籤的案例
  - `--output`：報告輸出路徑（預設 `tests/fixtures/last_run.json`）
- 報告 JSON 格式：
  ```json
  {
    "run_timestamp": "2026-02-15T15:30:00",
    "stage": "llm",
    "total": 5,
    "exact_match": 3,
    "different": 2,
    "results": [
      {
        "case_id": "20260215_105248",
        "description": "長段落語音輸入法需求說明",
        "stage_tested": "llm",
        "expected": "預期文字...",
        "actual": "實際輸出...",
        "match": "exact",
        "char_diff_ratio": 0.0
      }
    ]
  }
  ```
- 在 console 輸出簡易摘要：
  ```
  === Replay Results ===
  Total: 5 | Exact: 3 | Different: 2

  [EXACT]     20260215_084842 - 短句命令
  [EXACT]     20260215_084630 - 含英文術語
  [DIFFERENT] 20260215_105248 - 長段落 (diff: 5.2%)
  [DIFFERENT] 20260215_104007 - 技術說明 (diff: 2.1%)
  [EXACT]     20260215_103858 - 中等長度

  Report saved to: tests/fixtures/last_run.json
  ```
- `last_run.json` 每次覆寫，不保留歷史（歷史由 git 管理）

**相關檔案**
- `src/typeness/replay.py` — 擴充 CLI 入口和報告邏輯

**完成檢查**
- 執行 `uv run python -m typeness.replay --help` 能看到參數說明
- 在有至少一個 fixture 案例的情況下，執行 `uv run python -m typeness.replay --stage llm` 能產生 `last_run.json`

**實作備註**
照預期開發

---

### 撰寫 /fix-transcription skill

**實作要點**
- 建立 `.claude/skills/fix-transcription/SKILL.md`
- Skill 的觸發方式：使用者執行 `/fix-transcription <問題描述>`
- 典型使用情境：使用者在 IDE 中打開 `debug/<id>_result.json`，然後輸入 `/fix-transcription 少了一句前導語` 或 `/fix-transcription 標點不對`
- SKILL.md frontmatter：
  ```yaml
  ---
  description: Fix a voice transcription error by creating a test case from debug data, then help diagnose and fix the issue
  argument-hint: "[問題描述，例如：少了前導語 / 標點錯了 / 英文術語間距不對]"
  ---
  ```
- Skill 引導 Claude Code 執行以下步驟：

  **步驟 1：辨識案例**
  - 優先從 IDE 目前開啟的檔案（`ide_selection` 或 `ide_opened_file`）自動偵測 `debug/*_result.json`，取得 case_id
  - 若參數中包含 case_id 格式的字串（如 `20260215_084842`），以參數為準
  - 若無法自動偵測，列出 `debug/` 中所有 `*_result.json` 的時間戳和摘要（whisper_text 前 50 字），讓使用者選擇
  - 讀取該案例的 JSON，顯示 Whisper 原始輸出和 LLM 處理後輸出

  **步驟 2：確認預期輸出**
  - 根據使用者在參數中描述的問題（如「少了前導語」「標點錯了」），對照案例的實際輸出，推敲預期的正確輸出
  - 將推敲結果顯示給使用者確認，使用者可以直接同意或修正
  - 若使用者未在參數中描述問題，則詢問使用者：預期的正確輸出是什麼？

  **步驟 3：建立測試案例**
  - 將音頻 WAV 從 `debug/` 複製到 `tests/fixtures/`
  - 在 `cases.json` 中新增一筆案例
  - 預設 `whisper_expected` 設為目前的 Whisper 輸出（除非使用者指出 Whisper 也有問題）
  - `processed_expected` 設為使用者確認的預期輸出

  **步驟 4：重播驗證**
  - 執行 `uv run python -m typeness.replay --case <case_id> --stage llm`（或 `full`，取決於問題在哪一階段）
  - 確認問題可重現（實際輸出與預期不符）

  **步驟 5：分析與修正**
  - 根據問題類型，分析可能的修正方向：
    - 若是 LLM 問題：檢查 `postprocess.py` 的 `LLM_SYSTEM_PROMPT`，建議 prompt 調整
    - 若是 Whisper 問題：檢查 `transcribe.py` 的參數設定
  - 提出修改建議，等使用者確認後實施

  **步驟 6：驗證修正**
  - 重播修改後的結果，確認修正生效
  - 執行 `uv run python -m typeness.replay`（全部案例）確認沒有回歸問題
  - 顯示回歸測試摘要

**相關檔案**
- `.claude/skills/fix-transcription/SKILL.md` — 新建

**完成檢查**
- `.claude/skills/fix-transcription/SKILL.md` 存在且格式正確
- 在 Claude Code 中輸入 `/fix-transcription` 能觸發 skill

**實作備註**

已完成 SKILL.md 撰寫並實際執行過一次完整流程（案例 20260215_180535），過程中發現以下需傳遞的上下文：

1. **cases.json 已從 git 排除**：`tests/fixtures/*` 整個目錄都被 gitignore（WAV 太大），只保留 `cases.example.json` 作為 schema 參考。Skill 步驟 3 已更新：若 `cases.json` 不存在，先以 `{"cases": []}` 建立。
2. **replay.py 已加入缺檔處理**：`load_cases()` 在 `cases.json` 不存在時回傳空 list 並提示使用者，不會拋例外。
3. **新增 `processed_acceptable` 欄位**：cases.json 支援 `processed_acceptable`（可接受輸出），用於 Whisper 同音字錯誤等超出 LLM 能力的情況。重播引擎匹配 acceptable 時標記為 `"match": "acceptable"`。此欄位為選用。
4. **replay.py 已抑制 progress bar**：設定 `HF_HUB_DISABLE_PROGRESS_BARS=1` 和 `TRANSFORMERS_NO_TQDM=1`，避免模型載入時輸出過大（原本 80KB+）導致 Claude Code 截斷。
5. **首次修正案例**：LLM system prompt 新增規則 3（問句保留）和問句範例，修正了問句開頭/結尾被誤刪的問題。

---

### 撰寫 /run-regression skill

**實作要點**
- 建立 `.claude/skills/run-regression/SKILL.md`
- Skill 的觸發方式：使用者執行 `/run-regression` 或 `/run-regression --stage llm`
- SKILL.md frontmatter：
  ```yaml
  ---
  description: Run regression tests on all transcription test cases and judge results using LLM-as-Judge
  argument-hint: "[--stage whisper|llm|full]"
  ---
  ```
- Skill 引導 Claude Code 執行以下步驟：

  **步驟 1：執行重播引擎**
  - 執行 `uv run python -m typeness.replay --stage <stage>`（預設 `full`）
  - 等待執行完成

  **步驟 2：讀取報告**
  - 讀取 `tests/fixtures/last_run.json`
  - 篩選出 `match: "exact"` 的案例（自動 PASS，不需要進一步判斷）
  - 篩選出 `match: "different"` 的案例（需要 LLM-as-Judge 判斷）

  **步驟 3：LLM-as-Judge 判斷**
  - 對每個 `different` 案例，Claude Code 閱讀：
    - 預期輸出 (`expected`)
    - 實際輸出 (`actual`)
    - 案例的 `notes`（如果有的話）
    - 差異比例 (`char_diff_ratio`)
  - 根據以下準則判斷 PASS 或 FAIL：
    1. 核心語意是否保留（最重要）
    2. 沒有遺漏關鍵資訊
    3. 沒有添加原文沒有的內容
    4. 標點符號和空格的細微差異可以接受
    5. 同義詞替換可以接受
    6. 如果案例有 `notes`，按照 notes 的特殊要求判斷
  - 每個判斷附上一句話理由

  **步驟 4：產生最終報告**
  - 在 console 顯示摘要表格：
    ```
    === Regression Report ===
    Total: 5 | Auto-PASS: 3 | Judge-PASS: 1 | FAIL: 1

    [AUTO-PASS]  20260215_084842 - 短句命令
    [AUTO-PASS]  20260215_084630 - 含英文術語
    [AUTO-PASS]  20260215_103858 - 中等長度
    [PASS]       20260215_104007 - 標點微調，語意一致
    [FAIL]       20260215_105248 - 遺漏「請你幫我」這句前導語
    ```
  - 對每個 FAIL 案例，顯示預期 vs 實際的差異和失敗理由
  - 建議可能的修正方向

**相關檔案**
- `.claude/skills/run-regression/SKILL.md` — 新建

**完成檢查**
- `.claude/skills/run-regression/SKILL.md` 存在且格式正確
- 在 Claude Code 中輸入 `/run-regression` 能觸發 skill

**實作備註**
照預期開發

---

### 從現有 debug 案例建立初始測試集

**實作要點**
- 從 `debug/` 目錄中選取 3-5 個有代表性的案例建立初始測試集
- 選取原則：覆蓋不同類型（短句、中等長度含英文、口語化長句、超長段落）
- 對每個選取的案例：
  1. 複製 `debug/<id>_audio.wav` 到 `tests/fixtures/<id>_audio.wav`
  2. 讀取 `debug/<id>_result.json` 中的 `whisper_text` 和 `processed_text`
  3. 在 `cases.json` 中新增記錄，`processed_expected` 設為目前的 `processed_text`（假設目前的輸出是正確的基準）
  4. 為每個案例加上適當的 `description`、`tags` 和 `notes`
- 完成後執行 `uv run python -m typeness.replay --stage llm` 確認所有案例都 `exact` match（因為預期值就是用目前的輸出設定的）

**相關檔案**
- `debug/*_result.json` — 讀取現有結果
- `debug/*_audio.wav` — 複製音頻
- `tests/fixtures/cases.json` — 新增案例
- `tests/fixtures/*.wav` — 新增音頻

**完成檢查**
- `tests/fixtures/cases.json` 包含 3-5 個案例
- 對應的 WAV 檔案已在 `tests/fixtures/` 中
- 執行 `uv run python -m typeness.replay --stage llm` 全部顯示 `EXACT`

**實作備註**
照預期開發。選取 4 個新案例 + 1 個既有案例 = 共 5 個：短句 (084842)、問句含英文 (084630)、英文+數字 (104007)、中等長度 (103858)、技術混合語問句 (180535)。LLM replay 結果：4 EXACT + 1 ACCEPTABLE + 0 DIFFERENT。

---

### 執行驗收測試

**實作要點**
- 使用 AI 讀取 acceptance.feature 檔案
- 透過指令或 MCP 瀏覽器操作執行每個場景
- 驗證所有場景通過並記錄結果
- 如發現問題，記錄詳細的錯誤資訊和重現步驟

**相關檔案**
- `docs/specs/2026-02-15-regression-testing/acceptance.feature` — Gherkin 格式的驗收測試場景
- `docs/specs/2026-02-15-regression-testing/acceptance-report.md` — 詳細的驗收測試執行報告（執行時生成）

**實作備註**
<!-- 執行過程中填寫 -->

---

### 更新專案文件

**實作要點**
- 審查 `CLAUDE.md`，更新：
  - 新增 `replay.py` 模組說明到 Architecture 區塊
  - 新增 `tests/fixtures/` 說明
  - 新增 replay CLI 使用方式到 Running 區塊
  - 新增 skills 說明
- 審查 `README.md`，更新：
  - 新增回歸測試工作流程的使用說明
  - 新增 `/fix-transcription` 和 `/run-regression` skill 的說明

**相關檔案**
- `CLAUDE.md` — 更新架構和使用說明
- `README.md` — 更新使用者文件

**實作備註**
<!-- 執行過程中填寫 -->

---

## 實作參考資訊

### 來自研究文件的技術洞察
> **文件路徑：** `docs/research/2026-02-15-regression-testing-workflow.md`

**LLM-as-Judge 最佳實踐：**
- 二元判定（Pass/Fail）優於多級評分，搭配一句話理由最為可靠
- Judge prompt 需明確定義評判標準，避免模糊的「品質好」描述
- 常見陷阱：冗長偏差（偏好較長輸出）→ 需在 prompt 中明確「長度不是評判標準」
- Claude 判斷 Qwen3 輸出不存在自我增強偏差

**非確定性處理策略：**
- Qwen3 使用 `do_sample=False`，理論上相同輸入產生一致輸出
- Whisper 天然具有非確定性，比較標準不應是完全一致
- 容忍度分級：`exact`（完全一致）/ `semantic`（語意等價，預設）/ `lenient`（核心資訊保留即可）

**WAV 檔案格式：**
- PCM 16-bit, mono, 16kHz
- float32 → int16 轉換：`(audio * 32767).clip(-32768, 32767).astype(np.int16)`
- 反向轉換（讀取）：`int16_data.astype(np.float32) / 32767.0`

**重播引擎設計原則：**
- 重用現有 `transcribe()` 和 `process_text()` 函式，不重複推論邏輯
- 模型載入只做一次，多個案例共用
- 支援只跑 Whisper 或只跑 LLM，根據修改範圍決定

### 關鍵技術決策
- **裁判由 Claude Code 擔任**：不需要額外 API key 或本地模型，在 skill 中直接閱讀新舊輸出判斷
- **重播引擎為純 Python 腳本**：獨立於 Claude Code 運行，只負責跑模型和收集結果
- **測試案例與 debug 資料分離**：`tests/fixtures/` 是有版控的正式測試集，`debug/` 是臨時偵錯輸出
- **JSON 報告作為兩階段的銜接**：第一階段（重播）產生 `last_run.json`，第二階段（判斷）由 Claude Code 讀取該報告
