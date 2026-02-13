import time
import threading
import numpy as np
import sounddevice as sd
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline


SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"

WHISPER_MODEL_ID = "openai/whisper-large-v3-turbo"
WHISPER_INITIAL_PROMPT = "以下是繁體中文的語音內容。"


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


def load_whisper():
    """Load Whisper model and return the ASR pipeline and processor."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if device == "cuda" else torch.float32

    print(f"Loading Whisper model ({WHISPER_MODEL_ID}) on {device}...")
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        WHISPER_MODEL_ID,
        dtype=torch_dtype,
        low_cpu_mem_usage=True,
    ).to(device)

    processor = AutoProcessor.from_pretrained(WHISPER_MODEL_ID)

    asr_pipeline = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        dtype=torch_dtype,
        device=device,
    )
    print("Whisper model loaded.")
    return asr_pipeline, processor


def transcribe(asr_pipeline, processor, audio: np.ndarray) -> str:
    """Transcribe audio using the Whisper pipeline.

    Returns the transcribed text.
    """
    device = asr_pipeline.device
    prompt_ids = processor.get_prompt_ids(WHISPER_INITIAL_PROMPT, return_tensors="pt").to(device)

    start = time.time()

    result = asr_pipeline(
        audio,
        generate_kwargs={
            "language": "zh",
            "task": "transcribe",
            "prompt_ids": prompt_ids,
        },
    )

    elapsed = time.time() - start
    text = result["text"]
    print(f"Whisper result ({elapsed:.2f}s): {text}")
    return text


if __name__ == "__main__":
    print("=== Typeness Whisper Test ===")

    asr, processor = load_whisper()

    print("\nPress Enter to start recording...")
    input()

    audio = record_audio()
    if len(audio) > 0:
        transcribe(asr, processor, audio)
    else:
        print("No audio recorded.")
