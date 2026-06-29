"""Aggregate the within-Gemini-2.5-Flash C0-vs-C1 audio comparison: a clean,
full-quality, no-bitrate-confound cross-model audio test, reusing the shared
Gemini-3.1-Pro reference + probes and the GPT-5.4 judge. Reads
judge_*_{C0_flash25,C1_flash25}.json from each audio run-dir and computes
per-cell cascade deltas + a sign test, alongside the headline Pro numbers."""
from __future__ import annotations
import json, math, pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"

# cell display name -> (run-dir glob, minutes, headline Pro C0/C1 for reference)
CELLS = [
    ("3B1B Attention",   "audio-review-3b1b_attention-*",     26),
    ("MIT 6.034",        "audio-review-mit_6034_winston-*",    47),
    ("Karpathy",         "audio-review-karpathy_sogpt-*",      42),
    ("NeurIPS panel",    "audio-review-neurips_black_in_ai-*",  31),
    ("Harvard Moot",     "audio-review-harvard_moot_court-*",   82),
]


def read_score(rd, label):
    jh = rd / f"judge_halluc_{label}.json"
    jp = rd / f"judge_probes_{label}.json"
    if jh.exists() and jp.exists():
        return (json.loads(jh.read_text()).get("n_unsupported"),
                json.loads(jp.read_text()).get("coverage"))
    sp = rd / "summary.json"
    if sp.exists():
        sc = json.loads(sp.read_text()).get("scores", {}).get(label)
        if sc:
            return (sc.get("n_unsupported"), sc.get("probe_coverage"))
    return None


def sign_p(pos, neg):
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    rows = []
    for name, glob, mins in CELLS:
        hits = sorted(RUNS.glob(glob))
        if not hits:
            print(f"[skip] {name}: no run dir"); continue
        rd = hits[0]
        c0 = read_score(rd, "C0_flash25")
        c1 = read_score(rd, "C1_flash25")
        if c1 is None:
            print(f"[skip] {name}: no C1_flash25"); continue
        rows.append({"cell": name, "min": mins,
                     "C0_h": (c0[0] if c0 else None), "C0_cov": (round(c0[1], 3) if c0 else None),
                     "C1_h": c1[0], "C1_cov": round(c1[1], 3),
                     "d_h": (c1[0] - c0[0] if c0 else None),
                     "d_cov": (round(c1[1] - c0[1], 3) if c0 else None)})

    rows.sort(key=lambda r: r["min"])
    print(f"\n{'cell':18s} {'min':>4} {'C0 h/cov':>14} {'C1 h/cov':>14} {'dH':>5} {'dCov':>7}")
    for r in rows:
        c0s = f"{r['C0_h']}/{r['C0_cov']:.3f}" if r["C0_h"] is not None else "-- (skip)"
        print(f"{r['cell']:18s} {r['min']:4d} {c0s:>14} {r['C1_h']:>4}/{r['C1_cov']:<7.3f} "
              f"{(('%+d'%r['d_h']) if r['d_h'] is not None else '--'):>5} "
              f"{(('%+.3f'%r['d_cov']) if r['d_cov'] is not None else '--'):>7}")

    paired = [r for r in rows if r["d_h"] is not None]
    h_imp = sum(1 for r in paired if r["d_h"] <= -1)
    h_wor = sum(1 for r in paired if r["d_h"] >= 1)
    cov_imp = sum(1 for r in paired if r["d_cov"] >= 0.04)
    cov_wor = sum(1 for r in paired if r["d_cov"] <= -0.04)
    n = len(paired)
    summary = {"model": "gemini-2.5-flash", "n_paired_cells": n,
               "halluc": {"improved": h_imp, "worse": h_wor,
                          "mean_delta": round(sum(r["d_h"] for r in paired) / n, 2) if n else None,
                          "sign_p": round(sign_p(h_imp, h_wor), 4)},
               "coverage": {"improved": cov_imp, "worse": cov_wor,
                            "mean_delta": round(sum(r["d_cov"] for r in paired) / n, 3) if n else None,
                            "sign_p": round(sign_p(cov_imp, cov_wor), 4)},
               "rows": rows}
    print(f"\nHalluc:   improved {h_imp}/{n}, worse {h_wor}, mean d={summary['halluc']['mean_delta']}, sign p={summary['halluc']['sign_p']}")
    print(f"Coverage: improved {cov_imp}/{n}, worse {cov_wor}, mean d={summary['coverage']['mean_delta']}, sign p={summary['coverage']['sign_p']}")
    out = RUNS / "mechanism" / "flash25_xmodel_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\n[wrote] {out}")


if __name__ == "__main__":
    main()
