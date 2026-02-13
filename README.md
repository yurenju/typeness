# Typeness

Local voice input tool that converts speech to structured written text using Whisper and Qwen3.

## Prerequisites

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

## Usage

```bash
uv run python typeness.py
```

On first run, Whisper (`openai/whisper-large-v3-turbo`) and Qwen3 (`Qwen/Qwen3-1.7B`) models will be downloaded from HuggingFace automatically.

### How it works

1. Press **Enter** to start recording
2. Speak into your microphone (in Traditional Chinese)
3. Press **Enter** again to stop recording
4. The tool displays:
   - **Whisper raw**: original speech-to-text result
   - **LLM processed**: cleaned and formatted text (filler words removed, punctuation added, lists formatted)
   - **Timing stats**: recording duration, Whisper latency, LLM latency, total latency
5. Press **Ctrl+C** to exit

## Architecture

Single-file MVP (`typeness.py`) with unified PyTorch + transformers inference engine:

- **Speech recognition**: Whisper large-v3-turbo (FP16, ~3.5 GB VRAM)
- **Text post-processing**: Qwen3-1.7B (FP16, ~3.4 GB VRAM)
- **Audio capture**: sounddevice (16kHz, mono, float32)
