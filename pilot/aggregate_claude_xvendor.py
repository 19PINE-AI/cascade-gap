"""Aggregate the within-Claude C0-vs-C1 cascade comparison across all cells that
have BOTH a Claude C0 (end-to-end) and a Claude C1 (cascade) score.

This is the Blocker-2 artifact: a complete within-vendor C0-vs-C1 comparison on
multiple cells for a second model family (Claude Opus 4.7), not just the single
Thermal cell. It reads judge_*_{C0_claude,C1_claude}.json (and falls back to
summary.json scores) from each paper run-dir, computes per-cell cascade deltas,
and runs a sign test on the direction.
"""
from __future__ import annotations
import json, math, pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"

# item_id -> (display name, page count)
CELLS = {
    "19720009221": ("Wagging Tail", 9),
    "19680000724": ("Env Test", 18),
    "19690008405": ("Dynamic Response", 41),
    "19690013408": ("Natural Vibration", 42),
    "19700023812": ("Thermal Analysis", 66),
    "19700025120": ("Heat Pipes", 104),
}


def find_run(item):
    hits = sorted(RUNS.glob(f"paper-review-{item}-*"))
    return hits[0] if hits else None


def read_score(rd, label):
    """Return (n_unsupported, coverage, n_covered, n_probes) for a label, or None."""
    jh = rd / f"judge_halluc_{label}.json"
    jp = rd / f"judge_probes_{label}.json"
    if jh.exists() and jp.exists():
        h = json.loads(jh.read_text()).get("n_unsupported")
        d = json.loads(jp.read_text())
        return (h, d.get("coverage"), d.get("n_covered"), d.get("n_probes"))
    # fallback: summary.json scores dict
    sp = rd / "summary.json"
    if sp.exists():
        sc = json.loads(sp.read_text()).get("scores", {}).get(label)
        if sc:
            return (sc.get("n_unsupported"), sc.get("probe_coverage"),
                    sc.get("n_covered"), sc.get("n_probes"))
    return None


def sign_test_p(n_pos, n_neg):
    """Two-sided exact binomial sign test p-value at q=0.5 (ties dropped)."""
    n = n_pos + n_neg
    if n == 0:
        return 1.0
    k = min(n_pos, n_neg)
    cdf = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * cdf)


def main():
    rows = []
    for item, (name, pp) in CELLS.items():
        rd = find_run(item)
        if rd is None:
            print(f"[skip] {name}: no run dir"); continue
        c0 = read_score(rd, "C0_claude")
        c1 = read_score(rd, "C1_claude")
        if c0 is None or c1 is None:
            print(f"[skip] {name}: C0={c0 is not None} C1={c1 is not None} (incomplete)")
            continue
        rows.append({
            "cell": name, "pp": pp,
            "C0_h": c0[0], "C0_cov": round(c0[1], 3),
            "C1_h": c1[0], "C1_cov": round(c1[1], 3),
            "d_h": c1[0] - c0[0], "d_cov": round(c1[1] - c0[1], 3),
            "n_probes": c0[3],
        })

    rows.sort(key=lambda r: r["pp"])
    print(f"\n{'cell':20s} {'pp':>4} {'C0 h/cov':>14} {'C1 h/cov':>14} {'dH':>5} {'dCov':>7}")
    for r in rows:
        print(f"{r['cell']:20s} {r['pp']:4d} "
              f"{r['C0_h']:>4}/{r['C0_cov']:<7.3f} {r['C1_h']:>4}/{r['C1_cov']:<7.3f} "
              f"{r['d_h']:>+5} {r['d_cov']:>+7.3f}")

    # direction stats (noise floor: |dh|<=1 and |dcov|<=0.04 treated as ties, per paper)
    h_imp = sum(1 for r in rows if r["d_h"] <= -1)
    h_wor = sum(1 for r in rows if r["d_h"] >= 1)
    cov_imp = sum(1 for r in rows if r["d_cov"] >= 0.04)
    cov_wor = sum(1 for r in rows if r["d_cov"] <= -0.04)
    n = len(rows)
    summary = {
        "n_cells": n,
        "halluc": {"improved": h_imp, "worse": h_wor,
                   "mean_delta": round(sum(r["d_h"] for r in rows) / n, 2),
                   "sign_p": round(sign_test_p(h_imp, h_wor), 4)},
        "coverage": {"improved": cov_imp, "worse": cov_wor,
                     "mean_delta": round(sum(r["d_cov"] for r in rows) / n, 3),
                     "sign_p": round(sign_test_p(cov_imp, cov_wor), 4)},
        "rows": rows,
    }
    print(f"\nHalluc:   improved {h_imp}/{n}, worse {h_wor}, mean d={summary['halluc']['mean_delta']}, "
          f"sign p={summary['halluc']['sign_p']}")
    print(f"Coverage: improved {cov_imp}/{n}, worse {cov_wor}, mean d={summary['coverage']['mean_delta']}, "
          f"sign p={summary['coverage']['sign_p']}")
    out = RUNS / "mechanism" / "claude_xvendor_within_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\n[wrote] {out}")


if __name__ == "__main__":
    main()
