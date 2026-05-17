"""Generate LaTeX table + summary text for the chunked Pass-2 n=5 verification.

Reads multi_seed_C1c_concat_ms.json from the three arXiv run-dirs and prints:
  - LaTeX table body with mean/stdev/range
  - per-cell direction-survives-or-not assessment vs C1 baseline
"""
from __future__ import annotations

import json
import pathlib
import statistics

CELLS = [
    # (label, run_dir, c1_baseline_halluc, c1_baseline_cov, orig_n1_h, orig_n1_cov)
    ("arXiv Fairness AI", "runs/paper-review-2605.09852-1778859219", 15, 0.40, 37, 0.52),
    ("arXiv Megagauss", "runs/paper-review-2605.11379-1778859223", 32, 0.68, 36, 0.74),
    ("arXiv Perovskite", "runs/paper-review-2605.13991-1778859221", 3, 0.74, 13, 0.82),
]


def main():
    print("\n=== Chunked Pass-2 n=5 verification (Mode-A intervention) ===\n")
    print("\\begin{tabular}{lrrrrrl}")
    print("\\toprule")
    print("Cell & C1 baseline & orig n=1 (T=0) & n=5 halluc mean$\\pm$stdev & n=5 cov mean$\\pm$stdev & cov range & direction survives \\\\")
    print("\\midrule")

    summary_rows = []
    for label, rd_str, c1h, c1c, orig_h, orig_cov in CELLS:
        p = pathlib.Path(rd_str) / "multi_seed_C1c_concat_ms.json"
        if not p.exists():
            print(f"% {label}: missing {p}")
            continue
        runs = sorted(json.loads(p.read_text())["runs"], key=lambda r: r.get("seed", 0))
        if len(runs) < 5:
            print(f"% {label}: only {len(runs)}/5 seeds done, skipping table row")
            continue
        hs = [r["n_unsupported"] for r in runs]
        cs = [r["probe_coverage"] for r in runs]
        mh, sh, mc, sc = statistics.mean(hs), statistics.stdev(hs), statistics.mean(cs), statistics.stdev(cs)
        cov_lo, cov_hi = min(cs), max(cs)
        h_lo, h_hi = min(hs), max(hs)

        # Direction-survives test:
        # cascade-direction = cov gain (cov > C1 baseline) at halluc cost (halluc > C1 baseline)
        cov_gain_n5 = mc - c1c
        halluc_cost_n5 = mh - c1h
        cov_gain_orig = orig_cov - c1c
        halluc_cost_orig = orig_h - c1h

        # Does the direction hold at n=5? (positive cov gain + positive halluc cost)
        direction_holds = cov_gain_n5 > 0 and halluc_cost_n5 > 0

        # Is the orig n=1 cov within the n=5 envelope?
        orig_in_envelope = cov_lo <= orig_cov <= cov_hi

        sign_str = "yes" if direction_holds else "NO"
        envelope_note = "orig in n=5 env" if orig_in_envelope else "orig outside n=5 env"
        print(
            f"{label} & {c1h}h/{c1c:.2f} & {orig_h}h/{orig_cov:.2f} & "
            f"{mh:.1f}$\\pm${sh:.1f} & {mc:.3f}$\\pm${sc:.3f} & [{cov_lo:.3f}, {cov_hi:.3f}] & {sign_str} ({envelope_note}) \\\\"
        )
        summary_rows.append({
            "cell": label, "n": len(runs),
            "halluc_seeds": hs, "cov_seeds": cs,
            "halluc_mean": mh, "halluc_stdev": sh,
            "cov_mean": mc, "cov_stdev": sc,
            "cov_range": [cov_lo, cov_hi],
            "halluc_range": [h_lo, h_hi],
            "baseline_C1_halluc": c1h,
            "baseline_C1_cov": c1c,
            "orig_n1_halluc": orig_h,
            "orig_n1_cov": orig_cov,
            "cov_gain_n5_mean": cov_gain_n5,
            "halluc_cost_n5_mean": halluc_cost_n5,
            "direction_holds": direction_holds,
            "orig_in_n5_envelope_on_cov": orig_in_envelope,
        })

    print("\\bottomrule")
    print("\\end{tabular}\n")

    # Plain-text summary for the prose paragraph
    print("=== Prose-text summary ===")
    for r in summary_rows:
        if r["direction_holds"]:
            print(f"  {r['cell']}: direction REPLICATES at n=5 "
                  f"(Δcov mean {r['cov_gain_n5_mean']:+.3f}, Δhalluc mean {r['halluc_cost_n5_mean']:+.1f}); "
                  f"original n=1 cov {r['orig_n1_cov']:.2f} {'within' if r['orig_in_n5_envelope_on_cov'] else 'OUTSIDE'} n=5 envelope [{r['cov_range'][0]:.2f}, {r['cov_range'][1]:.2f}]")
        else:
            print(f"  {r['cell']}: direction DOES NOT REPLICATE at n=5 "
                  f"(Δcov mean {r['cov_gain_n5_mean']:+.3f}, Δhalluc mean {r['halluc_cost_n5_mean']:+.1f}); "
                  f"original n=1 cov {r['orig_n1_cov']:.2f} {'within' if r['orig_in_n5_envelope_on_cov'] else 'OUTSIDE'} n=5 envelope [{r['cov_range'][0]:.2f}, {r['cov_range'][1]:.2f}]")

    out = pathlib.Path("research_log/chunked_multiseed_summary.json")
    out.write_text(json.dumps({"rows": summary_rows}, indent=2))
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
