# Typeness 語音輸入工具技術可行性研究

## 1. 執行摘要

本研究針對一款名為「Typeness」的語音輸入工具進行技術可行性分析。這款工具的核心概念是：使用者按下快捷鍵開始錄音、說話後再按一次結束，系統將語音轉為文字，自動移除贅字與停頓，並進行格式化（如列表、段落分割），最後透過剪貼簿自動貼上到任何應用程式。

經過全面研究後，我們確認這個專案在技術上完全可行，且所有核心元件都有成熟的開源方案可用。關鍵發現如下：

- **語音辨識**：faster-whisper + large-v3-turbo 是最佳選擇，消費級 GPU 上 5 秒語音約 0.5-1 秒即可完成辨識
- **文字後處理**：混合架構（規則引擎 + Qwen3-1.7B 本地 LLM）可在 0.1-0.5 秒內完成清理與格式化
- **系統整合**：Python 生態有完整的全域快捷鍵、剪貼簿操作、系統匣等函式庫，Windows 上尤其成熟
- **已有多個高度相似的開源專案**（whisper-writer、simple-whisper-stt）可作為參考

---

## 2. 背景與脈絡

### 2.1 專案目標

建立一個常駐背景的語音輸入工具，讓使用者在任何應用程式中都能透過快捷鍵快速將語音轉為結構化文字。與一般語音輸入法的差異在於，Typeness 會自動進行「語音到書面語」的轉換——移除口語中的贅字（嗯、那個、就是）、消除停頓造成的空白，並根據語意自動格式化（如將口述的列舉轉為清單格式）。

### 2.2 核心需求

- **全本地端運行**：Whisper 語音辨識與 LLM 文字處理都在本地 GPU 上執行，無需網路
- **快捷鍵觸發**：左 Alt 鍵切換錄音狀態
- **自動貼上**：辨識完成後透過剪貼簿 + 模擬 Ctrl+V 貼上到當前焦點視窗
- **目標平台**：以 Windows 為主，但希望了解跨平台的可行性與差異
- **低延遲**：從使用者停止錄音到文字出現，希望在 1-3 秒內完成

---

## 3. 研究問題與發現過程

初始研究聚焦在四個核心問題：

1. **語音辨識引擎的選擇與部署方式**——哪個 Whisper 變體最適合即時語音輸入？繁體中文品質如何？
2. **系統層級的互動機制**——如何監聽全域快捷鍵、操作剪貼簿、模擬鍵盤輸入？跨平台差異有多大？
3. **文字後處理的技術方案**——用 LLM 還是規則引擎？本地 LLM 的延遲和資源需求是否可接受？
4. **專案結構與架構設計**——事件驅動還是 Pipeline？執行緒如何分配？如何打包發布？

在與使用者確認需求後，我們釐清了幾個關鍵決策：輸出方式為「自動剪貼簿貼上」、模型全部在本地端運行、不需要取得視窗狀態（只需要快捷鍵觸發即可）。這大幅簡化了系統層級互動的複雜度。

---

## 4. 技術分析

### 4.1 語音辨識：faster-whisper + large-v3-turbo

經過對 OpenAI Whisper、faster-whisper、whisper.cpp、insanely-fast-whisper 等方案的比較，**faster-whisper** 是最佳選擇。它基於 CTranslate2 引擎，比原版 Whisper 快 4 倍且記憶體消耗更低，Python 生態整合也最完善。

模型方面，**large-v3-turbo** 是關鍵選擇。它將解碼器從 32 層減至 4 層，速度比 large-v3 快 6 倍，而準確度僅低 1-2%。在消費級 GPU 上的表現：

| 模型 | VRAM (FP16) | VRAM (INT8) | 5 秒語音辨識延遲 |
|------|-------------|-------------|-----------------|
| large-v3-turbo | ~3.5 GB | ~2.5 GB | 0.3-0.8 秒 |
| large-v3 | ~5 GB | ~3.1 GB | 1.5-3 秒 |
| medium | ~3 GB | ~2 GB | 0.5-1.5 秒 |

#### 繁體中文支援策略

Whisper 只有 `zh` 語言標記，不區分繁簡體。解決方式是雙重保障：

1. **initial_prompt 引導**：提供繁體中文的 prompt（如「以下是繁體中文的語音轉錄稿」），Whisper 會傾向維持相同的文字風格
2. **OpenCC 後處理**：使用 `opencc.OpenCC('s2twp')` 做簡體到繁體（台灣用詞）的轉換，作為保險

此外，HuggingFace 上有 [JacobLinCool 針對 zh-TW 微調的 large-v3-turbo 模型](https://huggingface.co/JacobLinCool/whisper-large-v3-turbo-common_voice_19_0-zh-TW)，如果對繁體中文準確度要求極高，可以考慮使用。

#### 錄音方式

採用 **Push-to-Talk（按鍵說話）** 模式。使用者按下快捷鍵開始錄音，再按一次結束，音訊直接送入 Whisper。這是延遲最低的方式，不需要串流轉寫的複雜架構。搭配 Silero VAD（faster-whisper 內建）可自動裁剪前後靜音。

### 4.2 系統整合：快捷鍵、剪貼簿與系統匣

#### 全域快捷鍵

| 函式庫 | Windows | macOS | Linux | 區分左右 Alt |
|--------|---------|-------|-------|-------------|
| keyboard | 完整支援 | 實驗性 | 需 root | 支援 (`left alt`) |
| pynput | 完整支援 | 需輔助使用權限 | 支援 | 支援 (`Key.alt_l`) |

**建議**：使用 **pynput**。雖然 `keyboard` 在 Windows 上語法更簡潔，但 pynput 的跨平台能力更好，且與 pystray 同作者開發，整合更順暢。

重要注意事項：pynput 的回呼函式在作業系統執行緒中直接執行，不可在回呼中做長時間操作，應用 `queue.Queue` 分派事件到工作執行緒。

#### 剪貼簿 + 自動貼上

推薦的流程：

```python
# 1. 備份原始剪貼簿內容
original = pyperclip.paste()
# 2. 設定新內容
pyperclip.copy(transcribed_text)
time.sleep(0.05)  # 確保剪貼簿就緒
# 3. 模擬 Ctrl+V
pyautogui.hotkey('ctrl', 'v')
time.sleep(0.1)
# 4. 還原原始剪貼簿
pyperclip.copy(original)
```

注意事項：pyperclip 只能處理純文字，如果使用者剪貼簿中有圖片或富文字，簡單備份無法完整保留。若需要完整保留，Windows 上可用 `win32clipboard` 逐格式備份。

#### 系統匣

使用 **pystray** + **Pillow** 建立系統匣圖示。pystray 的 `run()` 是阻塞呼叫，必須在主執行緒執行。錄音狀態可透過動態更換圖示顏色（綠色=待命、紅色=錄音中）來顯示。

#### 音訊錄製

使用 **sounddevice**，以 16kHz 單聲道 float32 格式錄製（Whisper 的原生輸入格式），避免額外的重取樣。sounddevice 的 callback 模式自動管理音訊緩衝。

### 4.3 文字後處理：混合架構

經過分析，最佳方案是 **規則引擎 + 本地 LLM** 的混合架構。

#### 第一階段：規則引擎（零延遲、零風險）

處理確定性高的清理任務：

- **填充詞移除**：以正則表達式匹配中文常見贅字（嗯、啊、那個、就是、然後、對對對）
- **重複字元清理**：移除連續重複超過 3 次的字元
- **多餘空白清理**：合併連續空白為單一空白
- **基本標點修正**：移除連續重複的標點

#### 第二階段：LLM 格式化（0.1-0.5 秒）

處理需要語意理解的任務：

- **列表格式化**：將口述的列舉轉為編號列表
- **段落分割**：根據主題邊界插入段落分隔
- **進階標點修正**：需要語意判斷的標點位置

#### 本地 LLM 選擇：Qwen3-1.7B

| 模型 | VRAM (Q4_K_M) | 處理速度 (GPU) | 中文能力 |
|------|---------------|---------------|---------|
| Qwen3-0.6B | ~0.5 GB | 100+ tok/s | 基本 |
| **Qwen3-1.7B** | **~1.2 GB** | **100+ tok/s** | **優秀** |
| Qwen3-4B | ~2.5 GB | 50+ tok/s | 非常好 |

Qwen3-1.7B 的性能等同 Qwen2.5-3B，在中文處理上有原生優勢。Q4 量化後僅需 ~1.2 GB VRAM，可與 Whisper 共存在同一張 GPU 上。建議透過 **Ollama** 或 **llama.cpp server** 作為常駐服務運行，避免每次推理都載入模型的 5-30 秒延遲。

Whisper 和 LLM 不需要同時推理（語音辨識完成後才做文字清理），所以實際上是交替使用 GPU，VRAM 需求不會疊加。

#### LLM 提示詞設計

```
/no_think
清理以下語音轉文字的結果。

要求：
- 修正標點符號
- 將列舉內容格式化為列表
- 在適當位置分段
- 禁止改變任何實質內容或用詞
- 禁止添加原文沒有的內容

文字：{text}
```

關鍵技巧：使用 Qwen3 的 `/no_think` 指令關閉思考模式以減少延遲、將 temperature 設為 0 以減少創造性輸出、在提示中反覆強調不可改變原意。

### 4.4 Windows 專用 vs 跨平台差異

整體而言，Windows 專用開發**明顯更簡單**。以下是主要差異：

| 面向 | Windows 專用 | 跨平台 |
|------|-------------|--------|
| 快捷鍵 | `keyboard` 即可，無需權限 | 需用 `pynput`；macOS 需輔助使用權限；Linux 需 root |
| 剪貼簿備份 | `win32clipboard` 可完整備份所有格式 | `pyperclip` 只能備份純文字 |
| 模擬按鍵 | `pyautogui` 或 `keyboard` 都穩定 | macOS 需輔助使用權限 |
| 系統匣 | pystray 最穩定 | Linux 依賴桌面環境支援 |
| GPU/CUDA | 最穩定的 CUDA 支援 | macOS 無 CUDA（需用 Metal/Core ML） |

**建議**：先以 Windows 為目標開發，使用跨平台函式庫（pynput、pyperclip、pystray、sounddevice），未來要擴展到其他平台時，主要只需處理權限和 GPU 後端的差異。

---

## 5. 架構設計

### 5.1 整體架構：事件驅動 + Pipeline 混合

外層採用事件驅動（快捷鍵觸發、系統匣操作），內層採用線性 Pipeline（錄音 → 轉錄 → 處理 → 貼上）：

```
使用者按快捷鍵 ──→ 開始錄音
使用者再按快捷鍵 ──→ 停止錄音
    │
    ▼
Pipeline:
    錄音資料 → Whisper 辨識 → 規則清理 → LLM 格式化 → 剪貼簿貼上
```

### 5.2 執行緒設計

```
Main Thread
├── pystray 系統匣（阻塞，必須在主執行緒）
│
├── pynput Listener Thread（daemon thread）
│   └── 透過 queue.Queue 發送事件
│
├── Event Processor Thread
│   └── 從 Queue 取出事件，協調 Pipeline
│
└── Worker Thread（daemon thread）
    ├── sounddevice 錄音（自有 callback thread）
    ├── Whisper 推理（GPU 密集）
    ├── LLM 推理（GPU 密集）
    └── 剪貼簿操作 + 模擬按鍵
```

### 5.3 推薦專案結構

```
typeness/
├── pyproject.toml
├── README.md
├── config/
│   └── default.yaml
├── src/
│   └── typeness/
│       ├── __init__.py
│       ├── __main__.py          # Entry point
│       ├── app.py               # Application orchestrator / event bus
│       ├── audio/
│       │   ├── __init__.py
│       │   └── recorder.py      # sounddevice recording
│       ├── transcription/
│       │   ├── __init__.py
│       │   └── whisper.py       # faster-whisper integration
│       ├── processing/
│       │   ├── __init__.py
│       │   ├── rules.py         # Rule-based text cleanup
│       │   └── llm.py           # LLM formatting (Ollama/llama.cpp)
│       ├── output/
│       │   ├── __init__.py
│       │   └── clipboard.py     # Clipboard + auto-paste
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── tray.py          # System tray icon
│       │   └── hotkey.py        # Global hotkey listener
│       └── config.py            # Configuration loader
├── tests/
│   ├── test_recorder.py
│   ├── test_rules.py
│   └── test_pipeline.py
├── scripts/
│   └── install_models.py        # Model download helper
└── assets/
    └── icon.ico
```

### 5.4 依賴管理與開發工具

- **套件管理**：**uv**（速度比 Poetry/pip 快 10-100 倍，可同時管理 Python 版本）
- **Python 版本**：**3.11**（CUDA 相容性最穩定）
- **Linter/Formatter**：Ruff
- **打包**：先用 PyInstaller 快速迭代，穩定後考慮 Nuitka
- **模型管理**：首次執行時下載，快取在 `%APPDATA%/typeness/models/`

---

## 6. 硬體需求與延遲預期

### 6.1 最低硬體需求

| 元件 | 需求 |
|------|------|
| GPU | 8 GB VRAM（如 RTX 4060） |
| 系統 RAM | 16 GB |
| 儲存空間 | ~5 GB（Whisper 模型 + LLM 模型） |

### 6.2 建議硬體

| 元件 | 建議 |
|------|------|
| GPU | 12 GB VRAM（如 RTX 3060 12GB / RTX 4070） |
| 系統 RAM | 32 GB |

### 6.3 延遲預期

以 RTX 3060 12GB 為例：

| 階段 | 延遲 |
|------|------|
| Whisper 辨識（5 秒語音） | 0.3-0.8 秒 |
| 規則處理 | < 1 毫秒 |
| LLM 格式化（Qwen3-1.7B） | 0.1-0.3 秒 |
| 剪貼簿 + 貼上 | < 0.1 秒 |
| **總延遲** | **~0.5-1.5 秒** |

---

## 7. 參考專案

以下開源專案的技術棧與 Typeness 高度相似，值得參考：

### [whisper-writer](https://github.com/savbell/whisper-writer)
最接近的完整參考。使用 faster-whisper 本地轉錄，有設定視窗 UI（PyQt5），支援連續錄音模式，結果處理放在獨立的 result_thread。架構設計值得學習。

### [simple-whisper-stt](https://github.com/ivkatic/simple-whisper-stt)
技術棧幾乎完全一致（faster-whisper + sounddevice + keyboard + pyperclip + pyautogui + pystray）。Push-to-talk 模式，GPU/CPU 自動偵測。雖然是單檔案架構，但作為功能原型非常好。

### [scorchsoft-quick-whisper](https://github.com/andrew-scorchsoft/scorchsoft-quick-whisper)
LLM 後處理的參考。有透過 LLM API 做 copy-editing 的功能，還有 PyInstaller .spec 檔和多語言國際化支援。

### [whisper-key-local](https://github.com/PinW/whisper-key-local)
使用 Silero VAD 過濾靜音以避免 Whisper 幻覺。快捷鍵用 global-hotkeys + pywin32。

---

## 8. 技術棧總覽

| 功能 | 推薦函式庫 | 備選 |
|------|-----------|------|
| 語音辨識 | faster-whisper (large-v3-turbo) | whisper.cpp |
| 繁中保障 | OpenCC (s2twp) | 微調模型 |
| 音訊錄製 | sounddevice | PyAudio |
| 全域快捷鍵 | pynput | keyboard |
| 系統匣 | pystray + Pillow | — |
| 剪貼簿 | pyperclip | win32clipboard |
| 模擬按鍵 | pyautogui | pynput Controller |
| 規則處理 | re (正則表達式) | — |
| LLM 格式化 | Qwen3-1.7B via Ollama | llama.cpp server |
| 設定管理 | PyYAML | — |
| 套件管理 | uv | Poetry |
| 打包 | PyInstaller → Nuitka | cx_Freeze |

---

## 9. 下一步行動計畫

### 立即可做

1. **建立專案骨架**：使用 uv 初始化專案，建立目錄結構
2. **快速原型驗證**：參考 simple-whisper-stt，用單一 Python 檔案驗證核心流程（錄音 → Whisper → 貼上）
3. **安裝 faster-whisper**：先用 small 或 medium 模型快速驗證繁體中文品質

### 中期目標

4. **加入規則引擎**：實作填充詞移除和基本格式化
5. **整合 LLM**：設定 Ollama + Qwen3-1.7B，實作格式化 Pipeline
6. **系統匣 UI**：加入 pystray 系統匣和狀態顯示

### 後期目標

7. **打包發布**：使用 PyInstaller 打包為獨立 exe
8. **設定介面**：提供使用者可調整的設定（模型選擇、快捷鍵、格式化規則）
9. **開機自動啟動**：整合 Windows Registry 自動啟動

### 是否需要 PRD？

這個專案的需求相對明確，功能集中，建議可以直接撰寫一份 PRD 來定義：
- 詳細的使用者流程（按快捷鍵 → 錄音 → 結果出現的完整互動）
- 格式化規則的具體定義（哪些贅字要移除、列表格式的辨識規則）
- 設定項目的範圍（哪些是使用者可調整的）

---

## 10. 參考資料

### 核心技術文件
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper)
- [Whisper large-v3-turbo (HuggingFace)](https://huggingface.co/openai/whisper-large-v3-turbo)
- [Qwen3 官方部落格](https://qwenlm.github.io/blog/qwen3/)
- [pynput 文件](https://pynput.readthedocs.io/en/latest/keyboard.html)
- [pystray 文件](https://pystray.readthedocs.io/en/latest/usage.html)
- [sounddevice 文件](https://python-sounddevice.readthedocs.io/)
- [uv 文件](https://docs.astral.sh/uv/)

### 參考專案
- [whisper-writer](https://github.com/savbell/whisper-writer) — 最接近的完整參考
- [simple-whisper-stt](https://github.com/ivkatic/simple-whisper-stt) — 技術棧一致的精簡參考
- [scorchsoft-quick-whisper](https://github.com/andrew-scorchsoft/scorchsoft-quick-whisper) — LLM 後處理參考
- [whisper-key-local](https://github.com/PinW/whisper-key-local) — VAD + 快捷鍵參考
- [OpenWhispr](https://github.com/OpenWhispr/openwhispr) — 模型管理參考

### 延伸閱讀
- [Modal: Choosing between Whisper variants](https://modal.com/blog/choosing-whisper-variants)
- [Modal: Top Open Source STT Models 2025](https://modal.com/blog/open-source-stt)
- [JacobLinCool zh-TW 微調模型](https://huggingface.co/JacobLinCool/whisper-large-v3-turbo-common_voice_19_0-zh-TW)
- [2026 Showdown: PyInstaller vs cx_Freeze vs Nuitka](https://ahmedsyntax.com/2026-comparison-pyinstaller-vs-cx-freeze-vs-nui/)
- [Poetry vs UV 2025](https://medium.com/@hitorunajp/poetry-vs-uv-which-python-package-manager-should-you-use-in-2025-4212cb5e0a14)
