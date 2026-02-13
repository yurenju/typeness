# 實作計畫

## 參考文件

**PRD 文件路徑：** `docs/specs/2026-02-13-global-hotkey-clipboard/prd.md`
**研究文件路徑：** `docs/research/2026-02-12-voice-input-tool-feasibility.md`

## 任務概要

- [x] 安裝新依賴並驗證環境
- [x] 實作全域鍵盤監聽模組
- [x] 實作剪貼簿與自動貼上模組
- [ ] 重構主程式為事件驅動架構
- [ ] 端到端整合與邊界處理
- [ ] 執行驗收測試
- [ ] 更新專案文件

## 任務細節

### 安裝新依賴並驗證環境

**實作要點**
- 在 `pyproject.toml` 的 `dependencies` 中新增 `pynput` 和 `pyperclip`
- 執行 `uv sync` 安裝新依賴
- 驗證 pynput 能在 Windows 上正常監聽鍵盤事件（不需管理員權限）
- 驗證 pyperclip 能正常讀寫系統剪貼簿

**相關檔案**
- `pyproject.toml` - 新增 pynput、pyperclip 依賴

**完成檢查**
- 執行 `uv run python -c "from pynput import keyboard; print('pynput OK')"` 確認匯入成功
- 執行 `uv run python -c "import pyperclip; pyperclip.copy('test'); print(pyperclip.paste())"` 確認輸出 `test`

**實作備註**
照預期開發

---

### 實作全域鍵盤監聽模組

**實作要點**
- 建立 `hotkey.py` 模組，封裝全域鍵盤監聽邏輯
- 使用 `pynput.keyboard.Listener` 監聽右 Alt 鍵（`Key.alt_r`）
- 實作 Toggle 模式狀態機：idle → recording → idle
  - 第一次按下右 Alt：狀態從 idle 切換到 recording
  - 第二次按下右 Alt：狀態從 recording 切換到 idle，觸發辨識流程
- Listener callback 必須保持輕量——僅透過 `queue.Queue` 分派事件到工作執行緒，不做任何耗時操作
- 防禦 AltGr 問題：追蹤按鍵狀態，當 `Key.ctrl_l` 同時被按住時忽略 `Key.alt_r`（避免歐洲鍵盤佈局下 AltGr 被誤判）
- 過濾 injected 事件：使用 pynput 1.8+ 的 `injected` 參數，或退而使用 `_simulating` 旗標，忽略程式自身模擬的鍵盤事件（避免自動貼上觸發的 Ctrl+V 被攔截）
- 提供 `start()` 和 `stop()` 方法，方便主程式控制生命週期

**相關檔案**
- `hotkey.py` - 全域鍵盤監聽模組（新建）

**完成檢查**
- 執行測試腳本，按右 Alt 一次印出 "recording start"，再按一次印出 "recording stop"
- 按 Alt+Tab 等組合鍵不會誤觸發
- 按 Ctrl+C 能正常結束程式，右 Alt 恢復正常功能

**實作備註**
[方向調整] 原計畫使用右 Alt 單鍵觸發，但右 Alt 被 Windows/VSCode 攔截無法觸發。先後嘗試 Win+Shift+D 和 Ctrl+Win+A 也有衝突，最終改用 Shift+Win+A 組合鍵，確認可正常運作。
[技術決策] 組合鍵匹配使用 set-based 方式追蹤按下的鍵，搭配 normalize 方法統一左右修飾鍵變體（Shift_L/Shift_R → Shift, Cmd_L/Cmd_R → Cmd）和大小寫字母。

---

### 實作剪貼簿與自動貼上模組

**實作要點**
- 建立 `clipboard.py` 模組，封裝剪貼簿操作和自動貼上邏輯
- 使用 `pyperclip.copy()` 將文字寫入系統剪貼簿
- 使用 `pynput.keyboard.Controller` 模擬 Ctrl+V 鍵盤事件
- 在模擬按鍵前設定 `_simulating` 旗標（或通知 hotkey 模組），避免鍵盤監聽模組攔截自己模擬的事件
- 在 `pyperclip.copy()` 和模擬 Ctrl+V 之間加入短暫延遲（~20ms），確保剪貼簿就緒
- 提供單一函式 `paste_text(text: str)` 供主程式呼叫

**相關檔案**
- `clipboard.py` - 剪貼簿與自動貼上模組（新建）

**完成檢查**
- 開啟記事本，執行測試腳本呼叫 `paste_text("測試文字")`，確認「測試文字」出現在記事本中
- 執行後按 Ctrl+V，確認剪貼簿中仍然是「測試文字」

**實作備註**
照預期開發

---

### 重構主程式為事件驅動架構

**實作要點**
- 重構 `typeness.py`，將主迴圈從 `input()` 阻塞式改為事件驅動式
- 主迴圈使用 `queue.Queue` 接收來自 hotkey 模組的事件，以 `queue.get(timeout=0.5)` 輪詢
- 流程改為：
  1. 啟動時載入 Whisper 和 LLM 模型（同現有行為）
  2. 啟動全域鍵盤監聽（hotkey 模組）
  3. 主迴圈等待事件：
     - 收到 "start_recording" 事件 → 呼叫 `record_audio_start()` 開始錄音
     - 收到 "stop_recording" 事件 → 呼叫 `record_audio_stop()` 停止錄音，執行辨識 → LLM 處理 → 自動貼上
- 修改 `record_audio()` 函式，拆分為 `record_audio_start()` 和 `record_audio_stop()`：
  - `record_audio_start()`：啟動 sounddevice InputStream，開始收集音訊 chunks
  - `record_audio_stop()`：停止 InputStream，合併 chunks 並回傳 numpy 陣列
  - 使用模組層級的共享狀態（stream 和 chunks list）在兩個函式之間傳遞
- 在辨識和 LLM 處理完成後，呼叫 clipboard 模組的 `paste_text()` 自動貼上
- 終端機中保留 log 輸出（開始錄音、停止錄音、Whisper 結果、LLM 結果、時間統計）
- 保留 Ctrl+C 優雅退出：在 `finally` 中呼叫 `listener.stop()` 清除鍵盤 hook
- 將現有的 `load_whisper()`、`transcribe()`、`load_llm()`、`process_text()` 等函式保留在 `typeness.py` 中不動（或視需要拆分，但不強制）

**相關檔案**
- `typeness.py` - 主程式，重構主迴圈和錄音邏輯
- `hotkey.py` - 匯入並啟動鍵盤監聽
- `clipboard.py` - 匯入並呼叫自動貼上

**完成檢查**
- 執行 `uv run python typeness.py`，程式啟動後顯示「就緒」訊息
- 按右 Alt 開始錄音（終端機顯示 log），說一段話，再按右 Alt 停止
- 辨識完成後，結果自動貼上到當前焦點視窗
- 終端機顯示完整的處理時間統計
- 按 Ctrl+C 正常退出

**實作備註**
<!-- 執行過程中填寫 -->

---

### 端到端整合與邊界處理

**實作要點**
- 處理錄音長度為零的情況（按右 Alt 馬上又按一次）——跳過辨識，印出提示
- 處理 Whisper 辨識結果為空的情況——跳過 LLM 和貼上，印出提示
- 確保辨識/LLM 處理期間按右 Alt 不會觸發新的錄音（忙碌狀態鎖定）
- 確保模擬 Ctrl+V 不觸發鍵盤監聽的回呼（injected 事件過濾或 `_simulating` 旗標）
- 啟動訊息顯示：程式就緒後印出「按右 Alt 開始語音輸入」
- 測試連續兩次語音輸入的流程穩定性

**相關檔案**
- `typeness.py` - 主程式邊界處理
- `hotkey.py` - 忙碌狀態鎖定
- `clipboard.py` - injected 事件過濾

**完成檢查**
- 快速連按兩次右 Alt（幾乎無錄音），程式不崩潰，印出「無錄音」提示
- 在辨識處理期間按右 Alt，不會啟動新的錄音
- 連續完成兩次完整的語音輸入流程，兩次都正常貼上

**實作備註**
<!-- 執行過程中填寫 -->

---

### 執行驗收測試

**實作要點**
- 使用 AI 讀取 acceptance.feature 檔案
- 透過指令或手動操作執行每個場景
- 驗證所有場景通過並記錄結果
- 如發現問題，記錄詳細的錯誤資訊和重現步驟

**相關檔案**
- `docs/specs/2026-02-13-global-hotkey-clipboard/acceptance.feature` - Gherkin 格式的驗收測試場景
- `docs/specs/2026-02-13-global-hotkey-clipboard/acceptance-report.md` - 詳細的驗收測試執行報告（執行時生成）

**實作備註**
<!-- 執行過程中填寫 -->

---

### 更新專案文件

**實作要點**
- 更新 README.md：
  - 更新功能說明（新增全域快捷鍵和自動貼上）
  - 更新安裝步驟（新增 pynput、pyperclip 依賴）
  - 更新使用方式（右 Alt 操作說明取代 Enter 操作說明）
- 更新 CLAUDE.md（如已存在）：
  - 更新專案架構（從單一檔案變成多模組）
  - 新增 hotkey.py、clipboard.py 模組說明

**相關檔案**
- `README.md` - 專案主要說明文件
- `CLAUDE.md` - AI 助手的專案指引文件

**實作備註**
<!-- 執行過程中填寫 -->

---

## 實作參考資訊

### 來自研究文件的技術洞察
> **文件路徑：** `docs/research/2026-02-12-voice-input-tool-feasibility.md`

- **全域快捷鍵方案**：研究建議使用 pynput，跨平台能力好，`Key.alt_r` 可直接偵測右 Alt。pynput 的回呼函式在作業系統執行緒中直接執行，不可做長時間操作，應用 `queue.Queue` 分派事件到工作執行緒
- **剪貼簿 + 自動貼上流程**：
  ```python
  pyperclip.copy(text)
  time.sleep(0.05)  # 確保剪貼簿就緒
  # 模擬 Ctrl+V（使用 pynput Controller 或 pyautogui）
  ```
- **執行緒設計**：pynput Listener 執行在 daemon thread，透過 queue.Queue 與主執行緒溝通。Controller 可從任意執行緒呼叫，是 thread-safe 的
- **參考專案**：simple-whisper-stt 技術棧幾乎完全一致（faster-whisper + sounddevice + keyboard + pyperclip + pyautogui + pystray），Push-to-talk 模式可作為功能原型參考

### 來自 PRD 的實作細節
> **文件路徑：** `docs/specs/2026-02-13-global-hotkey-clipboard/prd.md`

- **Toggle 模式**：右 Alt 第一次按下開始錄音，第二次按下停止錄音並觸發辨識。不是 Push-to-talk
- **貼上內容**：LLM 處理後的最終文字（非 Whisper 原始結果）
- **無回饋設計**：不需要視覺或聲音回饋，靜默完成錄音→辨識→貼上流程
- **終端機保留 log**：程式仍在終端機前景運行，終端機中顯示運行狀態和結果
- **不干擾 Alt 組合鍵**：僅攔截單獨按下右 Alt 的事件，Alt+Tab 等組合鍵不受影響
- **已確認不需管理員權限**：WH_KEYBOARD_LL 低階鍵盤 hook 一般使用者即可安裝

### 來自技術研究的補充發現

- **右 Alt 與 AltGr**：繁體中文鍵盤佈局（注音/倉頡）以 US QWERTY 為基底，Right Alt 發出乾淨的 `Key.alt_r` 事件，不會附帶 `Key.ctrl_l`。但仍應加入防禦性檢查，以支援安裝多語言鍵盤佈局的使用者
- **過濾 injected 事件**：pynput 1.8+ 的 callback 支援 `injected` 參數，可用來區分硬體按鍵和程式模擬按鍵。亦可用 `win32_event_filter` 或簡單的 `_simulating` 旗標實現
- **pyperclip vs pyautogui**：建議使用 pyperclip（剪貼簿）+ pynput Controller（模擬按鍵），避免引入 pyautogui 的重量級依賴（Pillow 等）。兩者底層都使用 Win32 SendInput API
- **Listener + Controller 共存**：可安全地在同一個 process 中使用，Controller 是無狀態物件，可從任意執行緒呼叫
- **優雅退出**：使用 `listener.join(timeout=0.5)` 模式保持主執行緒對 Ctrl+C 的響應性。不加 timeout 的 `join()` 在 Windows 上可能吞掉 KeyboardInterrupt

### 關鍵技術決策

- **使用 pynput（非 keyboard 套件）**：pynput 跨平台能力更好，且已透過研究確認在 Windows 上不需管理員權限。pynput 同時提供 Listener（監聽）和 Controller（模擬按鍵），減少依賴數量
- **使用 pyperclip（非 win32clipboard）**：pyperclip 跨平台、API 簡潔、無額外依賴。本階段不需備份/還原剪貼簿中的非文字內容（圖片、富文字），pyperclip 的純文字操作已足夠
- **事件驅動主迴圈取代 input() 阻塞**：使用 queue.Queue 接收鍵盤事件，主迴圈以 timeout 輪詢，保持對 Ctrl+C 的響應性
- **模組拆分但保持簡潔**：拆為 typeness.py（主程式 + 模型載入 + 辨識邏輯）、hotkey.py（鍵盤監聽）、clipboard.py（剪貼簿貼上），共三個檔案。不過度拆分
- **錄音邏輯拆分為 start/stop**：原本的 `record_audio()` 是一個阻塞函式（內部用 input() 等待 Enter），需拆分為非阻塞的 `record_audio_start()` 和 `record_audio_stop()`，以配合事件驅動架構
