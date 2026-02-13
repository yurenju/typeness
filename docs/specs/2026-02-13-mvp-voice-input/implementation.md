# 實作計畫

## 參考文件

**PRD 文件路徑：** `docs/specs/2026-02-13-mvp-voice-input/prd.md`
**研究文件路徑：** `docs/research/2026-02-12-voice-input-tool-feasibility.md`

## 任務概要

- [x] 使用 uv 初始化專案並安裝依賴
- [x] 實作錄音控制模組
- [x] 實作 Whisper 語音辨識模組
- [ ] 實作 LLM 文字後處理模組
- [ ] 整合主程式與終端機互動迴圈
- [ ] 執行驗收測試
- [ ] 更新專案文件

## 任務細節

### 使用 uv 初始化專案並安裝依賴

**實作要點**
- 在專案根目錄執行 `uv init` 初始化 Python 專案
- 編輯 `pyproject.toml`，設定 `requires-python = ">=3.10,<3.13"`
- 在 `pyproject.toml` 的 `[project] dependencies` 中宣告非 PyTorch 依賴：`transformers`、`accelerate`、`sounddevice`、`numpy`
- 建立虛擬環境：`uv venv .venv --python 3.12`
- 安裝專案依賴：`uv pip install -e .`
- 安裝 PyTorch（RTX 5090 Blackwell 相容，需單獨指定 index-url）：`uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130`
- 驗證 PyTorch 能正確偵測 CUDA GPU

**相關檔案**
- `pyproject.toml` - 專案設定與依賴宣告
- `.python-version` - Python 版本鎖定

**完成檢查**
- 執行 `uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` 確認輸出 `True` 和 GPU 名稱
- 執行 `uv run python -c "import sounddevice; print(sounddevice.query_devices())"` 確認可列出音訊裝置

**實作備註**
[方向調整] 原計畫將 PyTorch 排除在 pyproject.toml 之外，僅透過手動 `uv pip install --index-url` 安裝。但 `uv run` 會觸發依賴解析，將 cu130 版 torch 替換為 CPU 版。改用 `[tool.uv.index]` + `[tool.uv.sources]` 在 pyproject.toml 中指定 PyTorch 從 cu130 index 安裝，確保 `uv sync` 和 `uv run` 都能取得正確版本。

[後續依賴] PyTorch 已透過 `tool.uv.sources` 鎖定 cu130 index，後續若需新增 PyTorch 相關套件（如 torchvision），也需在 `[tool.uv.sources]` 中指定相同 index。

---

### 實作錄音控制模組

**實作要點**
- 在 `typeness.py`（單一腳本）中建立錄音功能
- 使用 `sounddevice.InputStream` 搭配 callback 模式錄音
- 錄音格式：16kHz、單聲道、float32（Whisper 原生輸入格式）
- 使用 `threading.Event` 控制錄音的開始與結束
- 錄音期間將音訊資料存入 `list`，結束後用 `numpy.concatenate` 合併為完整陣列
- Enter 鍵按下後切換錄音狀態（使用 `input()` 阻塞等待）

**相關檔案**
- `typeness.py` - 主要腳本（所有程式碼在此單一檔案中）

**完成檢查**
- 執行腳本，按 Enter 開始錄音，對麥克風說話 3 秒，再按 Enter 結束，程式能正常停止錄音並印出錄音長度（秒數）

**實作備註**
照預期開發

---

### 實作 Whisper 語音辨識模組

**實作要點**
- 使用 `transformers` 的 `AutoModelForSpeechSeq2Seq` 和 `AutoProcessor` 載入 `openai/whisper-large-v3-turbo`
- 模型載入時使用 `torch_dtype=torch.float16` 並搬移到 CUDA
- 使用 `transformers.pipeline("automatic-speech-recognition", ...)` 建立推理管線
- 設定 `generate_kwargs`：`language="zh"`, `task="transcribe"`
- 使用 `initial_prompt`（如「以下是繁體中文的語音內容。」）引導輸出繁體中文
- 首次執行時模型會自動從 HuggingFace 下載，不需額外處理
- 印出 Whisper 原始辨識結果和辨識耗時

**相關檔案**
- `typeness.py` - 在此檔案中新增 Whisper 辨識函式

**完成檢查**
- 錄一段 5 秒的繁體中文語音，確認能產出辨識結果且耗時在合理範圍內（< 3 秒）
- 確認辨識結果為中文文字（非亂碼或空白）

**實作備註**
[技術障礙] transformers v5 中 `torch_dtype` 參數已 deprecated，需改用 `dtype`。另外 `initial_prompt` 不能直接傳入 `generate_kwargs`，需透過 `processor.get_prompt_ids()` 編碼為 `prompt_ids`，且必須 `.to(device)` 搬到 CUDA 上。

---

### 實作 LLM 文字後處理模組

**實作要點**
- 使用 `transformers` 的 `AutoModelForCausalLM` 和 `AutoTokenizer` 載入 Qwen3-1.7B（`Qwen/Qwen3-1.7B`）
- 模型載入使用 `torch_dtype=torch.float16`，搬移到 CUDA
- 設計系統提示詞，涵蓋：移除贅字、修正標點、列表格式化、段落分隔
- 提示詞中加入 `/no_think` 指令（Qwen3 特性），關閉思考模式以降低延遲
- 設定推理參數：`temperature=0`（避免創造性輸出）、`max_new_tokens` 設為輸入長度的 2 倍
- 解析 LLM 輸出，提取處理後的文字（去除 prompt 和 thinking 部分）
- 印出 LLM 處理後結果和處理耗時

**相關檔案**
- `typeness.py` - 在此檔案中新增 LLM 處理函式

**完成檢查**
- 用一段含贅字的測試文字（如「嗯那個就是說我想要買三個東西第一個是蘋果第二個是香蕉第三個是橘子」）送入 LLM，確認輸出移除贅字且格式化為列表
- 確認 LLM 處理耗時在合理範圍內（< 2 秒）

**實作備註**
<!-- 執行過程中填寫重要的技術決策、障礙和需要傳遞的上下文 -->

---

### 整合主程式與終端機互動迴圈

**實作要點**
- 建立主迴圈：等待 Enter → 錄音 → 等待 Enter → 停止錄音 → Whisper 辨識 → LLM 處理 → 顯示結果 → 回到等待
- 程式啟動時先載入 Whisper 和 LLM 模型（顯示載入進度）
- 顯示格式化的輸出結果，包含：
  - Whisper 原始辨識結果
  - LLM 處理後結果
  - 處理時間統計（錄音時長、Whisper 辨識時間、LLM 處理時間、總延遲）
- 使用 `time.time()` 測量各階段耗時
- 支援 Ctrl+C 優雅退出（`KeyboardInterrupt` 處理）
- 在 `if __name__ == "__main__"` 中呼叫主函式
- 確保主程式可透過 `uv run python typeness.py` 直接執行

**相關檔案**
- `typeness.py` - 整合所有模組，建立主程式進入點

**完成檢查**
- 執行 `uv run python typeness.py`，完成一次完整的錄音-辨識-處理流程，確認終端機顯示三個區塊（原始結果、處理後結果、時間統計）
- 完成一次流程後，程式回到等待狀態，能繼續下一次錄音
- 按 Ctrl+C 能正常結束程式

**實作備註**
<!-- 執行過程中填寫重要的技術決策、障礙和需要傳遞的上下文 -->

---

### 執行驗收測試

**實作要點**
- 使用 AI 讀取 acceptance.feature 檔案
- 透過指令或手動操作執行每個場景
- 驗證所有場景通過並記錄結果
- 如發現問題，記錄詳細的錯誤資訊和重現步驟

**相關檔案**
- `docs/specs/2026-02-13-mvp-voice-input/acceptance.feature` - Gherkin 格式的驗收測試場景
- `docs/specs/2026-02-13-mvp-voice-input/acceptance-report.md` - 詳細的驗收測試執行報告（執行時生成）

**實作備註**
<!-- 執行過程中填寫 -->

---

### 更新專案文件

**實作要點**
- 建立 README.md，包含：
  - 專案簡介（一句話描述 Typeness MVP）
  - 前提條件（NVIDIA GPU、CUDA、Python 3.12）
  - 安裝步驟（uv 初始化、PyTorch 安裝、依賴安裝）
  - 使用方式（執行指令、操作說明）
- 建立或更新 CLAUDE.md，記錄：
  - 專案架構（單一檔案 MVP）
  - 技術選型（PyTorch + transformers 統一推理）
  - 模型資訊（Whisper large-v3-turbo、Qwen3-1.7B）
  - 開發環境設定注意事項（cu130 wheel）

**相關檔案**
- `README.md` - 專案主要說明文件
- `CLAUDE.md` - AI 助手的專案指引文件

**實作備註**
<!-- 執行過程中填寫 -->

---

## 實作參考資訊

### 來自研究文件的技術洞察
> **文件路徑：** `docs/research/2026-02-12-voice-input-tool-feasibility.md`

- **Whisper 繁體中文引導策略**：使用 `initial_prompt`（如「以下是繁體中文的語音轉錄稿」）引導 Whisper 輸出繁體中文。HuggingFace 上也有 JacobLinCool 針對 zh-TW 微調的 large-v3-turbo 模型可作為備選
- **LLM Prompt 設計**：使用 Qwen3 的 `/no_think` 指令關閉思考模式以減少延遲、將 temperature 設為 0 以減少創造性輸出、在提示中反覆強調不可改變原意。研究文件中有完整的 prompt 範例可參考
- **音訊格式**：使用 sounddevice 以 16kHz 單聲道 float32 格式錄製（Whisper 的原生輸入格式），避免額外的重取樣
- **VRAM 預估**：Whisper large-v3-turbo FP16 ~3.5 GB + Qwen3-1.7B FP16 ~3.4 GB + PyTorch overhead ~2 GB ≈ 9 GB，在 RTX 5090 24GB 上完全沒有問題
- **延遲預期**：Whisper 辨識 5 秒語音約 0.3-0.8 秒、LLM 格式化約 0.1-0.5 秒，總延遲目標 < 3 秒

### 來自 PRD 的實作細節
> **文件路徑：** `docs/specs/2026-02-13-mvp-voice-input/prd.md`

- **統一 PyTorch 推理引擎**：Whisper 和 LLM 都透過 PyTorch + transformers 執行，不使用 CTranslate2 或 llama.cpp，避免多引擎相容性問題
- **RTX 5090 Blackwell 相容性**：必須使用 PyTorch cu130 wheel，透過 `--index-url https://download.pytorch.org/whl/cu130` 安裝
- **LLM 處理範圍**：移除贅字、移除重複、修正標點、列表格式化、段落分隔——全部由 LLM 一次處理（不使用規則引擎）
- **MVP 為單一 Python 檔案**：所有功能在一個 `typeness.py` 中實作

### 來自參考專案的技術實踐
> **專案路徑：** `C:\Users\yuren\Documents\30-resources\src\comfyui-related\comfyui-civitai-alchemist`

- **Windows 上的 PyTorch cu130 安裝方式**：
  ```
  uv venv .venv --python 3.12
  uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130
  ```
- **Blackwell 優化環境變數**（可選，用於改善效能）：
  ```
  set CUDA_MODULE_LOADING=lazy
  set TORCH_CUDA_ARCH_LIST=12.0
  set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
  ```
- **pyproject.toml 最小依賴原則**：只在 pyproject.toml 中列出非 PyTorch 的依賴，PyTorch 透過 `--index-url` 單獨安裝以確保拿到正確的 CUDA 版本

### 關鍵技術決策
- **PyTorch 安裝與 pyproject.toml 分離**：由於 PyTorch 需要指定特定的 index-url（cu130），不適合放在 pyproject.toml 的 dependencies 中，改為手動 `uv pip install` 安裝
- **Whisper 使用 transformers pipeline**：而非 faster-whisper（CTranslate2），因為 CTranslate2 對 Blackwell 架構的支援不確定
- **LLM 使用 transformers 原生載入**：而非 llama.cpp 或 Ollama，統一推理引擎減少相容性風險
- **模型精度使用 FP16**：RTX 5090 有充足的 VRAM（24GB），FP16 比 INT8/INT4 量化品質更好且 Blackwell 原生支援
- **不使用 bitsandbytes 量化**：MVP 階段 VRAM 充足，不需量化，避免引入額外依賴和潛在的相容性問題
