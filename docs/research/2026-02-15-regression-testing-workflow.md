# 語音辨識回歸測試與自動修正工作流程

日期：2026-02-15

## 執行摘要

本研究針對 Typeness 語音輸入法的品質保證流程進行深入分析，旨在設計一套從「發現錯誤」到「驗證修正」的完整工作流程。核心構想是利用現有的 `--debug` 錄音機制，將有問題的辨識結果轉化為可重複驗證的測試案例，並在後續程式修改時自動回歸測試所有既存案例。

關鍵發現：

- **LLM-as-Judge** 模式適合作為語意比對的裁判機制，業界實踐表明 Pass/Fail 二元判定比多級評分更穩定可靠
- 測試流程可分離 Whisper 與 LLM 兩階段，大幅加速迭代速度（多數修改集中在 LLM prompt 調整）
- 現有 9 個 debug 案例的內容涵蓋短句、技術術語、長段落等多種情境，已是良好的初始測試集

## 背景與脈絡

Typeness 是一個全域語音輸入工具，透過 Whisper large-v3-turbo 進行語音轉文字，再由 Qwen3-1.7B 做口語清理與格式化後處理。使用者按下 Shift+Win+A 開始錄音，再按一次停止，處理後的文字自動貼到游標位置。

現有的 `--debug` 旗標會在每次辨識後儲存一組檔案到 `debug/` 目錄：一個 WAV 音頻檔和一個 JSON 結果檔（包含 Whisper 原始輸出、LLM 處理後輸出、延遲時間等 metadata）。這些資料是離線重現問題的基礎。

然而目前缺乏一個系統化的流程來：
1. 將有問題的 debug 案例提升為正式測試案例
2. 在修改 Whisper 參數或 LLM prompt 後驗證修正是否生效
3. 確認修改沒有破壞其他案例的辨識品質

## 研究問題與發現過程

使用者的原始需求可以拆解為兩個核心問題：

**問題一：如何快速重現並修正辨識錯誤？** 使用者希望發現問題時，能告訴 Claude Code「這個 case 預期輸出是 X，但結果是 Y」，Claude Code 能自動建立測試案例、確認問題可重現，然後協助修改並驗證修正結果。

**問題二：如何確保修改不會破壞既有案例？** 由於 LLM 輸出具有非確定性，直接的字串比對不可行，需要一種能容忍合理差異、但能捕捉品質下降的比對機制。

經過釐清，確定了以下設計方向：
- 測試案例存放在獨立的 `tests/fixtures/` 目錄
- Whisper 和 LLM 階段可分開測試，預設只跑被修改的階段
- 使用 LLM-as-Judge 來判斷結果是否符合預期

## 技術分析

### 4.1 現有 Debug 資料分析

目前 `debug/` 目錄有 9 個案例，涵蓋多種場景：

| 類型 | 範例 | 時長 | LLM 主要處理 |
|------|------|------|-------------|
| 短句命令 | 「幫我看一下這個錯誤。」 | 4 秒 | 幾乎無變化 |
| 含英文術語 | 「用 PlayWrite CLI 檢查...」 | 9-14 秒 | CJK 空格規範化 |
| 口語化長句 | 「目前是回復 conflict...你幫我看怎麼修」 | 16 秒 | 移除尾部 filler |
| 超長段落 | 完整工作流程說明 | 118 秒 | 去重複、修文法、格式化 |

LLM 後處理的主要工作包括：CJK 與英文/數字間的空格規範化、口語贅字移除、文法修正、繁簡一致性。這些處理的「正確性」往往不是非黑即白的，而是存在灰色地帶，這正是需要 LLM-as-Judge 的原因。

### 4.2 測試案例格式設計

每個測試案例需要的資訊：

```
tests/fixtures/
├── cases.json                    # 案例清冊與 metadata
├── 20260215_105248_audio.wav     # 音頻檔案
├── 20260215_105248_audio.wav     # (更多音頻...)
└── ...
```

`cases.json` 結構設計：

```json
{
  "cases": [
    {
      "id": "20260215_105248",
      "audio_file": "20260215_105248_audio.wav",
      "description": "長段落語音輸入法需求說明",
      "whisper_expected": "原始 Whisper 預期文字（可選）",
      "processed_expected": "LLM 處理後的預期文字",
      "tags": ["long", "technical", "mixed-lang"],
      "whisper_tolerance": "semantic",
      "llm_tolerance": "semantic",
      "notes": "關鍵：不應移除「我想要請你幫我做一個研究」這句前導語"
    }
  ]
}
```

設計考量：
- `whisper_expected` 是可選的：如果只關心端對端結果，可以只設 `processed_expected`
- `tags` 用於分類和篩選，方便只跑特定類型的案例
- `notes` 是人工補充的判斷準則，會傳給 LLM Judge 作為額外context
- tolerance 欄位控制比對嚴格程度（`exact` / `semantic` / `lenient`）

### 4.3 重播引擎設計

重播引擎是一個獨立的 Python 腳本（或模組），能載入 fixture 中的音頻檔案，分別通過 Whisper 和 LLM 管線，然後與預期結果比對。

核心 API 設計：

```python
# src/typeness/replay.py

def replay_whisper(audio_path: str) -> str:
    """Load audio file and run Whisper transcription."""
    ...

def replay_llm(whisper_text: str) -> str:
    """Run LLM post-processing on given text."""
    ...

def replay_full(audio_path: str) -> dict:
    """Run full pipeline: audio → Whisper → LLM."""
    return {
        "whisper_text": ...,
        "processed_text": ...,
        "whisper_latency": ...,
        "llm_latency": ...,
    }
```

關鍵設計決策：
- 重播引擎重用 `transcribe.py` 和 `postprocess.py` 的現有函式，避免重複邏輯
- 模型載入只做一次（lazy singleton），多個案例共用同一個模型實例
- 支援只跑 Whisper 或只跑 LLM，根據修改範圍決定

### 4.4 LLM-as-Judge 裁判機制

業界研究和實踐表明，LLM-as-Judge 最有效的做法是：

**二元判定（Pass/Fail）優於多級評分**。多級量表（1-10 分）在 LLM 評估中不穩定，而 Pass/Fail 搭配一句話理由的格式最為可靠。

**Judge Prompt 設計**：

```
你是一個語音輸入法品質的裁判。你需要比較「實際輸出」和「預期輸出」，
判斷實際輸出的品質是否可接受。

評判標準：
1. 核心語意是否保留（最重要）
2. 沒有遺漏關鍵資訊
3. 沒有添加原文沒有的內容
4. 標點符號和空格的細微差異可以接受
5. 同義詞替換可以接受（如「因此」vs「所以」）

{notes}  ← 如果案例有特別的判斷準則，會注入這裡

預期輸出：
{expected}

實際輸出：
{actual}

請回答 JSON 格式：
{
  "verdict": "PASS" 或 "FAIL",
  "reason": "一句話說明理由",
  "differences": ["列出主要差異點"]
}
```

**誰來當裁判？** 這裡有兩個選擇：

1. **Claude Code 本身**：在 skill 執行時，Claude Code 直接閱讀兩段文字並判斷。優點是不需要額外的 API 呼叫，缺點是只在互動式使用時可用。
2. **獨立的 LLM API 呼叫**：在自動化測試腳本中呼叫 Claude API 或使用本地的 Qwen3 模型判斷。優點是可以自動化跑，缺點是需要 API key 或額外的推論資源。

**建議方案**：採用混合策略。

- **互動式修正流程**（skill）：由 Claude Code 自己充當裁判，直接閱讀新舊輸出並判斷。這是最自然的做法，不需要額外設定。
- **自動化回歸測試**（CLI 腳本）：產生差異報告（包含每個案例的新舊輸出對比），由 Claude Code 在 skill 中閱讀報告並批次判斷。這樣不需要獨立的 API key，同時保留了人工審查的能力。

### 4.5 非確定性的處理策略

Qwen3-1.7B 目前使用 `do_sample=False`，理論上在相同輸入下應該產生一致的輸出。但在實務上仍可能有微小差異（GPU 浮點精度、不同 batch size 等）。處理策略：

1. **Whisper 階段**：語音轉文字天然具有非確定性。比較標準不應是完全一致，而是語意等價。可以用 CER（Character Error Rate）作為定量參考，但最終判斷由 LLM Judge 決定。
2. **LLM 階段**：由於用了 `do_sample=False`，多數情況下輸出應該穩定。如果出現差異，大多是因為程式碼或 prompt 的修改。
3. **容忍度分級**：
   - `exact`：要求完全一致（適用於已知確定性輸出的案例）
   - `semantic`：語意等價即可（預設，由 LLM Judge 判斷）
   - `lenient`：只要核心資訊保留就算通過（適用於已知不穩定的長段落）

### 4.6 業界最佳實踐參考

**jiwer 函式庫**：業界標準的 WER（Word Error Rate）/ CER（Character Error Rate）計算工具。可用於提供定量參考，但對中文的適用性有限（中文分詞問題），建議以 CER 為主。

**LLM-as-Judge 常見陷阱**：
- 位置偏差（偏好第一個答案）→ 我們的場景不涉及排名，只是比較兩段文字，影響較小
- 冗長偏差（偏好較長輸出）→ 需要在 prompt 中明確「長度不是評判標準」
- 自我增強偏差（偏好同家族模型）→ 由 Claude 判斷 Qwen3 輸出，不存在此問題

**pytest 整合模式**：業界流行將 LLM 評估寫成 pytest 測試案例（如 pytest-evals、DeepEval 框架）。但考慮到 Typeness 的場景（需要 GPU 載入模型、互動式修正），更適合用獨立的重播腳本搭配 Claude Code skill。

## 解決方案設計

### 方案概覽

整個系統由三個元件組成：

```
┌─────────────────────────────────────────────────┐
│                  Claude Code Skills              │
│                                                  │
│  /fix-transcription    /run-regression           │
│  (互動式修正流程)       (回歸測試流程)              │
└──────────────┬─────────────────┬────────────────┘
               │                 │
               ▼                 ▼
┌──────────────────────────────────────────────────┐
│              replay.py (重播引擎)                  │
│                                                   │
│  replay_whisper() │ replay_llm() │ replay_full()  │
│  load_models()    │ run_all_cases()               │
└──────────────────────────────────────────────────┘
               │                 │
               ▼                 ▼
┌──────────────────────────────────────────────────┐
│           tests/fixtures/ (測試案例庫)              │
│                                                   │
│  cases.json + *.wav 音頻檔案                       │
└──────────────────────────────────────────────────┘
```

### 元件一：測試案例管理

**tests/fixtures/cases.json** — 所有測試案例的清冊。每個案例記錄：
- 音頻檔案路徑
- Whisper 預期輸出（可選）
- LLM 預期輸出
- 人工備註（特殊判斷準則）
- 容忍度等級
- 標籤

**新增案例的方式**：透過 `/fix-transcription` skill，使用者描述問題後，skill 會：
1. 從 `debug/` 複製音頻到 `tests/fixtures/`
2. 在 `cases.json` 新增一筆記錄
3. 設定預期輸出

### 元件二：重播引擎 (replay.py)

一個獨立模組，提供以下功能：
- 載入 Whisper 和/或 LLM 模型
- 讀取 WAV 音頻並跑 Whisper 轉錄
- 讀取文字並跑 LLM 後處理
- 批次執行所有 fixture 案例
- 輸出結構化的結果報告（JSON 格式）

CLI 介面：

```bash
# 只跑 LLM 階段（最常見）
uv run python -m typeness.replay --stage llm

# 只跑 Whisper 階段
uv run python -m typeness.replay --stage whisper

# 跑完整管線
uv run python -m typeness.replay --stage full

# 只跑特定案例
uv run python -m typeness.replay --case 20260215_105248

# 只跑特定標籤
uv run python -m typeness.replay --tag long
```

輸出格式（JSON 報告）：

```json
{
  "run_timestamp": "2026-02-15T15:30:00",
  "stage": "llm",
  "results": [
    {
      "case_id": "20260215_105248",
      "expected": "預期文字...",
      "actual": "實際輸出...",
      "match": "exact" | "different",
      "char_diff_ratio": 0.05
    }
  ]
}
```

### 元件三：Claude Code Skills

#### Skill 1: `/fix-transcription` — 互動式修正流程

用途：使用者發現辨識錯誤時，啟動修正流程。

工作流程：
1. 使用者告訴 Claude Code 哪個 debug case 有問題、預期輸出是什麼
2. Claude Code 讀取該 case 的音頻和 JSON
3. 將案例加入 `tests/fixtures/`，建立預期輸出
4. 重播確認問題可重現
5. 分析 Whisper 輸出和 LLM prompt，找出可能的修正方向
6. 提出修改建議，使用者確認後實施
7. 重播修改後的結果，確認修正生效
8. 跑回歸測試確認其他案例沒有被破壞

#### Skill 2: `/run-regression` — 回歸測試流程

用途：修改程式碼後，驗證所有既存案例。

工作流程：
1. 執行重播引擎，產生結果報告
2. 過濾出完全一致的案例（自動通過）
3. 對有差異的案例，Claude Code 逐一比較新舊輸出
4. 對每個差異案例判定：PASS（可接受的差異）或 FAIL（品質下降）
5. 產生最終報告，列出所有 FAIL 案例及理由

## 建議與決策指引

基於分析結果，建議分三個階段實施：

**第一階段：基礎建設**
- 建立 `tests/fixtures/` 目錄結構和 `cases.json` 格式
- 實作 `replay.py` 重播引擎（重用現有的 transcribe/postprocess 模組）
- 從現有 9 個 debug 案例中挑選有代表性的建立初始測試集

**第二階段：互動式 Skill**
- 撰寫 `/fix-transcription` skill
- 撰寫 `/run-regression` skill
- 實際用幾個案例走過完整流程，驗證可行性

**第三階段：持續改進**
- 根據使用經驗調整 LLM Judge 的判斷 prompt
- 累積更多測試案例
- 考慮加入 jiwer 的 CER 計算作為輔助定量指標

## 下一步行動計畫

實施需要分階段進行。第一階段重點是建立技術基礎設施（replay 模組和 fixture 格式），第二階段則是撰寫 Claude Code skills 串接完整工作流程。

具體步驟：
- **立即行動**：撰寫 PRD，詳細定義 replay 模組的 API、fixture 格式、skill 的互動流程
- **技術確認**：驗證現有的 `transcribe()` 和 `process_text()` 函式能否直接被 replay 引擎呼叫（從程式碼審查來看是可以的）
- **新增依賴**：可能需要 `jiwer`（CER 計算，可選）

## 參考資料

### 技術文件
- [jiwer — WER/CER 計算工具](https://github.com/jitsi/jiwer)
- [Evidently AI — LLM-as-a-Judge 完整指南](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
- [Claude Code Skills 官方文件](https://code.claude.com/docs/en/skills)
- [Skill Authoring Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)

### 實作範例
- [DeepEval — LLM 評估框架](https://github.com/confident-ai/deepeval)
- [pytest-evals — pytest LLM 測試插件](https://github.com/AlmogBaku/pytest-evals)
- [Anthropic 官方 Skills 範例](https://github.com/anthropics/skills)

### 延伸閱讀
- [Eugene Yan — 評估 LLM 評估器](https://eugeneyan.com/writing/llm-evaluators/)
- [Eric Ma — 在 pytest 中撰寫 LLM 評估](https://ericmjl.github.io/blog/2024/9/6/on-writing-llm-evals-in-pytest/)
- [Whisper 轉錄測試實踐](https://blog.lopp.net/openai-whisper-transcription-testing/)
