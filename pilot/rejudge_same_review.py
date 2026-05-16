"""Re-judge an existing review file with GPT-5.4 to measure judge intra-rater variance.

Compares the new judgment to the original (already in run-dir).

Usage:
  python3 pilot/rejudge_same_review.py \
      --run-dir runs/paper-review-19700025120-1777462513 \
      --review-file review_C1_claude.txt.bak_pre_temp0 \
      --label C1_claude_rejudge
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from pilot_audio_review import score_review


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--review-file", required=True)
    ap.add_argument("--label", required=True)
    args = ap.parse_args()

    rd = args.run_dir
    review = (rd / args.review_file).read_text()
    ref = (rd / "reference_transcript.txt").read_text()
    probes = json.loads((rd / "probes.json").read_text()).get("probes", [])

    print(f"[review] {args.review_file} ({len(review.split())} words)", flush=True)
    print(f"[label]  {args.label}", flush=True)

    # Use score_review but with a unique label so it writes to fresh files
    score = score_review(review, ref, probes, args.label, rd)
    print(f"  [{args.label}] halluc={score.n_unsupported} cov={score.probe_coverage:.3f}", flush=True)


if __name__ == "__main__":
    main()
