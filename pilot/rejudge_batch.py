"""Batch multi-judge re-runs for measuring GPT-5.4 judge variance on existing
review files. Re-uses the existing `score_review` pipeline but writes outputs
with seed-tagged labels so multiple runs of the same review coexist.

Usage:
  python3 pilot/rejudge_batch.py \
      --run-dir runs/paper-review-19720022550-1778857333 \
      --review-file review_C0.txt \
      --base-label C0_jrun \
      --n-runs 3
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from pilot_audio_review import score_review


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--review-file", required=True)
    ap.add_argument("--base-label", required=True,
                    help="Output files will be judge_halluc_<base-label><idx>.json etc.")
    ap.add_argument("--n-runs", type=int, default=3)
    ap.add_argument("--start-idx", type=int, default=1,
                    help="First index for label suffix (so re-running adds rather than overwriting)")
    args = ap.parse_args()

    rd = args.run_dir
    review = (rd / args.review_file).read_text()
    ref = (rd / "reference_transcript.txt").read_text()
    probes = json.loads((rd / "probes.json").read_text()).get("probes", [])

    print(f"[batch-rejudge] {rd.name}/{args.review_file} ({len(review.split())} words), {args.n_runs} runs", flush=True)

    results = []
    for k in range(args.n_runs):
        idx = args.start_idx + k
        label = f"{args.base_label}{idx}"
        t0 = time.time()
        score = score_review(review, ref, probes, label, rd)
        ms = int((time.time() - t0) * 1000)
        results.append({
            "label": label,
            "n_unsupported": score.n_unsupported,
            "n_probes": score.n_probes,
            "n_covered": score.n_covered,
            "probe_coverage": score.probe_coverage,
            "ms": ms,
        })
        print(f"  [{label}] halluc={score.n_unsupported} cov={score.probe_coverage:.3f} ({ms/1000:.1f}s)", flush=True)

    log_path = rd / f"rejudge_{args.base_label}_summary.json"
    existing = json.loads(log_path.read_text()) if log_path.exists() else {"runs": []}
    existing["runs"].extend(results)
    log_path.write_text(json.dumps(existing, indent=2))


if __name__ == "__main__":
    main()
