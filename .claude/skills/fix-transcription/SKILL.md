---
description: 修正語音辨識錯誤：從 debug 資料建立測試案例，診斷並修復問題
---

# 修正語音辨識錯誤

你正在協助使用者修正 Typeness 語音輸入法的辨識錯誤。請依序執行以下步驟。

## 步驟 1：辨識案例

判斷使用者指的是哪個 debug 案例：

1. **優先檢查 IDE 上下文**：查看對話中的 `ide_opened_file` 或 `ide_selection` 標籤。如果使用者開啟了 `debug/*_result.json`，從檔名提取 case_id（例如從 `20260215_084842_result.json` 取得 `20260215_084842`）。
2. **檢查參數**：若使用者在參數中提供了時間戳格式的 ID（如 `20260215_084842`），以參數為準。
3. **兜底方案 — 列出可用案例**：若以上都無法判斷，列出 `debug/` 中所有 `*_result.json` 的時間戳和 `whisper_text` 前 50 字，讓使用者選擇。

取得 case_id 後，讀取 `debug/<case_id>_result.json` 並顯示：
- **Whisper 輸出**：`whisper_text` 欄位
- **LLM 輸出**：`processed_text` 欄位
- **錄音時長**：`duration_seconds` 欄位

## 步驟 2：確認預期輸出

使用者的參數描述了輸出的問題（如「少了前導語」「標點錯了」）。

- 讀取 debug JSON 中的 `whisper_text` 和 `processed_text`
- 根據使用者的問題描述，推敲正確的 `processed_expected`（理想輸出）應該是什麼
- 判斷是否需要 `processed_acceptable`（可接受輸出）— 當理想輸出包含超出 LLM 能力的修正（如同音字修正、專有名詞修正），設定一個只要求 LLM 合理範圍內修正的可接受版本
- 將推敲結果顯示給使用者確認，使用者可以直接同意或修正
- 若參數中沒有問題描述，詢問使用者：「正確的輸出應該是什麼？」

## 步驟 3：建立測試案例

預期輸出確認後：

1. 複製 `debug/<case_id>_audio.wav` 到 `tests/fixtures/<case_id>_audio.wav`
2. 讀取目前的 `tests/fixtures/cases.json`。若檔案不存在，先以 `{"cases": []}` 建立它。
3. 新增一筆案例：
   ```json
   {
     "id": "<case_id>",
     "audio_file": "<case_id>_audio.wav",
     "description": "<簡短描述這個案例測試的情境>",
     "whisper_expected": "<debug JSON 中目前的 whisper_text>",
     "processed_expected": "<使用者確認的理想輸出>",
     "processed_acceptable": "<可接受的輸出，或省略此欄位>",
     "tags": ["<適當的標籤>"],
     "notes": "<特殊判斷備註，或 null>"
   }
   ```
4. `whisper_expected` 預設為目前的 Whisper 輸出（除非使用者指出 Whisper 也有問題）
5. `processed_expected` 設為使用者確認的理想輸出
6. `processed_acceptable`（選用）— 當理想輸出包含超出 LLM 能力的修正（如同音字、專有名詞），設定一個只要求 LLM 合理範圍內修正的版本。重播引擎匹配 acceptable 時會標記為 `"match": "acceptable"` 而非 `"different"`
7. 依錄音長度和內容選擇標籤：`short`（<10 秒）、`medium`（10-30 秒）、`long`（>30 秒）、`technical`、`mixed-lang`、`list` 等

## 步驟 4：重播驗證

執行重播引擎確認問題可重現：

```bash
uv run python -m typeness.replay --case <case_id> --stage llm
```

若問題出在 Whisper（而非 LLM），改用 `--stage full`。

檢查 `tests/fixtures/last_run.json` — 該案例應顯示 `"match": "different"`（不應為 `"exact"` 或 `"acceptable"`），確認問題已被捕捉。

## 步驟 5：分析與修正

根據問題類型：

- **LLM 後處理問題**（最常見）：讀取 `src/typeness/postprocess.py`，特別是 `LLM_SYSTEM_PROMPT`。建議 prompt 調整（新增規則、新增範例）來修正問題。等使用者確認後再修改。
- **Whisper 問題**：讀取 `src/typeness/transcribe.py` 檢查參數。這類問題較難修正，可能需要調整 `WHISPER_INITIAL_PROMPT` 或生成參數。

提出具體修改建議，等待使用者同意後實施。

## 步驟 6：驗證修正

修改完成後：

1. 重跑該案例：
   ```bash
   uv run python -m typeness.replay --case <case_id> --stage llm
   ```
2. 確認 `last_run.json` 中該案例顯示 `"match": "exact"` 或 `"match": "acceptable"`
3. 跑全部案例檢查有無回歸：
   ```bash
   uv run python -m typeness.replay --stage llm
   ```
4. 向使用者顯示完整的回歸測試摘要
5. 若有既有案例出現回歸，與使用者討論如何調整修正

## 注意事項

- 重播引擎載入 GPU 模型需要約 10-20 秒，這是正常的。
- Windows 終端可能顯示亂碼中文 — 這是 console 編碼問題，不是 bug。請讀取 `last_run.json` 確認實際內容。
- LLM 使用 `do_sample=False`，相同輸入應產生相同輸出。
- `tests/fixtures/last_run.json` 每次執行都會覆寫 — 歷史由 git 追蹤。
