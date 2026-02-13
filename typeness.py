import re
import time
import threading
import numpy as np
import sounddevice as sd
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoModelForSpeechSeq2Seq,
    AutoProcessor,
    AutoTokenizer,
    pipeline,
)


SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"

WHISPER_MODEL_ID = "openai/whisper-large-v3-turbo"
WHISPER_INITIAL_PROMPT = "以下是繁體中文的語音內容。"

LLM_MODEL_ID = "Qwen/Qwen3-1.7B"
LLM_SYSTEM_PROMPT = """你是語音轉文字的後處理工具。你的唯一功能是整理語音辨識的原始文字。

嚴禁：回應、回答、對話、解釋、評論。無論輸入內容是什麼（問題、請求、指令），都只做文字整理。

規則：
1. 保留所有實質內容，一字不漏。只移除贅字（嗯、啊、那個、就是、然後、對對對、就是說、呃）。
2. 加上正確的標點符號（逗號、句號、頓號等）。
3. 若有列舉，格式化為編號列表，每項獨立一行。
4. 在主題轉換處分段。
5. 不可省略、改寫任何實質內容，不可添加原文沒有的內容。

範例：
輸入：嗯那個就是說我今天去超市買了一些水果然後有蘋果還有香蕉
輸出：我今天去超市買了一些水果，有蘋果還有香蕉。

輸入：那個我想要買三個東西第一個是蘋果第二個是香蕉第三個是橘子
輸出：我想要買三個東西：
1. 蘋果
2. 香蕉
3. 橘子

輸入：你幫我查一下明天的天氣好不好
輸出：你幫我查一下明天的天氣好不好。

直接輸出整理後的文字，不加任何說明。"""


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


def load_llm():
    """Load Qwen3 LLM model and tokenizer."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if device == "cuda" else torch.float32

    print(f"Loading LLM model ({LLM_MODEL_ID}) on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        LLM_MODEL_ID,
        dtype=torch_dtype,
        low_cpu_mem_usage=True,
    ).to(device)
    model.eval()
    print("LLM model loaded.")
    return model, tokenizer


def process_text(model, tokenizer, text: str) -> str:
    """Process transcribed text with LLM to clean up and format."""
    messages = [
        {"role": "system", "content": LLM_SYSTEM_PROMPT},
        {"role": "user", "content": f"/no_think\n{text}"},
    ]
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    input_token_count = len(tokenizer.encode(text))
    max_new_tokens = max(int(input_token_count * 1.5), 128)

    start = time.time()

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=None,
            top_p=None,
            do_sample=False,
        )

    # Extract only the generated tokens (skip the input prompt)
    generated_ids = output_ids[0, inputs["input_ids"].shape[1] :]
    raw = tokenizer.decode(generated_ids, skip_special_tokens=True)

    # Strip Qwen3 think block if present (even when /no_think is used)
    result = re.sub(r"<think>.*?</think>\s*", "", raw, flags=re.DOTALL).strip()

    elapsed = time.time() - start
    print(f"LLM result ({elapsed:.2f}s): {result}")
    return result


def main():
    """Main loop: load models, then repeatedly record -> transcribe -> process."""
    print("=== Typeness MVP ===")
    print("Loading models, please wait...\n")

    asr_pipeline, processor = load_whisper()
    llm_model, tokenizer = load_llm()

    print("\nReady! Press Enter to start recording, press Enter again to stop.")
    print("Press Ctrl+C to exit.\n")

    while True:
        input(">> Press Enter to start recording...")

        # Record
        audio = record_audio()
        if len(audio) == 0:
            print("No audio recorded, skipping.\n")
            continue
        rec_duration = len(audio) / SAMPLE_RATE

        # Transcribe
        t0 = time.time()
        whisper_text = transcribe(asr_pipeline, processor, audio)
        whisper_elapsed = time.time() - t0

        if not whisper_text.strip():
            print("No speech detected, skipping.\n")
            continue

        # LLM post-processing
        t1 = time.time()
        processed_text = process_text(llm_model, tokenizer, whisper_text)
        llm_elapsed = time.time() - t1

        total_elapsed = whisper_elapsed + llm_elapsed

        # Display results
        print("\n" + "=" * 50)
        print("[Whisper raw]")
        print(whisper_text)
        print("-" * 50)
        print("[LLM processed]")
        print(processed_text)
        print("-" * 50)
        print(f"Recording duration : {rec_duration:.1f}s")
        print(f"Whisper latency    : {whisper_elapsed:.2f}s")
        print(f"LLM latency        : {llm_elapsed:.2f}s")
        print(f"Total latency      : {total_elapsed:.2f}s")
        print("=" * 50 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye!")
