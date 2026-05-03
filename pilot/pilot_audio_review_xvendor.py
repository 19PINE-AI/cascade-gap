"""Cross-vendor variant of pilot_audio_review.py — uses OpenRouter for the
audio multimodal model (Mimo v2-omni from Xiaomi), keeping Gemini's reference
transcript and probes, and GPT-5.4 as judge.

Goal: test whether the cascade pattern (cascade reduces hallucinations,
improves coverage) replicates on a different audio multimodal vendor.

Usage:
  python3 pilot/pilot_audio_review_xvendor.py \
    --run-dir runs/audio-review-karpathy_sogpt-1777458038 \
    --audio data/longform_audio/karpathy_sogpt_32k.mp3 \
    --task review

If --run-dir already has a reference + probes (Gemini run), they are reused.
The script writes:
  - review_C0_xvendor.txt
  - transcript_C1_pass1_xvendor.txt
  - review_C1_xvendor.txt
  - judge_halluc_C0_xvendor.json   judge_probes_C0_xvendor.json
  - judge_halluc_C1_xvendor.json   judge_probes_C1_xvendor.json
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from openai import OpenAI

from pilot_audio_review import (
    MEETING_MINUTES_PROMPT,
    PROMPTS_BY_TASK,
    REVIEW_PROMPT,
    REFERENCE_TRANSCRIPTION_PROMPT,
    pass2_review_prompt,
    score_review,
)

REPO = pathlib.Path(__file__).resolve().parent.parent
XVENDOR_MODEL_DEFAULT = "xiaomi/mimo-v2-omni"


def _openrouter_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )


def call_xvendor_with_audio(prompt: str, audio_path: str, model: str, max_tokens: int = 8_000) -> tuple[str, int]:
    client = _openrouter_client()
    with open(audio_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    fmt = pathlib.Path(audio_path).suffix.lstrip(".").lower()
    t0 = time.time()
    r = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {"type": "input_audio", "input_audio": {"data": b64, "format": fmt}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    ms = int((time.time() - t0) * 1000)
    if not (r.choices and r.choices[0].message):
        return "", ms
    return (r.choices[0].message.content or "").strip(), ms


def call_xvendor_text(prompt: str, model: str, max_tokens: int = 8_000) -> tuple[str, int]:
    client = _openrouter_client()
    t0 = time.time()
    r = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    )
    ms = int((time.time() - t0) * 1000)
    if not (r.choices and r.choices[0].message):
        return "", ms
    return (r.choices[0].message.content or "").strip(), ms


def split_audio(audio_path: str, chunk_seconds: int = 1800, overlap_seconds: int = 5,
                workdir: pathlib.Path | None = None) -> list[pathlib.Path]:
    audio_p = pathlib.Path(audio_path)
    workdir = workdir or audio_p.parent / f".chunks_xvendor_{audio_p.stem}_{int(time.time())}"
    workdir.mkdir(parents=True, exist_ok=True)
    dur = float(subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_p)],
        capture_output=True, text=True,
    ).stdout.strip())
    n_chunks = max(1, int((dur - 1) // chunk_seconds) + 1)
    print(f"      [chunk] duration {dur:.0f}s, splitting into {n_chunks} chunk(s) of {chunk_seconds}s + {overlap_seconds}s overlap", flush=True)
    chunk_paths: list[pathlib.Path] = []
    for i in range(n_chunks):
        start = max(0, i * chunk_seconds - (overlap_seconds if i > 0 else 0))
        end = min(dur, (i + 1) * chunk_seconds)
        out = workdir / f"chunk_{i:02d}.mp3"
        if not out.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_p),
                 "-ss", str(start), "-to", str(end), "-c:a", "libmp3lame", "-b:a", "32k", str(out)],
                check=True,
            )
        chunk_paths.append(out)
    return chunk_paths


def call_xvendor_chunked_audio(audio_path: str, model: str) -> tuple[str, int]:
    chunks = split_audio(audio_path)
    pieces: list[str] = []
    total_ms = 0
    for i, cp in enumerate(chunks):
        t0 = time.time()
        text, ms = call_xvendor_with_audio(REFERENCE_TRANSCRIPTION_PROMPT, str(cp), model, max_tokens=16_000)
        chunk_ms = int((time.time() - t0) * 1000)
        total_ms += chunk_ms
        if not text:
            print(f"      [warn] chunk {i+1}/{len(chunks)} empty after {chunk_ms/1000:.1f}s", flush=True)
            text = "(empty)"
        marker_start = i * 1800
        marker_end = (i + 1) * 1800
        pieces.append(f"=== chunk {i+1}/{len(chunks)} ({marker_start}-{marker_end}s) ===\n{text}")
        print(f"      [chunk {i+1}/{len(chunks)}] {chunk_ms/1000:.1f}s, {len(text.split())} words", flush=True)
    return "\n\n".join(pieces), total_ms


def run(audio_path: pathlib.Path, run_dir: pathlib.Path, task: str, model: str):
    print(f"[run_dir] {run_dir}", flush=True)
    print(f"[xvendor model] {model}", flush=True)
    print(f"[task] {task}", flush=True)

    ref_path = run_dir / "reference_transcript.txt"
    probes_path = run_dir / "probes.json"
    if not ref_path.exists():
        raise SystemExit(f"reference_transcript.txt not found in {run_dir}")
    if not probes_path.exists():
        raise SystemExit(f"probes.json not found in {run_dir}")

    reference = ref_path.read_text()
    probes = json.loads(probes_path.read_text()).get("probes", [])
    print(f"  [ref] reusing existing ({len(reference.split())} words)", flush=True)
    print(f"  [probes] reusing existing ({len(probes)} probes)", flush=True)

    task_prompt = PROMPTS_BY_TASK[task]

    # C0_xvendor — end-to-end
    c0_path = run_dir / "review_C0_xvendor.txt"
    if c0_path.exists():
        print(f"  [C0_xvendor] reusing existing", flush=True)
        review_c0 = c0_path.read_text()
    else:
        print(f"  [C0_xvendor] {model} end-to-end {task} on full audio...", flush=True)
        review_c0, ms = call_xvendor_with_audio(task_prompt, str(audio_path), model, max_tokens=8_000)
        c0_path.write_text(review_c0)
        print(f"    C0_xvendor: {len(review_c0.split())} words ({ms/1000:.1f}s)", flush=True)
    if not review_c0 or len(review_c0.split()) < 50:
        raise RuntimeError(f"C0 review too short ({len(review_c0.split())} words)")

    # C1_xvendor Pass-1 — chunked transcription
    c1p1_path = run_dir / "transcript_C1_pass1_xvendor.txt"
    if c1p1_path.exists():
        print(f"  [C1.p1_xvendor] reusing existing", flush=True)
        c1_pass1 = c1p1_path.read_text()
    else:
        print(f"  [C1.p1_xvendor] {model} chunked transcription...", flush=True)
        c1_pass1, ms = call_xvendor_chunked_audio(str(audio_path), model)
        c1p1_path.write_text(c1_pass1)
        print(f"    C1.p1_xvendor: {len(c1_pass1.split())} words ({ms/1000:.1f}s)", flush=True)
    if not c1_pass1 or len(c1_pass1.split()) < 50:
        raise RuntimeError(f"C1 Pass-1 transcript too short ({len(c1_pass1.split())} words)")

    # C1_xvendor Pass-2 — text-only review from transcript
    c1_path = run_dir / "review_C1_xvendor.txt"
    if c1_path.exists():
        print(f"  [C1.p2_xvendor] reusing existing", flush=True)
        review_c1 = c1_path.read_text()
    else:
        print(f"  [C1.p2_xvendor] {model} {task} from transcript...", flush=True)
        review_c1, ms = call_xvendor_text(pass2_review_prompt(c1_pass1, task_prompt), model, max_tokens=8_000)
        c1_path.write_text(review_c1)
        print(f"    C1_xvendor: {len(review_c1.split())} words ({ms/1000:.1f}s)", flush=True)

    # Score with GPT-5.4 (existing judge)
    score_c0 = score_review(review_c0, reference, probes, "C0_xvendor", run_dir)
    score_c1 = score_review(review_c1, reference, probes, "C1_xvendor", run_dir)

    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    summary.setdefault("scores", {})["C0_xvendor"] = asdict(score_c0)
    summary["scores"]["C1_xvendor"] = asdict(score_c1)
    summary["review_C0_xvendor_word_count"] = len(review_c0.split())
    summary["review_C1_xvendor_word_count"] = len(review_c1.split())
    summary["transcript_C1_pass1_xvendor_word_count"] = len(c1_pass1.split())
    summary["xvendor_model"] = model
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f"\n=== xvendor {run_dir.name} ===", flush=True)
    for s in [score_c0, score_c1]:
        print(
            f"  {s.condition}  halluc_score={s.halluc_score} (unsupported={s.n_unsupported})  "
            f"probe_cov={s.probe_coverage:.3f} ({s.n_covered}/{s.n_probes})  "
            f"final={s.final_score:.3f}",
            flush=True,
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--audio", type=pathlib.Path, required=True)
    ap.add_argument("--task", choices=list(PROMPTS_BY_TASK), default="review")
    ap.add_argument("--model", default=XVENDOR_MODEL_DEFAULT)
    args = ap.parse_args()
    run(args.audio, args.run_dir, args.task, args.model)


if __name__ == "__main__":
    main()
