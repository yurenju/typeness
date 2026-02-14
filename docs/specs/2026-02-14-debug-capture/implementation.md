# 實作計畫

## 參考文件

**PRD 文件路徑：** 無
**研究文件路徑：** `docs/research/2026-02-14-debug-capture.md`

## 任務概要

- [x] 新增 CLI 參數解析
- [x] 實作 debug 保存函式
- [x] 整合 debug 保存到主事件循環
- [x] 更新 .gitignore 和啟動提示
- [x] 執行驗收測試
- [x] 更新專案文件

## 任務細節

### 新增 CLI 參數解析

**實作要點**
- 在 `__main__.py` 中使用 `argparse` 建立參數解析器
- 新增 `--debug` flag（`store_true`，預設 `False`）
- 解析後將 `args.debug` 傳入 `main(debug=...)`
- 修改 `main.py` 的 `main()` 函式簽名，新增 `debug: bool = False` 參數

**相關檔案**
- `src/typeness/__main__.py` — 新增 argparse 邏輯
- `src/typeness/main.py` — 修改 `main()` 函式簽名

**完成檢查**
- 執行 `uv run typeness --help` 確認顯示 `--debug` 參數說明
- 執行 `uv run typeness --debug` 確認可正常啟動（Ctrl+C 退出）

**實作備註**
[方向調整] 原計畫 argparse 只在 `__main__.py` 的 `if __name__` 區塊中，但 `pyproject.toml` 的 entry point 直接指向 `main:main` 會繞過 `__main__.py`。改為在 `__main__.py` 建立 `cli()` 函式，entry point 改指向 `typeness.__main__:cli`。

---

### 實作 debug 保存函式

**實作要點**
- 在 `main.py` 中新增 `_save_debug_capture()` 函式
- 函式參數：`audio: np.ndarray`, `whisper_text: str`, `processed_text: str`, `rec_duration: float`, `whisper_latency: float`, `llm_latency: float`
- 使用 Python 標準庫 `wave` 模組保存 WAV（scipy 未安裝，不另外安裝）
  - 需要將 float32 numpy array 轉為 int16 PCM：`(audio * 32767).astype(np.int16)`
  - 設定 WAV 參數：1 channel, 2 bytes/sample (int16), 16000 Hz
- 使用 `json.dump()` 保存 metadata JSON
- 時間戳格式：`YYYYMMDD_HHMMSS`，用 `datetime.now().strftime("%Y%m%d_%H%M%S")`
- 檔案命名：`{timestamp}_audio.wav` 和 `{timestamp}_result.json`
- 保存目錄：專案根目錄下的 `debug/`，用 `Path(__file__).resolve().parents[2] / "debug"` 取得
- 自動建立目錄：`os.makedirs(debug_dir, exist_ok=True)`
- JSON 結構包含：`timestamp`, `audio_file`, `duration_seconds`, `whisper_text`, `processed_text`, `whisper_latency`, `llm_latency`
- JSON 使用 `ensure_ascii=False` 和 `indent=2` 確保中文可讀
- 整個函式用 try/except 包裹，失敗時只 print 警告不中斷主流程

**相關檔案**
- `src/typeness/main.py` — 新增 `_save_debug_capture()` 函式

**完成檢查**
- 在 Python REPL 中手動呼叫 `_save_debug_capture()` 傳入假資料，確認 `debug/` 目錄產生正確的 .wav 和 .json 檔案
- 確認 JSON 檔案內容可讀且中文正確顯示

**實作備註**
照預期開發

---

### 整合 debug 保存到主事件循環

**實作要點**
- 在 `main()` 的 `EVENT_STOP_RECORDING` 處理區塊中，於 `paste_text()` 之後、結果顯示之前，加入 debug 保存呼叫
- 僅在 `debug=True` 時執行保存
- 保存成功後在 console 印出保存的檔案路徑，例如 `[Debug] Saved: debug/20260214_153042_result.json`
- 確保 debug 保存不影響原有的處理流程和延遲

**相關檔案**
- `src/typeness/main.py` — 在事件處理中呼叫 `_save_debug_capture()`

**完成檢查**
- 啟動 `uv run typeness --debug`，進行一次語音錄入，確認 `debug/` 目錄產生對應的 .wav 和 .json 檔案
- 確認不帶 `--debug` 啟動時不會產生任何 debug 檔案

**實作備註**
照預期開發

---

### 更新 .gitignore 和啟動提示

**實作要點**
- 在 `.gitignore` 中新增 `debug/` 條目
- 修改 `main()` 的啟動訊息：當 `debug=True` 時額外印出提示，例如 `Debug mode ON — captures saved to debug/`

**相關檔案**
- `.gitignore` — 新增 `debug/`
- `src/typeness/main.py` — 修改啟動訊息

**完成檢查**
- 確認 `git status` 不顯示 `debug/` 目錄中的檔案
- 啟動 `uv run typeness --debug` 確認看到 debug mode 提示訊息

**實作備註**
照預期開發

---

### 執行驗收測試

**實作要點**
- 使用 AI 讀取 acceptance.feature 檔案
- 透過指令執行每個場景
- 驗證所有場景通過並記錄結果
- 如發現問題，記錄詳細的錯誤資訊和重現步驟

**相關檔案**
- `docs/specs/2026-02-14-debug-capture/acceptance.feature` - Gherkin 格式的驗收測試場景
- `docs/specs/2026-02-14-debug-capture/acceptance-report.md` - 詳細的驗收測試執行報告（執行時生成）

**實作備註**
使用者自行驗收。

---

### 更新專案文件

**實作要點**
- 審查 README.md，在 Usage 章節新增 `--debug` 參數的使用說明
- 審查 CLAUDE.md，更新 Running 章節加入 debug 模式說明
- 確保所有程式碼範例和指令都是最新且可執行的

**相關檔案**
- `README.md` - 專案主要說明文件
- `CLAUDE.md` - AI 助手的專案指引文件

**實作備註**
照預期開發

---

## 實作參考資訊

### 來自研究文件的技術洞察
> **文件路徑：** `docs/research/2026-02-14-debug-capture.md`

**WAV 保存（已修正：改用 `wave` 標準庫）**

研究文件原建議使用 `scipy.io.wavfile`，但經確認 scipy 未安裝於此專案環境。改用 Python 標準庫 `wave` 模組，需要手動處理 float32 → int16 轉換：

```python
import wave
import struct
import numpy as np

def _save_wav(path: str, audio: np.ndarray, sample_rate: int = 16000) -> None:
    pcm16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 2 bytes = int16
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
```

**JSON metadata 結構**

```json
{
  "timestamp": "2026-02-14T15:30:42",
  "audio_file": "20260214_153042_audio.wav",
  "duration_seconds": 3.2,
  "whisper_text": "嗯那個就是說我今天去超市買了一些水果",
  "processed_text": "我今天去超市買了一些水果。",
  "whisper_latency": 0.85,
  "llm_latency": 0.42
}
```

**debug 目錄路徑定位**

使用 `Path(__file__).resolve().parents[2]` 從 `src/typeness/main.py` 回溯兩層到專案根目錄：
- `main.py` → `src/typeness/` (parent 0) → `src/` (parent 1) → 專案根 (parent 2)

**錯誤處理策略**

debug 保存是輔助功能，失敗不應中斷主流程。整個保存函式用 `try/except Exception` 包裹，失敗時 print 警告即可。

### 關鍵技術決策

- **`wave` 標準庫取代 `scipy.io.wavfile`**：避免新增依賴，代價是需要手動做 float32 → int16 轉換
- **扁平目錄結構**：所有 debug 檔案放在同一個 `debug/` 目錄，不分子目錄，方便瀏覽
- **時間戳命名 `YYYYMMDD_HHMMSS`**：保證唯一性且易於排序
- **保存時機在 `paste_text()` 之後**：不影響使用者感受到的延遲
- **`argparse` 在 `__main__.py` 中**：遵循 Python 慣例，保持 `main()` 函式可測試
