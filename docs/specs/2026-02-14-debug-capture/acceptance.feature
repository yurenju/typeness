# language: zh-TW
功能: Debug 錄音保存
  作為 開發者
  我想要 在 debug 模式下自動保存每次語音輸入的音訊和辨識結果
  以便 能夠重現和診斷語音辨識問題

  場景: 使用 --debug 參數啟動程式
    假設 開發者在終端機中
    當 執行 "uv run typeness --debug"
    那麼 終端機應顯示 "Debug mode ON" 相關提示訊息
    並且 程式正常進入等待錄音狀態

  場景: 使用 --help 查看參數說明
    假設 開發者在終端機中
    當 執行 "uv run typeness --help"
    那麼 輸出中應包含 "--debug" 參數的說明文字

  場景: debug 模式下完成一次語音錄入後保存檔案
    假設 程式以 "--debug" 模式啟動且模型已載入
    當 開發者按下 Shift+Win+A 開始錄音
    並且 對麥克風說話超過 0.3 秒
    並且 再次按下 Shift+Win+A 停止錄音
    那麼 debug 目錄下應新增一個 .wav 音訊檔案
    並且 debug 目錄下應新增一個對應的 .json metadata 檔案
    並且 兩個檔案的時間戳前綴應一致
    並且 終端機應顯示保存的檔案路徑

  場景: 確認 JSON metadata 內容完整
    假設 debug 目錄中已有一組保存的檔案
    當 開發者開啟 .json 檔案
    那麼 JSON 中應包含 "timestamp" 欄位（ISO 格式）
    並且 JSON 中應包含 "audio_file" 欄位（對應 .wav 檔名）
    並且 JSON 中應包含 "duration_seconds" 欄位（正數）
    並且 JSON 中應包含 "whisper_text" 欄位（非空字串）
    並且 JSON 中應包含 "processed_text" 欄位（非空字串）
    並且 JSON 中應包含 "whisper_latency" 和 "llm_latency" 欄位（正數）

  場景: 確認 WAV 檔案可播放
    假設 debug 目錄中已有一組保存的 .wav 檔案
    當 開發者用音訊播放器開啟該 .wav 檔案
    那麼 應能聽到與原始錄音一致的語音內容

  場景: 非 debug 模式不產生檔案
    假設 程式以正常模式啟動（不帶 --debug）
    當 開發者完成一次正常的語音錄入
    那麼 不應產生 debug 目錄或其中的檔案

  場景: debug 目錄被 git 忽略
    假設 debug 目錄中已有檔案
    當 開發者執行 "git status"
    那麼 不應顯示 debug 目錄中的任何檔案為 untracked
