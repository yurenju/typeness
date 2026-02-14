"""Whisper speech recognition module for Typeness.

Loads the Whisper model and provides transcription with CJK text normalization.
"""

import re
import time

import numpy as np
import torch
from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoProcessor,
    pipeline,
)

WHISPER_MODEL_ID = "openai/whisper-large-v3-turbo"
WHISPER_INITIAL_PROMPT = "以下是繁體中文的語音內容。"

# Half-width -> full-width punctuation mapping for CJK text
_PUNCTUATION_MAP = str.maketrans({
    ",": "，",
    ":": "：",
    ";": "；",
    "!": "！",
    "?": "？",
    "(": "（",
    ")": "）",
})


def _normalize_punctuation(text: str) -> str:
    """Replace half-width punctuation with full-width equivalents for CJK text."""
    return text.translate(_PUNCTUATION_MAP)


def _add_cjk_spacing(text: str) -> str:
    """Insert a space between CJK and Latin/digit characters where missing."""
    # CJK before Latin/digit: 中A -> 中 A
    text = re.sub(
        r"([\u4e00-\u9fff\u3400-\u4dbf])([A-Za-z0-9])", r"\1 \2", text
    )
    # Latin/digit before CJK: A中 -> A 中 (but not punctuation before CJK)
    text = re.sub(
        r"([A-Za-z0-9])([\u4e00-\u9fff\u3400-\u4dbf])", r"\1 \2", text
    )
    return text


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
    """Transcribe audio using the Whisper pipeline."""
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
    text = _normalize_punctuation(result["text"])
    print(f"Whisper result ({elapsed:.2f}s): {text}")
    return text
