"""Audio recording module for Typeness.

Captures microphone input via sounddevice with start/stop control.
"""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"
MIN_RECORDING_SECONDS = 0.3

_audio_stream: sd.InputStream | None = None
_audio_chunks: list[np.ndarray] = []


def _audio_callback(indata: np.ndarray, frames: int, time_info, status) -> None:
    if status:
        print(f"  [audio warning] {status}")
    _audio_chunks.append(indata.copy())


def record_audio_start() -> None:
    """Start recording audio from the microphone."""
    global _audio_stream
    _audio_chunks.clear()
    _audio_stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=_audio_callback,
    )
    _audio_stream.start()
    print("Recording...")


def stop_stream() -> None:
    """Stop and close the audio stream if active (for cleanup on shutdown)."""
    global _audio_stream
    if _audio_stream is not None:
        _audio_stream.stop()
        _audio_stream.close()
        _audio_stream = None


def record_audio_stop() -> np.ndarray:
    """Stop recording and return the audio as a 1D float32 numpy array."""
    global _audio_stream
    if _audio_stream is not None:
        _audio_stream.stop()
        _audio_stream.close()
        _audio_stream = None

    if not _audio_chunks:
        return np.array([], dtype=np.float32)

    audio = np.concatenate(_audio_chunks, axis=0).flatten()
    duration = len(audio) / SAMPLE_RATE
    print(f"Recorded {duration:.1f}s of audio")
    return audio
