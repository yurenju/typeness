---
description: 執行回歸測試：重播所有測試案例，由 LLM-as-Judge 判斷結果
---

# 執行回歸測試

你正在為 Typeness 語音輸入法執行回歸測試。請依序執行以下步驟。

## 步驟 1：執行重播引擎

從使用者的參數中解析 `--stage` 旗標，若未指定則預設為 `full`。

執行重播引擎：

```bash
uv run python -m typeness.replay --stage <stage>
```

等待指令完成。重播引擎需載入 GPU 模型（約 10-20 秒），接著逐一處理每個測試案例。Console 會顯示處理進度和摘要。

## 步驟 2：讀取報告

讀取 `tests/fixtures/last_run.json`，將結果分為：

- **Auto-PASS**：`"match": "exact"` 或 `"match": "acceptable"` 的案例 — 自動通過，不需進一步判斷。
- **需要判斷**：`"match": "different"` 的案例 — 需要 LLM-as-Judge 評估。

若所有案例皆為 Auto-PASS，直接跳到步驟 4。

## 步驟 3：LLM-as-Judge 判斷

對每個 `"different"` 的案例，從報告中讀取：

- `expected`（預期輸出）
- `actual`（模型實際輸出）
- `char_diff_ratio`（差異比例的定量參考）

同時從 `tests/fixtures/cases.json` 中讀取該案例的：

- `notes`（特殊判斷準則，如果有的話）
- `description`（案例描述，提供上下文）

依以下準則（按優先順序）判斷每個案例為 **PASS** 或 **FAIL**：

1. **核心語意是否保留**（最重要）— 意思必須相同
2. **沒有遺漏關鍵資訊** — 不能丟掉重要內容
3. **沒有添加原文沒有的內容** — 不能憑空產生文字
4. **標點符號和空格的細微差異可以接受**
5. **同義詞替換可以接受**（如「因此」vs「所以」）
6. **長度不是評判標準** — 不偏好較長或較短的輸出
7. **若案例有 `notes`**，按照 notes 的特殊要求判斷

對每個案例附上一句話理由。

## 步驟 4：產生最終報告

在 console 顯示摘要表格：

```
=== Regression Report ===
Total: N | Auto-PASS: N | Judge-PASS: N | FAIL: N

[AUTO-PASS]  <case_id> - <description>
[AUTO-PASS]  <case_id> - <description>
[PASS]       <case_id> - <reason>
[FAIL]       <case_id> - <reason>
```

對每個 **FAIL** 案例，顯示：

1. **預期輸出** vs **實際輸出**（完整顯示兩段文字）
2. **失敗理由**（一句話）
3. **建議修正方向**：
   - 若為 LLM 後處理問題：建議檢查 `src/typeness/postprocess.py` 的 `LLM_SYSTEM_PROMPT`
   - 若為 Whisper 問題：建議檢查 `src/typeness/transcribe.py` 的 `WHISPER_INITIAL_PROMPT`

若有任何 FAIL 案例，建議使用者以 `/fix-transcription` 逐一調查修正。

## 注意事項

- 重播引擎需要 GPU，載入模型約需 10-20 秒。
- Windows 終端可能顯示亂碼中文 — 請讀取 `last_run.json` 確認實際內容。
- LLM 使用 `do_sample=False`，相同輸入應產生相同輸出。
- `tests/fixtures/last_run.json` 每次執行都會覆寫 — 歷史由 git 追蹤。
- 若 `tests/fixtures/cases.json` 不存在或沒有案例，提示使用者先透過 `/fix-transcription` 建立測試案例，或手動填入 fixtures。
