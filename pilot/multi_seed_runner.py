"""Multi-seed Pass-2 runner for n=5 verification of Gemini cascade-fix claims.

Two modes:
  - mode=strip: single Pass-2 from a citation-stripped transcript
  - mode=chunked_concat: split transcript into K chunks, sub-summarize each,
    concatenate (no merge — the concat variant is the published Mode-A fix)

Each mode runs with a specified seed and temperature; outputs are written
with seed-tagged labels so multiple seeds coexist in the same run-dir.

Usage:
  python3 pilot/multi_seed_runner.py \
      --run-dir runs/paper-review-19690013408-1777471789 \
      --mode strip \
      --transcript-file transcript_C1_pass1_stripped.txt \
      --label-prefix C1_stripped_ms \
      --seed 1 --temperature 0.7
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from google import genai
from google.genai import types

from pilot_audio_review import score_review
from pilot_audio_review import pass2_review_prompt as _audio_pass2_prompt
from pilot_paper_review import pass2_review_prompt as _paper_pass2_prompt
from chunked_pass2 import (
    SUB_SUMMARY_PROMPT_TMPL,
    split_transcript,
)


def pass2_review_prompt(transcript: str, run_dir_name: str) -> str:
    """Dispatch to audio vs paper Pass-2 prompt based on run-dir naming.

    Run dirs starting with 'audio-' use the audio framing; those starting with
    'paper-' use the document framing. Same content otherwise.
    """
    if run_dir_name.startswith("audio-"):
        return _audio_pass2_prompt(transcript)
    return _paper_pass2_prompt(transcript)


def call_gemini_seeded(
    prompt: str,
    model: str,
    temperature: float,
    seed: int,
    max_output_tokens: int = 65_536,
) -> tuple[str, int]:
    """Single Gemini text-only call with explicit seed + temperature."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    t0 = time.time()
    resp = client.models.generate_content(
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=temperature,
            top_p=1.0,
            max_output_tokens=max_output_tokens,
            seed=seed,
        ),
    )
    ms = int((time.time() - t0) * 1000)
    text = (resp.text or "").strip()
    return text, ms


def run_strip(
    run_dir: pathlib.Path,
    transcript_file: str,
    model: str,
    temperature: float,
    seed: int,
    label: str,
) -> dict:
    transcript = (run_dir / transcript_file).read_text()
    ref = (run_dir / "reference_transcript.txt").read_text()
    probes = json.loads((run_dir / "probes.json").read_text()).get("probes", [])

    review_path = run_dir / f"review_{label}.txt"
    if review_path.exists():
        review = review_path.read_text()
        print(f"  [{label}] reusing existing review", flush=True)
    else:
        prompt = pass2_review_prompt(transcript, run_dir.name)
        print(f"  [{label}] Pass-2 seed={seed} T={temperature}", flush=True)
        review, ms = call_gemini_seeded(prompt, model, temperature, seed)
        review_path.write_text(review)
        print(f"    wrote {len(review.split())} words ({ms/1000:.1f}s)", flush=True)

    score = score_review(review, ref, probes, label, run_dir)
    return {
        "label": label,
        "seed": seed,
        "temperature": temperature,
        "n_unsupported": score.n_unsupported,
        "n_probes": score.n_probes,
        "n_covered": score.n_covered,
        "probe_coverage": score.probe_coverage,
        "review_words": len(review.split()),
    }


def run_chunked_concat(
    run_dir: pathlib.Path,
    transcript_file: str,
    model: str,
    temperature: float,
    seed: int,
    label: str,
    n_chunks: int = 5,
    sub_summary_words: int = 500,
) -> dict:
    transcript = (run_dir / transcript_file).read_text()
    ref = (run_dir / "reference_transcript.txt").read_text()
    probes = json.loads((run_dir / "probes.json").read_text()).get("probes", [])

    chunks = split_transcript(transcript, n_chunks)
    print(f"  [{label}] split into {len(chunks)} chunks (seed={seed}, T={temperature})", flush=True)

    sub_path = run_dir / f"review_{label}_subsummaries.txt"
    concat_path = run_dir / f"review_{label}.txt"
    if concat_path.exists():
        review = concat_path.read_text()
        print(f"  [{label}] reusing existing concat", flush=True)
    else:
        sub_summaries: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            prompt = SUB_SUMMARY_PROMPT_TMPL.format(
                i=i, N=len(chunks), target_words=sub_summary_words, chunk=chunk,
            )
            sub, ms = call_gemini_seeded(prompt, model, temperature, seed + i * 7919)
            if not sub:
                sub = "(empty)"
            sub_summaries.append(f"=== Section {i}/{len(chunks)} ===\n{sub}")
            print(f"    [chunk {i}/{len(chunks)}] {len(sub.split())} words ({ms/1000:.1f}s)", flush=True)
        sub_path.write_text("\n\n".join(sub_summaries))
        review = "\n\n".join(sub_summaries)
        concat_path.write_text(review)
        print(f"  [{label}] concat: {len(review.split())} words", flush=True)

    score = score_review(review, ref, probes, label, run_dir)
    return {
        "label": label,
        "seed": seed,
        "temperature": temperature,
        "mode": "chunked_concat",
        "n_chunks": len(chunks),
        "n_unsupported": score.n_unsupported,
        "n_probes": score.n_probes,
        "n_covered": score.n_covered,
        "probe_coverage": score.probe_coverage,
        "review_words": len(review.split()),
    }


def run_plain(
    run_dir: pathlib.Path,
    transcript_file: str,
    model: str,
    temperature: float,
    seed: int,
    label: str,
) -> dict:
    """Plain C1 Pass-2 with seed+temperature — same code path as strip but
    uses the unstripped Pass-1 transcript. Used for per-cell multi-seed
    error bars on the headline cells.
    """
    return run_strip(run_dir, transcript_file, model, temperature, seed, label)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--mode", choices=["strip", "chunked_concat", "plain"], required=True)
    ap.add_argument("--transcript-file", required=True)
    ap.add_argument("--label-prefix", required=True,
                    help="Outputs will be review_<prefix>_seed<N>.txt")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--model", default="gemini-3.1-pro-preview")
    ap.add_argument("--n-chunks", type=int, default=5)
    ap.add_argument("--sub-summary-words", type=int, default=500)
    args = ap.parse_args()

    rd = args.run_dir
    if not rd.exists():
        raise SystemExit(f"run-dir not found: {rd}")

    label = f"{args.label_prefix}_seed{args.seed}"
    print(f"[multi_seed] {rd.name} mode={args.mode} label={label}", flush=True)

    if args.mode == "strip":
        result = run_strip(rd, args.transcript_file, args.model, args.temperature, args.seed, label)
    elif args.mode == "plain":
        result = run_plain(rd, args.transcript_file, args.model, args.temperature, args.seed, label)
    elif args.mode == "chunked_concat":
        result = run_chunked_concat(
            rd, args.transcript_file, args.model, args.temperature, args.seed, label,
            n_chunks=args.n_chunks, sub_summary_words=args.sub_summary_words,
        )
    else:
        raise SystemExit(f"unknown mode: {args.mode}")

    # Append to multi-seed log per cell
    log_path = rd / f"multi_seed_{args.label_prefix}.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {"runs": []}
    # Replace any prior entry for the same seed
    log["runs"] = [r for r in log["runs"] if r.get("seed") != args.seed]
    log["runs"].append(result)
    log["runs"].sort(key=lambda r: r.get("seed", 0))
    log_path.write_text(json.dumps(log, indent=2))

    print(
        f"  [{label}] halluc={result['n_unsupported']}  "
        f"cov={result['probe_coverage']:.3f} ({result['n_covered']}/{result['n_probes']})",
        flush=True,
    )


if __name__ == "__main__":
    main()
