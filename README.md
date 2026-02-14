# Typeness

Local voice input tool that converts speech to structured written text using Whisper and Qwen3. Works as a global voice input method — press a hotkey in any application, speak, and the processed text is automatically pasted at the cursor position.

## Prerequisites

- Windows 11
- NVIDIA GPU with CUDA support (tested on RTX 5090 Laptop, Blackwell architecture)
- CUDA drivers installed
- Python 3.12
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd typeness

# Create virtual environment and install dependencies
uv sync
```

PyTorch with CUDA 13.0 support is automatically resolved via `[tool.uv.sources]` in `pyproject.toml`.

Dependencies include `pynput` (global hotkey listener) and `pyperclip` (clipboard operations).

## Usage

```bash
uv run typeness
```

On first run, Whisper (`openai/whisper-large-v3-turbo`) and Qwen3 (`Qwen/Qwen3-1.7B`) models will be downloaded from HuggingFace automatically.

### How it works

1. Launch the program — it runs in the terminal foreground
2. Press **Shift+Win+A** to start recording (works in any application)
3. Speak into your microphone (in Traditional Chinese)
4. Press **Shift+Win+A** again to stop recording
5. The processed text is automatically pasted into the focused window
6. The terminal displays:
   - **Whisper raw**: original speech-to-text result
   - **LLM processed**: cleaned and formatted text (filler words removed, punctuation added, lists formatted)
   - **Timing stats**: recording duration, Whisper latency, LLM latency, total latency
7. Press **Ctrl+C** to exit (global keyboard hook is cleaned up)

## Architecture

Modular design with unified PyTorch + transformers inference engine. Source code lives in `src/typeness/`:

- `main.py` — event-driven loop, orchestrates all modules
- `audio.py` — microphone recording (sounddevice)
- `transcribe.py` — Whisper speech-to-text and CJK text normalization
- `postprocess.py` — Qwen3 LLM text cleanup (filler removal, punctuation, list formatting)
- `hotkey.py` — global keyboard listener (Shift+Win+A toggle via pynput)
- `clipboard.py` — clipboard write and auto-paste (pyperclip + pynput Controller)

### Models

- **Speech recognition**: Whisper large-v3-turbo (FP16, ~3.5 GB VRAM)
- **Text post-processing**: Qwen3-1.7B (FP16, ~3.4 GB VRAM)
- **Audio capture**: sounddevice (16kHz, mono, float32)
