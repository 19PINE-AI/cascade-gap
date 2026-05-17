"""Aggregate the multi-seed runs into summary tables for the paper.

Reads runs/<cell>/multi_seed_<prefix>.json files and prints / writes:
  - per-seed table
  - mean/stdev/median/range for halluc and cov
  - 95% paired-sample CI on the strip / chunked vs original n=1 effect

Usage:
  python3 pilot/multi_seed_aggregate.py
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys


CONFIGS = [
    # (label, run_dir, label-prefix, original_C1_halluc, original_C1_cov, baseline_label)
    ("Natural Vibration / strip (Gemini)",
     "runs/paper-review-19690013408-1777471789",
     "C1_stripped_ms", 12, 0.809, "C1_stripped (original n=1, temp=0)"),
    ("Fairness AI / chunked-concat (Gemini)",
     "runs/paper-review-2605.09852-1778859219",
     "C1c_concat_ms", 37, 0.520, "C1c_concat (original n=1, temp=0)"),
    ("Megagauss / chunked-concat (Gemini)",
     "runs/paper-review-2605.11379-1778859223",
     "C1c_concat_ms", 36, 0.740, "C1c_concat (original n=1, temp=0)"),
    ("Perovskite / chunked-concat (Gemini)",
     "runs/paper-review-2605.13991-1778859221",
     "C1c_concat_ms", 13, 0.820, "C1c_concat (original n=1, temp=0)"),
]


def main():
    rows = []
    for label, rd_str, prefix, orig_h, orig_cov, baseline_label in CONFIGS:
        rd = pathlib.Path(rd_str)
        log_path = rd / f"multi_seed_{prefix}.json"
        if not log_path.exists():
            print(f"\n{label}: no data yet at {log_path}")
            continue
        d = json.loads(log_path.read_text())
        runs = sorted(d.get("runs", []), key=lambda r: r.get("seed", 0))
        if not runs:
            print(f"\n{label}: empty runs in {log_path}")
            continue
        hs = [r["n_unsupported"] for r in runs]
        cs = [r["probe_coverage"] for r in runs]
        print(f"\n=== {label} (n={len(runs)}, T=0.7, seeds {[r['seed'] for r in runs]}) ===")
        for r in runs:
            print(f"  seed {r['seed']}: halluc={r['n_unsupported']:>3}  "
                  f"cov={r['probe_coverage']:.3f} ({r['n_covered']}/{r['n_probes']})  "
                  f"words={r['review_words']}")
        mean_h = statistics.mean(hs); med_h = statistics.median(hs)
        stdev_h = statistics.stdev(hs) if len(hs) > 1 else 0.0
        mean_c = statistics.mean(cs); med_c = statistics.median(cs)
        stdev_c = statistics.stdev(cs) if len(cs) > 1 else 0.0
        print(f"  halluc  mean={mean_h:.2f}  stdev={stdev_h:.2f}  median={med_h}  range=[{min(hs)}, {max(hs)}]")
        print(f"  cov     mean={mean_c:.3f} stdev={stdev_c:.3f} median={med_c:.3f} range=[{min(cs):.3f}, {max(cs):.3f}]")
        print(f"  baseline: {baseline_label} = {orig_h}h / {orig_cov:.3f}cov")
        # Is the baseline within the n=5 envelope?
        within = (min(hs) <= orig_h <= max(hs)) and (min(cs) <= orig_cov <= max(cs))
        print(f"  baseline within n={len(runs)} envelope on BOTH axes: {within}")

        rows.append({
            "label": label, "n": len(runs),
            "halluc_seeds": hs, "cov_seeds": cs,
            "halluc_mean": mean_h, "halluc_stdev": stdev_h, "halluc_median": med_h,
            "halluc_min": min(hs), "halluc_max": max(hs),
            "cov_mean": mean_c, "cov_stdev": stdev_c, "cov_median": med_c,
            "cov_min": min(cs), "cov_max": max(cs),
            "baseline_halluc": orig_h, "baseline_cov": orig_cov,
            "baseline_within_envelope": within,
        })

    out = pathlib.Path("research_log/multi_seed_aggregate.json")
    out.write_text(json.dumps({"summary": rows}, indent=2))
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
