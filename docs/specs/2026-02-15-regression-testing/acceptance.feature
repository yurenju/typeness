# language: zh-TW
功能: 語音辨識回歸測試工作流程
  作為 Typeness 開發者
  我想要能夠建立測試案例並執行回歸測試
  以便確保程式修改不會破壞既有的辨識品質

  背景:
    假設 Typeness 專案已安裝（uv sync 完成）
    並且 tests/fixtures/ 目錄存在且包含至少 3 個測試案例
    並且 GPU 可用（CUDA 裝置可存取）

  場景: 重播引擎 CLI 可正常執行
    當 執行 "uv run python -m typeness.replay --help"
    那麼 應該顯示 --stage、--case、--tag、--output 等參數說明
    並且 退出碼為 0

  場景: 只跑 LLM 階段的回歸測試
    當 執行 "uv run python -m typeness.replay --stage llm"
    那麼 console 應顯示每個案例的處理進度
    並且 console 應顯示摘要（Total / Exact / Different 計數）
    並且 tests/fixtures/last_run.json 應被建立
    並且 last_run.json 的 stage 欄位為 "llm"
    並且 每個 result 包含 case_id、expected、actual、match、char_diff_ratio

  場景: 只跑 Whisper 階段的回歸測試
    當 執行 "uv run python -m typeness.replay --stage whisper"
    那麼 tests/fixtures/last_run.json 應被建立
    並且 last_run.json 的 stage 欄位為 "whisper"

  場景: 跑完整管線的回歸測試
    當 執行 "uv run python -m typeness.replay --stage full"
    那麼 tests/fixtures/last_run.json 應被建立
    並且 last_run.json 的 stage 欄位為 "full"
    並且 每個 result 包含 whisper_text 和 processed_text

  場景: 篩選特定案例執行
    假設 tests/fixtures/cases.json 中有案例 ID 為 "20260215_084842"
    當 執行 "uv run python -m typeness.replay --case 20260215_084842 --stage llm"
    那麼 last_run.json 的 results 只包含一個案例
    並且 該案例的 case_id 為 "20260215_084842"

  場景: 篩選特定標籤執行
    假設 tests/fixtures/cases.json 中有案例標記為 "short" 標籤
    當 執行 "uv run python -m typeness.replay --tag short --stage llm"
    那麼 last_run.json 的 results 只包含標記為 "short" 的案例

  場景: 初始測試集基準驗證
    假設 初始測試集的 processed_expected 是用目前 LLM 輸出設定的
    當 執行 "uv run python -m typeness.replay --stage llm"
    那麼 所有案例的 match 應為 "exact"
    並且 所有案例的 char_diff_ratio 應為 0.0

  場景: /fix-transcription skill 可被觸發
    當 在 Claude Code 中輸入 "/fix-transcription"
    那麼 應載入 fix-transcription skill
    並且 Claude Code 應列出 debug/ 目錄中可用的案例

  場景: /fix-transcription skill 建立新測試案例
    假設 debug/ 目錄中有案例 "20260215_084842"
    當 使用 /fix-transcription 指定該案例並提供預期輸出
    那麼 tests/fixtures/ 中應新增對應的 WAV 檔案
    並且 cases.json 中應新增一筆記錄，包含正確的 processed_expected

  場景: /run-regression skill 可被觸發
    當 在 Claude Code 中輸入 "/run-regression"
    那麼 應載入 run-regression skill
    並且 Claude Code 應執行重播引擎並產生結果

  場景: /run-regression skill 判斷差異案例
    假設 last_run.json 中有 match 為 "different" 的案例
    當 /run-regression skill 進入判斷階段
    那麼 Claude Code 應逐一閱讀每個 different 案例的 expected 和 actual
    並且 對每個案例給出 PASS 或 FAIL 判定
    並且 附上一句話理由
