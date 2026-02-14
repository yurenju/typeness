"""Debug capture module for Typeness.

Saves audio recordings and transcription results for reproducing issues.
"""

import json
import os
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

from typeness.audio import SAMPLE_RATE

DEBUG_DIR = Path(__file__).resolve().parents[2] / "debug"


def save_capture(
    audio: np.ndarray,
    whisper_text: str,
    processed_text: str,
    rec_duration: float,
    whisper_latency: float,
    llm_latency: float,
) -> None:
    """Save audio and transcription results to the debug/ directory."""
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)

        ts = datetime.now()
        prefix = ts.strftime("%Y%m%d_%H%M%S")
        wav_name = f"{prefix}_audio.wav"
        json_name = f"{prefix}_result.json"
        wav_path = DEBUG_DIR / wav_name
        json_path = DEBUG_DIR / json_name

        # Save WAV (convert float32 -> int16 PCM)
        pcm16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm16.tobytes())

        # Save JSON metadata
        metadata = {
            "timestamp": ts.isoformat(timespec="seconds"),
            "audio_file": wav_name,
            "duration_seconds": round(rec_duration, 2),
            "whisper_text": whisper_text,
            "processed_text": processed_text,
            "whisper_latency": round(whisper_latency, 3),
            "llm_latency": round(llm_latency, 3),
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"[Debug] Saved: {json_path}")

    except Exception as exc:
        print(f"[Debug] Warning: failed to save capture — {exc}")
