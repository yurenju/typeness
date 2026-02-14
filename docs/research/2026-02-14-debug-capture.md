# 研究：Debug 錄音保存功能

## 執行摘要

本研究針對 Typeness 語音輸入工具新增「Debug 錄音保存」功能進行技術分析。這個功能的核心目的是讓開發者能夠捕捉難以重現的語音辨識問題——因為口語發音是一次性的，錯過就無法再現。透過保存原始音訊和各階段處理結果，我們可以建立可重現的測試案例，系統性地改善辨識品質。

關鍵發現：

- **實作門檻低**：目前程式碼架構已經將 audio、whisper_text、processed_text 三個關鍵資料點集中在 `main.py` 的事件處理流程中，只需在該處加入保存邏輯即可
- **不需新增依賴**：使用 `scipy.io.wavfile`（scipy 已被 numpy/torch 間接安裝）即可保存 WAV，JSON 為標準庫
- **對效能無顯著影響**：WAV 寫入和 JSON 序列化相比模型推理時間可忽略不計

## 背景與脈絡

Typeness 是一個本地端語音輸入工具，其處理管線為：麥克風錄音 → Whisper 語音辨識 → Qwen3 LLM 文字後處理 → 自動貼上。在日常使用中，經常會遇到辨識結果不如預期的情況，可能的問題來源包括：

1. **Whisper 層面**：某些詞彙、口音或語速導致轉錄錯誤
2. **LLM 層面**：後處理過度刪除內容、標點不當、或格式化錯誤
3. **交互作用**：Whisper 的微小錯誤被 LLM 放大或誤修正

這些問題的共通難處在於「不可重現」——使用者發現問題時，原始語音已經消失，只能憑記憶描述。有了 debug 保存功能，每次發現問題只需要到 debug 目錄找到對應的檔案，就能完整還原當時的輸入輸出。

## 技術分析

### 現有程式碼的切入點

檢視 `main.py` 的事件處理流程，所有需要保存的資料都已經以區域變數存在於 `EVENT_STOP_RECORDING` 的處理區塊中：

```python
# main.py:46-91 — 這些變數都是現成的
audio = record_audio_stop()            # np.ndarray, float32, 16kHz
whisper_text = transcribe(...)         # str
processed_text = process_text(...)     # str
rec_duration = len(audio) / SAMPLE_RATE
whisper_elapsed = ...
llm_elapsed = ...
```

這意味著我們不需要修改任何子模組（audio、transcribe、postprocess），只需要在 main.py 中加入保存邏輯。

### WAV 保存方案

音訊資料格式為 16kHz、mono、float32 的 numpy array。保存為 WAV 有兩個主要選項：

| 方案 | 優點 | 缺點 |
|------|------|------|
| `scipy.io.wavfile.write` | 零額外依賴（scipy 通常已安裝）、API 簡單 | 不支援 metadata |
| `soundfile` | 功能更豐富、支援多種格式 | 需新增依賴 |

**建議使用 `scipy.io.wavfile`**，因為我們只需要最基本的 WAV 寫入，不需要額外功能。scipy 在安裝 numpy/torch 生態系時通常已經存在。如果 scipy 不在依賴中，也可以考慮直接用 Python 標準庫的 `wave` 模組（需要先將 float32 轉為 int16）。

### 檔案命名與目錄結構

建議採用時間戳命名，每次錄音產生一對檔案：

```
debug/
├── 20260214_153042_audio.wav       # 原始音訊
├── 20260214_153042_result.json     # 辨識結果和 metadata
├── 20260214_153215_audio.wav
├── 20260214_153215_result.json
└── ...
```

時間戳格式 `YYYYMMDD_HHMMSS` 既能保證唯一性（同一秒內不太可能有兩次錄音），又方便人眼閱讀和排序。使用扁平結構（不分子目錄）更容易瀏覽和管理。

### JSON Metadata 結構

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

這個結構包含了後續建立測試案例所需的所有資訊：
- `audio_file`：對應的音訊檔名，方便程式載入
- `whisper_text`：Whisper 原始輸出，用於診斷是 Whisper 還是 LLM 的問題
- `processed_text`：最終輸出，用於比對預期結果
- 延遲資訊：用於效能分析

### CLI 參數設計

目前 `main()` 函式不接受任何參數，`__main__.py` 也沒有 argument parsing。需要新增 `argparse` 支援：

```
uv run typeness --debug
```

建議使用 Python 標準庫的 `argparse`，保持簡單。`--debug` 為 boolean flag，預設 `False`。

### 實作影響範圍

| 檔案 | 修改內容 |
|------|----------|
| `src/typeness/main.py` | 新增 `argparse`、debug 保存邏輯 |
| `src/typeness/__main__.py` | 傳遞 CLI args 到 `main()` |
| `.gitignore` | 新增 `debug/` |

不需要修改 audio.py、transcribe.py、postprocess.py、hotkey.py、clipboard.py。

## 解決方案設計

### 核心實作方向

在 `main.py` 中新增一個 `_save_debug_capture()` 輔助函式，在每次成功處理完成後呼叫。這個函式負責：

1. 確保 `debug/` 目錄存在（`os.makedirs` with `exist_ok=True`）
2. 生成時間戳作為檔名前綴
3. 用 `scipy.io.wavfile.write()` 保存音訊為 WAV
4. 用 `json.dump()` 保存 metadata 為 JSON

保存邏輯放在 `paste_text()` 之後、結果顯示之前，確保不影響主要功能的延遲體驗。保存失敗時只 print 警告，不中斷主流程。

### 後續測試案例的使用流程

```
1. 使用者開啟 debug 模式：uv run typeness --debug
2. 正常使用語音輸入，所有錄音自動保存到 debug/
3. 發現辨識有問題時，到 debug/ 找到對應的檔案
4. 手動複製有問題的案例到 tests/fixtures/（未來規劃）
5. 寫測試案例：載入 WAV → 跑 Whisper → 比對預期 → 跑 LLM → 比對預期
```

## 建議與下一步

基於分析結果，這個功能的實作範圍很小、風險很低，且能立即為後續的品質改善工作提供基礎。

**建議的實作步驟：**

1. **在 `.gitignore` 加入 `debug/`**
2. **修改 `__main__.py`**：加入 `argparse`，解析 `--debug` 參數
3. **修改 `main.py`**：
   - `main()` 接收 `debug: bool` 參數
   - 新增 `_save_debug_capture()` 輔助函式
   - 在 `EVENT_STOP_RECORDING` 處理成功後呼叫保存
4. **確認 scipy 可用性**：如果不可用，改用 `wave` 標準庫模組

**不需要 PRD**：這是一個範圍明確、影響面小的開發工具功能，可以直接進入實作。

## 參考資料

- [scipy.io.wavfile.write 文件](https://docs.scipy.org/doc/scipy/reference/generated/scipy.io.wavfile.write.html)
- [Python argparse 文件](https://docs.python.org/3/library/argparse.html)
