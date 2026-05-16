"""Re-run Claude C1 Pass-2 (text-only) at temperature 0.0 for reproducibility,
on cells where we want to verify whether the original strip-helps-Claude finding
survives Pass-2 stochasticity.

For each (run_dir, transcript_file, label) given:
  - Read transcript_file, run Pass-2 via call_claude_text_only (now temp=0.0),
    write review_<label>.txt and score it (GPT-5.4 judge).

Usage:
  python3 pilot/claude_pass2_temp0.py \
      --run-dir runs/paper-review-19700025120-1777462513 \
      --transcript-file transcript_C1_pass1_claude.txt \
      --label C1_claude_t0
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from pilot_audio_review import score_review
from pilot_paper_review import pass2_review_prompt
from pilot_paper_review_claude import call_claude_text_only, CLAUDE_MODEL_DEFAULT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--transcript-file", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--model", default=CLAUDE_MODEL_DEFAULT)
    args = ap.parse_args()

    rd = args.run_dir
    transcript = (rd / args.transcript_file).read_text()
    ref = (rd / "reference_transcript.txt").read_text()
    probes = json.loads((rd / "probes.json").read_text()).get("probes", [])

    review_path = rd / f"review_{args.label}.txt"
    if review_path.exists():
        print(f"  [{args.label}] reusing existing review", flush=True)
        review = review_path.read_text()
    else:
        print(f"  [{args.label}] Pass-2 with {args.model} (temp=0.0)...", flush=True)
        review, ms = call_claude_text_only(pass2_review_prompt(transcript), args.model)
        review_path.write_text(review)
        print(f"    {args.label}: {len(review.split())} words ({ms/1000:.1f}s)", flush=True)

    score = score_review(review, ref, probes, args.label, rd)
    sp = rd / "summary.json"
    s = json.loads(sp.read_text()) if sp.exists() else {}
    s.setdefault("scores", {})[args.label] = asdict(score)
    s[f"review_{args.label}_word_count"] = len(review.split())
    sp.write_text(json.dumps(s, indent=2))
    print(f"  [{args.label}] halluc={score.n_unsupported} cov={score.probe_coverage:.3f}", flush=True)


if __name__ == "__main__":
    main()
