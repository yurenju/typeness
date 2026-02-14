# Typeness - Project Guide

## Architecture

Source code lives in `src/typeness/` (src layout):

- `src/typeness/main.py` — event-driven loop (queue.Queue), orchestrates all modules
- `src/typeness/audio.py` — microphone recording via sounddevice (start/stop split)
- `src/typeness/transcribe.py` — Whisper model loading, speech-to-text, CJK text normalization
- `src/typeness/postprocess.py` — Qwen3 LLM loading, filler-word removal, punctuation, list formatting
- `src/typeness/hotkey.py` — global keyboard listener: Shift+Win+A toggle via pynput, injected-event filtering, busy-state lock
- `src/typeness/clipboard.py` — clipboard and auto-paste: pyperclip for clipboard write, pynput Controller for Ctrl+V simulation

## Tech Stack

- **Runtime**: Python 3.12, managed by uv
- **Inference engine**: PyTorch + transformers (unified for both models)
- **Speech recognition**: Whisper large-v3-turbo (`openai/whisper-large-v3-turbo`), FP16
- **Text post-processing**: Qwen3-1.7B (`Qwen/Qwen3-1.7B`), FP16
- **Audio capture**: sounddevice (16kHz, mono, float32)
- **Global hotkey**: pynput (keyboard Listener + Controller)
- **Clipboard**: pyperclip

## Key Technical Notes

### PyTorch CUDA 13.0 (Blackwell)

PyTorch cu130 wheels are configured via `[tool.uv.sources]` in `pyproject.toml`. If adding new PyTorch ecosystem packages (e.g. torchvision), add them to `[tool.uv.sources]` with the same `pytorch-cu130` index.

### Whisper (transformers v5)

- Use `dtype=` instead of deprecated `torch_dtype=` in `from_pretrained()`
- `initial_prompt` must go through `processor.get_prompt_ids()` and be passed as `prompt_ids` in `generate_kwargs`
- `prompt_ids` tensor must be moved to the same device as the model (`.to(device)`)

### Qwen3 LLM

- `/no_think` directive goes at the start of the user message, not in the system prompt
- Even with `/no_think`, Qwen3 may produce empty `<think></think>` blocks — strip with regex after decoding
- Few-shot examples in the system prompt are critical for good filler-word removal and list formatting
- Use `do_sample=False` with `temperature=None, top_p=None` for deterministic output

## Running

```bash
uv run typeness
uv run typeness --debug   # save recordings to debug/ for diagnostics
```

## GPU Requirements

~9 GB VRAM total (Whisper ~3.5 GB + Qwen3 ~3.4 GB + overhead ~2 GB). Tested on RTX 5090 Laptop (24 GB).
