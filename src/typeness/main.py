"""Typeness main entry point.

Event-driven loop: hotkey -> record -> transcribe -> process -> paste.
"""

import queue
import time

import transformers

from typeness.audio import MIN_RECORDING_SECONDS, SAMPLE_RATE, record_audio_start, record_audio_stop
from typeness.clipboard import paste_text
from typeness.hotkey import EVENT_START_RECORDING, EVENT_STOP_RECORDING, HotkeyListener
from typeness.postprocess import load_llm, process_text
from typeness.transcribe import load_whisper, transcribe

# Suppress noisy warnings from transformers (duplicate logits-processor, invalid generation flags)
transformers.logging.set_verbosity_error()


def main():
    """Event-driven main loop: hotkey -> record -> transcribe -> process -> paste."""
    print("=== Typeness ===")
    print("Loading models, please wait...\n")

    asr_pipeline, processor = load_whisper()
    llm_model, tokenizer = load_llm()

    event_queue: queue.Queue[str] = queue.Queue()
    listener = HotkeyListener(event_queue)
    listener.start()

    print("\nReady! Press Shift+Win+A to start/stop voice input.")
    print("Press Ctrl+C to exit.\n")

    try:
        while True:
            try:
                event = event_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if event == EVENT_START_RECORDING:
                record_audio_start()

            elif event == EVENT_STOP_RECORDING:
                # Stop recording
                audio = record_audio_stop()
                print("Processing...")

                listener.busy = True
                try:
                    rec_duration = len(audio) / SAMPLE_RATE
                    if rec_duration < MIN_RECORDING_SECONDS:
                        print("Recording too short, skipping.\n")
                        continue

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

                    # Auto-paste to focused window
                    paste_text(processed_text)

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
                finally:
                    listener.busy = False

    finally:
        listener.stop()
