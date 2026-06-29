"""Cross-MODEL variant of pilot_audio_review.py: run a non-Pro Gemini model
(e.g. Gemini 2.5 Flash, Gemini 3 Flash) as the C0/C1 SUBJECT on audio, reusing
the existing Gemini-3.1-Pro reference transcript and probes, with GPT-5.4 judge.

Why: the only clean long-form-audio C0-vs-C1 comparison so far is on Gemini 3.1
Pro itself; Claude takes no audio and Mimo's audio is bitrate-confounded
(OpenRouter 10MB cap). Flash models are full-quality, long-context multimodal,
so C0 (end-to-end on 26-85 min audio) IS realizable, with no bitrate confound.
This tests whether the reduce-to-text win generalizes across Gemini capability
tiers / generations, and the inverse-baseline prediction (weaker subject ->
lower C0 -> larger cascade gain).

Reuses existing reference_transcript.txt + probes.json in the run-dir (does NOT
regenerate them, so the reference stays the shared Pro reference). Writes:
  review_C0_{label}.txt, transcript_C1_pass1_{label}.txt, review_C1_{label}.txt,
  judge_{halluc,probes}_{C0,C1}_{label}.json, and a summary block.

Usage:
  python3 pilot/pilot_audio_review_gemini_xmodel.py \
    --run-dir runs/audio-review-3b1b_attention-1778857367 \
    --audio data/longform_audio/3blue1brown_attention_32k.mp3 \
    --model gemini-2.5-flash --label flash25
"""
from __future__ import annotations
import argparse, json, os, pathlib, subprocess, sys, time
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import google.genai as genai
from google.genai import types

from pilot_audio_review import (
    REVIEW_PROMPT,
    call_gemini,
    pass2_review_prompt,
    score_review,
)

_CHUNK_PROMPT = (
    "Transcribe this audio segment in full. Capture every spoken sentence "
    "verbatim, including disfluencies and false starts. Identify speaker "
    "changes when audible. Output plain text only; do not summarize or paraphrase."
)


def _thinking_cfg(model: str):
    """Transcription is not a reasoning task; minimize thinking so the output
    budget is not consumed by deliberation (Gemini 3 Flash otherwise returns an
    empty transcript). 2.5 Flash can disable thinking outright; 3 Flash requires
    thinking mode, so we use the minimum 'low' level."""
    if "2.5" in model:
        return types.ThinkingConfig(thinking_budget=0)
    return types.ThinkingConfig(thinking_level="low")


def chunked_transcribe(audio_path: str, model: str, chunk_seconds: int = 1800,
                       overlap_seconds: int = 5) -> tuple[str, int]:
    """Chunked verbatim transcription by `model`, with minimal thinking."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
         "csv=p=0", audio_path], capture_output=True, text=True).stdout.strip())
    starts = list(range(0, int(dur), chunk_seconds))
    n = len(starts)
    print(f"      [chunk] duration {dur:.0f}s -> {n} chunk(s)", flush=True)
    work = pathlib.Path(audio_path).parent / f".chunks_xmodel_{pathlib.Path(audio_path).stem}"
    work.mkdir(exist_ok=True)
    pieces = []; total_ms = 0
    for i, start in enumerate(starts):
        end = min(dur, start + chunk_seconds + overlap_seconds)
        cp = work / f"chunk_{i:02d}.mp3"
        if not cp.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", audio_path,
                            "-ss", str(start), "-to", str(end), "-c:a", "libmp3lame",
                            "-b:a", "32k", str(cp)], check=True)
        parts = [_CHUNK_PROMPT, types.Part.from_bytes(data=cp.read_bytes(), mime_type="audio/mpeg")]
        t0 = time.time()
        try:
            resp = client.models.generate_content(
                model=model, contents=parts,
                config=types.GenerateContentConfig(temperature=0.0, top_p=1.0,
                    max_output_tokens=65_536, thinking_config=_thinking_cfg(model)))
            txt = (resp.text or "").strip()
        except Exception as e:
            txt = ""; print(f"        [warn] chunk {i+1}/{n}: {type(e).__name__}: {str(e)[:100]}", flush=True)
        ms = int((time.time() - t0) * 1000); total_ms += ms
        pieces.append(f"=== chunk {i+1}/{n} ===\n{txt or '(empty)'}")
        print(f"      [chunk {i+1}/{n}] {ms/1000:.1f}s, {len(txt.split())} words", flush=True)
    return "\n\n".join(pieces), total_ms


def run(run_dir: pathlib.Path, audio: pathlib.Path, model: str, label: str):
    ref_path = run_dir / "reference_transcript.txt"
    probes_path = run_dir / "probes.json"
    if not ref_path.exists() or not probes_path.exists():
        raise SystemExit(f"need existing reference+probes in {run_dir}")
    reference = ref_path.read_text()
    probes = json.loads(probes_path.read_text()).get("probes", [])
    print(f"[run_dir] {run_dir}\n[model] {model} (label={label})", flush=True)
    print(f"  [ref] reusing existing ({len(reference.split())} words), {len(probes)} probes", flush=True)

    # C0: end-to-end review over raw audio
    c0_path = run_dir / f"review_C0_{label}.txt"
    skip_path = run_dir / f"review_C0_{label}.SKIPPED"
    if c0_path.exists():
        review_c0 = c0_path.read_text(); print("  [C0] reuse", flush=True)
    elif skip_path.exists():
        review_c0 = None; print("  [C0] previously skipped", flush=True)
    else:
        print(f"  [C0] {model} end-to-end on raw audio...", flush=True)
        try:
            review_c0, ms = call_gemini(REVIEW_PROMPT, str(audio), model)
            if not review_c0:
                raise RuntimeError("empty C0 (likely audio too long / budget)")
            c0_path.write_text(review_c0)
            print(f"    C0: {len(review_c0.split())} words ({ms/1000:.0f}s)", flush=True)
        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"    [skip] C0 failed ({msg})", flush=True)
            skip_path.write_text(msg); review_c0 = None

    # C1 Pass-1: chunked transcription by the same subject model
    p1_path = run_dir / f"transcript_C1_pass1_{label}.txt"
    if p1_path.exists():
        c1_pass1 = p1_path.read_text(); print("  [C1.p1] reuse", flush=True)
    else:
        print(f"  [C1.p1] {model} chunked-audio transcription...", flush=True)
        c1_pass1, ms = chunked_transcribe(str(audio), model)
        p1_path.write_text(c1_pass1)
        print(f"    C1.p1: {len(c1_pass1.split())} words ({ms/1000:.0f}s)", flush=True)
    if not c1_pass1 or len(c1_pass1.split()) < 50:
        raise RuntimeError(f"C1 Pass-1 too short ({len(c1_pass1.split())} words)")

    # C1 Pass-2: text-only review from the subject's own transcript
    c1_path = run_dir / f"review_C1_{label}.txt"
    if c1_path.exists():
        review_c1 = c1_path.read_text(); print("  [C1.p2] reuse", flush=True)
    else:
        print(f"  [C1.p2] {model} text-only review from transcript...", flush=True)
        review_c1, ms = call_gemini(pass2_review_prompt(c1_pass1, REVIEW_PROMPT), None, model)
        c1_path.write_text(review_c1)
        print(f"    C1: {len(review_c1.split())} words ({ms/1000:.0f}s)", flush=True)

    # Score (GPT-5.4 judge vs the shared Pro reference + probes)
    score_c0 = score_review(review_c0, reference, probes, f"C0_{label}", run_dir) if review_c0 else None
    score_c1 = score_review(review_c1, reference, probes, f"C1_{label}", run_dir)

    sp = run_dir / "summary.json"
    summary = json.loads(sp.read_text()) if sp.exists() else {}
    if score_c0 is not None:
        summary.setdefault("scores", {})[f"C0_{label}"] = asdict(score_c0)
    summary.setdefault("scores", {})[f"C1_{label}"] = asdict(score_c1)
    summary[f"{label}_model"] = model
    sp.write_text(json.dumps(summary, indent=2))

    print(f"\n=== {label} {run_dir.name} ===", flush=True)
    for s in [score_c0, score_c1]:
        if s is None:
            print("  C0  SKIPPED", flush=True); continue
        print(f"  {s.condition}  unsupported={s.n_unsupported}  "
              f"cov={s.probe_coverage:.3f} ({s.n_covered}/{s.n_probes})", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--audio", type=pathlib.Path, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", required=True, help="e.g. flash25, flash3")
    args = ap.parse_args()
    run(args.run_dir, args.audio, args.model, args.label)


if __name__ == "__main__":
    main()
