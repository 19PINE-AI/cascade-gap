"""Aggregate Phase-2 multi-judge data with bootstrap CIs.

Reads runs/<tag>/judge_multi.jsonl files, builds a per-cell table averaged
across judges, computes Δ(C1−C0), Δ(C2−C0) per (vendor, paper) with
bootstrap CIs and sign tests.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from stats import bootstrap_ci_paired_diff, sign_test, bootstrap_ci_mean


def load_judge_multi(run_dir: pathlib.Path) -> list[dict]:
    """Load per-cell multi-judge results from a run directory."""
    p = run_dir / "judge_multi.jsonl"
    if not p.exists():
        return []
    rows = []
    for line in p.open():
        d = json.loads(line)
        # Skip cells with errors
        if "error" in d:
            continue
        valid_judges = [j for j in d.get("per_judge", []) if "error" not in j]
        if not valid_judges:
            continue
        # Average precision and coverage across judges
        precs = [j["precision"] for j in valid_judges]
        covs = [j["coverage"] for j in valid_judges]
        rows.append({
            "run_dir": run_dir.name,
            "item_id": d["item_id"],
            "condition": d["condition"],
            "n_judges": len(valid_judges),
            "precision_mean": sum(precs) / len(precs),
            "precision_min": min(precs),
            "precision_max": max(precs),
            "coverage_mean": sum(covs) / len(covs),
            "coverage_min": min(covs),
            "coverage_max": max(covs),
            "precision_range": max(precs) - min(precs),
            "coverage_range": max(covs) - min(covs),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=pathlib.Path, default=pathlib.Path("runs"))
    args = ap.parse_args()

    all_rows = []
    for run_dir in sorted(args.runs_dir.glob("longform-pdf-*")):
        rows = load_judge_multi(run_dir)
        all_rows.extend(rows)

    # Tag each row with vendor (best-guess from run_dir name)
    for r in all_rows:
        rd = r["run_dir"]
        if "openai" in rd:
            r["vendor"] = "GPT-5.4"
        elif "openrouter" in rd and "qwen" in rd:
            r["vendor"] = "Qwen3-VL-30B"
        elif "gemini" in rd:
            r["vendor"] = "Gemini Pro"
        else:
            r["vendor"] = "?"

    print("=== Per-cell mean across judges ===")
    print(f"{'vendor':18s} {'item':14s} {'cond':4s} {'prec':>6s} {'cov':>6s}  {'prec_range':>10s} {'cov_range':>10s}")
    for r in all_rows:
        print(
            f"{r['vendor']:18s} {r['item_id']:14s} {r['condition']:4s} "
            f"{r['precision_mean']:6.3f} {r['coverage_mean']:6.3f}  "
            f"{r['precision_range']:10.3f} {r['coverage_range']:10.3f}"
        )

    # Inter-judge agreement summary
    print("\n=== Inter-judge agreement summary ===")
    prec_ranges = [r["precision_range"] for r in all_rows]
    cov_ranges = [r["coverage_range"] for r in all_rows]
    if prec_ranges:
        print(f"  n cells: {len(prec_ranges)}")
        print(f"  precision range  mean={sum(prec_ranges)/len(prec_ranges):.3f}  max={max(prec_ranges):.3f}")
        print(f"  coverage  range  mean={sum(cov_ranges)/len(cov_ranges):.3f}  max={max(cov_ranges):.3f}")

    # Build paired Δ tables: for each (vendor, item) where both C0 and C1 exist
    by_vendor_item: dict[tuple[str, str], dict[str, dict]] = {}
    for r in all_rows:
        key = (r["vendor"], r["item_id"])
        by_vendor_item.setdefault(key, {})[r["condition"]] = r

    print("\n=== Paired Δ(C1 − C0) by vendor (precision) ===")
    by_vendor_pairs_prec_c1: dict[str, list[tuple[float, float]]] = {}
    by_vendor_pairs_cov_c1: dict[str, list[tuple[float, float]]] = {}
    by_vendor_pairs_prec_c2: dict[str, list[tuple[float, float]]] = {}
    by_vendor_pairs_cov_c2: dict[str, list[tuple[float, float]]] = {}
    for (vendor, item), conds in by_vendor_item.items():
        if "C0" in conds and "C1" in conds:
            by_vendor_pairs_prec_c1.setdefault(vendor, []).append(
                (conds["C0"]["precision_mean"], conds["C1"]["precision_mean"])
            )
            by_vendor_pairs_cov_c1.setdefault(vendor, []).append(
                (conds["C0"]["coverage_mean"], conds["C1"]["coverage_mean"])
            )
        if "C0" in conds and "C2" in conds:
            by_vendor_pairs_prec_c2.setdefault(vendor, []).append(
                (conds["C0"]["precision_mean"], conds["C2"]["precision_mean"])
            )
            by_vendor_pairs_cov_c2.setdefault(vendor, []).append(
                (conds["C0"]["coverage_mean"], conds["C2"]["coverage_mean"])
            )

    for vendor, paired in by_vendor_pairs_prec_c1.items():
        ci = bootstrap_ci_paired_diff(paired)
        sign = sign_test(paired)
        print(
            f"  {vendor:18s}  Δ(C1−C0) prec  n={len(paired)}  Δ={ci.point:+.3f}  CI=[{ci.low:+.3f}, {ci.high:+.3f}]  sign p={sign['p_value']:.3f} (pos={sign['n_pos']}/{sign['n_pos']+sign['n_neg']})"
        )

    print("\n=== Paired Δ(C1 − C0) by vendor (coverage) ===")
    for vendor, paired in by_vendor_pairs_cov_c1.items():
        ci = bootstrap_ci_paired_diff(paired)
        sign = sign_test(paired)
        print(
            f"  {vendor:18s}  Δ(C1−C0) cov   n={len(paired)}  Δ={ci.point:+.3f}  CI=[{ci.low:+.3f}, {ci.high:+.3f}]  sign p={sign['p_value']:.3f} (pos={sign['n_pos']}/{sign['n_pos']+sign['n_neg']})"
        )

    print("\n=== Paired Δ(C2 − C0) by vendor (precision) ===")
    for vendor, paired in by_vendor_pairs_prec_c2.items():
        ci = bootstrap_ci_paired_diff(paired)
        sign = sign_test(paired)
        print(
            f"  {vendor:18s}  Δ(C2−C0) prec  n={len(paired)}  Δ={ci.point:+.3f}  CI=[{ci.low:+.3f}, {ci.high:+.3f}]  sign p={sign['p_value']:.3f} (pos={sign['n_pos']}/{sign['n_pos']+sign['n_neg']})"
        )

    print("\n=== Paired Δ(C2 − C0) by vendor (coverage) ===")
    for vendor, paired in by_vendor_pairs_cov_c2.items():
        ci = bootstrap_ci_paired_diff(paired)
        sign = sign_test(paired)
        print(
            f"  {vendor:18s}  Δ(C2−C0) cov   n={len(paired)}  Δ={ci.point:+.3f}  CI=[{ci.low:+.3f}, {ci.high:+.3f}]  sign p={sign['p_value']:.3f} (pos={sign['n_pos']}/{sign['n_pos']+sign['n_neg']})"
        )


if __name__ == "__main__":
    main()
