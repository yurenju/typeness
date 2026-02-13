import threading
import numpy as np
import sounddevice as sd


SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"


def record_audio() -> np.ndarray:
    """Record audio from microphone until Enter is pressed.

    Uses sounddevice.InputStream with callback mode.
    Returns the recorded audio as a 1D float32 numpy array.
    """
    chunks: list[np.ndarray] = []
    stop_event = threading.Event()

    def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            print(f"  [audio warning] {status}")
        chunks.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=callback,
    )

    print("Recording... (press Enter to stop)")
    stream.start()

    input()
    stop_event.set()

    stream.stop()
    stream.close()

    if not chunks:
        return np.array([], dtype=np.float32)

    audio = np.concatenate(chunks, axis=0).flatten()
    duration = len(audio) / SAMPLE_RATE
    print(f"Recorded {duration:.1f}s of audio")
    return audio


if __name__ == "__main__":
    print("=== Typeness Recording Test ===")
    print("Press Enter to start recording...")
    input()

    audio = record_audio()
    if len(audio) > 0:
        print(f"Audio shape: {audio.shape}, dtype: {audio.dtype}")
    else:
        print("No audio recorded.")
