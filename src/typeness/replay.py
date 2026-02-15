"""Regression test replay engine for Typeness.

Loads test fixtures (WAV audio + expected text) and replays them through
the Whisper and/or LLM pipeline to detect regressions.

Usage:
    uv run python -m typeness.replay --stage llm
    uv run python -m typeness.replay --stage whisper
    uv run python -m typeness.replay --stage full
    uv run python -m typeness.replay --case 20260215_084842 --stage llm
    uv run python -m typeness.replay --tag short --stage llm
"""

import argparse
import json
import os
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

# Suppress transformers/HF Hub progress bars to keep output concise
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_NO_TQDM", "1")

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
CASES_FILE = FIXTURES_DIR / "cases.json"


def load_cases(case_id=None, tag=None):
    """Load test cases from cases.json, optionally filtering by ID or tag."""
    if not CASES_FILE.exists():
        print(f"No cases.json found at {CASES_FILE}")
        print("Copy cases.example.json to cases.json and add your test cases.")
        return []

    with open(CASES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]

    if case_id is not None:
        cases = [c for c in cases if c["id"] == case_id]

    if tag is not None:
        cases = [c for c in cases if tag in c.get("tags", [])]

    return cases


def _load_wav(audio_path):
    """Read a WAV file and return float32 numpy array (inverse of debug save)."""
    with wave.open(str(audio_path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        int16_data = np.frombuffer(raw, dtype=np.int16)
        return int16_data.astype(np.float32) / 32767.0


def replay_whisper(asr_pipeline, processor, audio_path):
    """Replay a WAV file through Whisper and return (text, latency)."""
    from typeness.transcribe import transcribe

    audio = _load_wav(audio_path)
    start = time.time()
    text = transcribe(asr_pipeline, processor, audio)
    latency = time.time() - start
    return text, latency


def replay_llm(llm_model, tokenizer, whisper_text):
    """Replay text through LLM post-processing and return (text, latency)."""
    from typeness.postprocess import process_text

    start = time.time()
    text = process_text(llm_model, tokenizer, whisper_text)
    latency = time.time() - start
    return text, latency


def replay_full(asr_pipeline, processor, llm_model, tokenizer, audio_path):
    """Run full pipeline: audio -> Whisper -> LLM. Return result dict."""
    from typeness.postprocess import process_text
    from typeness.transcribe import transcribe

    audio = _load_wav(audio_path)

    start_w = time.time()
    whisper_text = transcribe(asr_pipeline, processor, audio)
    whisper_latency = time.time() - start_w

    start_l = time.time()
    processed_text = process_text(llm_model, tokenizer, whisper_text)
    llm_latency = time.time() - start_l

    return {
        "whisper_text": whisper_text,
        "processed_text": processed_text,
        "whisper_latency": whisper_latency,
        "llm_latency": llm_latency,
    }


def _char_diff_ratio(expected, actual):
    """Compute character-level diff ratio: diff chars / max(len(expected), len(actual))."""
    if expected == actual:
        return 0.0
    max_len = max(len(expected), len(actual))
    if max_len == 0:
        return 0.0
    # Count differing characters using simple alignment
    diff_count = 0
    for i in range(max(len(expected), len(actual))):
        ch_e = expected[i] if i < len(expected) else ""
        ch_a = actual[i] if i < len(actual) else ""
        if ch_e != ch_a:
            diff_count += 1
    return diff_count / max_len


def run_all_cases(stage, asr_pipeline=None, processor=None,
                  llm_model=None, tokenizer=None,
                  case_id=None, tag=None):
    """Run replay on all matching cases and return structured results.

    Args:
        stage: "whisper", "llm", or "full"
        asr_pipeline, processor: Whisper model (needed for whisper/full)
        llm_model, tokenizer: LLM model (needed for llm/full)
        case_id: Filter to a single case ID
        tag: Filter to cases with this tag

    Returns:
        List of result dicts with case_id, description, stage_tested,
        expected, actual, match, char_diff_ratio.
    """
    cases = load_cases(case_id=case_id, tag=tag)
    results = []

    for case in cases:
        cid = case["id"]
        audio_path = FIXTURES_DIR / case["audio_file"]

        if stage == "whisper":
            actual, _ = replay_whisper(asr_pipeline, processor, audio_path)
            expected = case.get("whisper_expected")
            result_entry = {
                "case_id": cid,
                "description": case.get("description", ""),
                "stage_tested": "whisper",
                "expected": expected,
                "actual": actual,
            }

        elif stage == "llm":
            # For LLM-only, use the whisper_expected as input
            whisper_input = case.get("whisper_expected")
            if whisper_input is None:
                print(f"  Skipping {cid}: no whisper_expected for LLM-only replay")
                continue
            actual, _ = replay_llm(llm_model, tokenizer, whisper_input)
            expected = case["processed_expected"]
            result_entry = {
                "case_id": cid,
                "description": case.get("description", ""),
                "stage_tested": "llm",
                "expected": expected,
                "actual": actual,
            }

        elif stage == "full":
            full_result = replay_full(
                asr_pipeline, processor, llm_model, tokenizer, audio_path
            )
            expected = case["processed_expected"]
            actual = full_result["processed_text"]
            result_entry = {
                "case_id": cid,
                "description": case.get("description", ""),
                "stage_tested": "full",
                "expected": expected,
                "actual": actual,
                "whisper_text": full_result["whisper_text"],
                "processed_text": full_result["processed_text"],
            }

        else:
            raise ValueError(f"Unknown stage: {stage}")

        # Determine match status
        acceptable = case.get("processed_acceptable") if stage in ("llm", "full") else case.get("whisper_acceptable")
        if expected is None:
            result_entry["match"] = "skipped"
            result_entry["char_diff_ratio"] = None
        elif expected == actual:
            result_entry["match"] = "exact"
            result_entry["char_diff_ratio"] = 0.0
        elif acceptable is not None and acceptable == actual:
            result_entry["match"] = "acceptable"
            result_entry["char_diff_ratio"] = round(
                _char_diff_ratio(expected, actual), 4
            )
        else:
            result_entry["match"] = "different"
            result_entry["char_diff_ratio"] = round(
                _char_diff_ratio(expected, actual), 4
            )

        results.append(result_entry)

    return results


def _generate_report(stage, results, output_path):
    """Generate JSON report and print console summary."""
    exact_count = sum(1 for r in results if r.get("match") == "exact")
    acceptable_count = sum(1 for r in results if r.get("match") == "acceptable")
    different_count = sum(1 for r in results if r.get("match") == "different")
    total = len(results)

    report = {
        "run_timestamp": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "total": total,
        "exact_match": exact_count,
        "acceptable": acceptable_count,
        "different": different_count,
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Console summary
    print(f"\n=== Replay Results ===")
    print(f"Total: {total} | Exact: {exact_count} | Acceptable: {acceptable_count} | Different: {different_count}")
    print()

    for r in results:
        cid = r["case_id"]
        desc = r.get("description", "")
        match = r.get("match", "unknown")
        if match == "exact":
            print(f"[EXACT]      {cid} - {desc}")
        elif match == "acceptable":
            ratio = r.get("char_diff_ratio", 0)
            print(f"[ACCEPTABLE] {cid} - {desc} (diff: {ratio * 100:.1f}%)")
        elif match == "different":
            ratio = r.get("char_diff_ratio", 0)
            print(f"[DIFFERENT]  {cid} - {desc} (diff: {ratio * 100:.1f}%)")
        elif match == "skipped":
            print(f"[SKIPPED]    {cid} - {desc}")

    print(f"\nReport saved to: {output_path}")
    return report


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Typeness regression test replay engine"
    )
    parser.add_argument(
        "--stage",
        choices=["whisper", "llm", "full"],
        default="full",
        help="Pipeline stage to replay (default: full)",
    )
    parser.add_argument(
        "--case",
        default=None,
        help="Run a single case by ID (e.g. 20260215_084842)",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Filter cases by tag (e.g. short, long, technical)",
    )
    parser.add_argument(
        "--output",
        default=str(FIXTURES_DIR / "last_run.json"),
        help="Report output path (default: tests/fixtures/last_run.json)",
    )
    args = parser.parse_args()

    # Load only the models needed for the requested stage
    asr_pipeline = processor = None
    llm_model = tokenizer = None

    if args.stage in ("whisper", "full"):
        from typeness.transcribe import load_whisper
        asr_pipeline, processor = load_whisper()

    if args.stage in ("llm", "full"):
        from typeness.postprocess import load_llm
        llm_model, tokenizer = load_llm()

    results = run_all_cases(
        stage=args.stage,
        asr_pipeline=asr_pipeline,
        processor=processor,
        llm_model=llm_model,
        tokenizer=tokenizer,
        case_id=args.case,
        tag=args.tag,
    )

    _generate_report(args.stage, results, args.output)


if __name__ == "__main__":
    main()
