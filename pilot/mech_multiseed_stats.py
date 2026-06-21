"""V2 statistics: paired Wilcoxon, bootstrap CIs, mixed-effects, TOST equivalence.

Reads runs/mechanism/multiseed_summary.json (cell, cond, seed, coverage, n_unsupported, [error]).
Key contrasts (per-cell seed-means -> paired across cells):
  - E2 (single-call) vs C1: coverage collapse + review-failure rate.
  - E1 (C1+ both) vs C1: coverage (TOST equivalence, SESOI=0.04) + hallucinations.
Plus a seed-level mixed-effects model coverage ~ cond + (1|cell), and per-condition
synthesis (seed) variance. Writes multiseed_stats.json.
"""
from __future__ import annotations
import json, pathlib, statistics as st
import numpy as np
from scipy import stats

MECH = pathlib.Path(__file__).resolve().parent.parent / "runs" / "mechanism"
rows = json.loads((MECH / "multiseed_summary.json").read_text())

cells = sorted({r["cell"] for r in rows})
conds = ["C1", "E1", "E2"]

def seedvals(cell, cond, key):
    return [r[key] for r in rows if r["cell"] == cell and r["cond"] == cond and key in r and "error" not in r]

def cellmean(cell, cond, key):
    v = seedvals(cell, cond, key)
    return float(np.mean(v)) if v else None

def failures(cell, cond):
    return sum(1 for r in rows if r["cell"] == cell and r["cond"] == cond and "error" in r)

def boot_ci(d, n=10000, seed=0):
    d = np.asarray([x for x in d if x is not None], float)
    if len(d) < 2: return [None, None]
    rng = np.random.default_rng(seed)
    bs = [np.mean(rng.choice(d, len(d), replace=True)) for _ in range(n)]
    return [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]

def tost(diffs, sesoi, alpha=0.05):
    d = np.asarray([x for x in diffs if x is not None], float)
    n = len(d)
    if n < 2: return {"equivalent": None, "n": n}
    m, se = float(np.mean(d)), float(stats.sem(d))
    # 90% CI for alpha=0.05 TOST
    t = stats.t.ppf(1 - alpha, n - 1)
    lo, hi = m - t * se, m + t * se
    return {"mean_diff": round(m, 4), "ci90": [round(lo, 4), round(hi, 4)], "sesoi": sesoi,
            "equivalent": bool(lo > -sesoi and hi < sesoi), "n": n}

def paired_contrast(a, b, key, sesoi=None):
    """a vs b on key, paired across cells (per-cell seed means)."""
    A, B, diffs = [], [], []
    for c in cells:
        ma, mb = cellmean(c, a, key), cellmean(c, b, key)
        if ma is not None and mb is not None:
            A.append(ma); B.append(mb); diffs.append(ma - mb)
    out = {"contrast": f"{a}-vs-{b}", "key": key, "n_pairs": len(diffs),
           "mean_a": round(float(np.mean(A)), 4) if A else None,
           "mean_b": round(float(np.mean(B)), 4) if B else None,
           "mean_diff": round(float(np.mean(diffs)), 4) if diffs else None,
           "boot_ci95": boot_ci(diffs),
           "n_a_worse": int(sum(1 for d in diffs if d < 0)),
           "n_a_better": int(sum(1 for d in diffs if d > 0))}
    if len(diffs) >= 6 and any(diffs):
        try:
            w = stats.wilcoxon(A, B)
            out["wilcoxon_p"] = round(float(w.pvalue), 5)
        except Exception as e:
            out["wilcoxon_p"] = f"err:{e}"
        out["sign_test_p"] = round(float(stats.binomtest(sum(1 for d in diffs if d>0), len(diffs)).pvalue), 5)
    if sesoi is not None:
        out["tost"] = tost(diffs, sesoi)
    return out

def synth_variance():
    out = {}
    for cond in conds:
        sds = []
        for c in cells:
            v = seedvals(c, cond, "coverage")
            if len(v) >= 2: sds.append(st.stdev(v))
        out[cond] = {"mean_within_cell_seed_sd_coverage": round(float(np.mean(sds)), 4) if sds else None,
                     "n_cells_with>=2_seeds": len(sds)}
    return out

def mixed_effects():
    try:
        import statsmodels.formula.api as smf, pandas as pd
        recs = [{"cov": r["coverage"], "cond": r["cond"], "cell": r["cell"]}
                for r in rows if "coverage" in r and "error" not in r]
        df = pd.DataFrame(recs)
        df["cond"] = df["cond"].astype("category")
        # C1 as reference
        df["cond"] = df["cond"].cat.reorder_categories([c for c in ["C1","E1","E2"] if c in set(df["cond"])])
        m = smf.mixedlm("cov ~ C(cond, Treatment('C1'))", df, groups=df["cell"]).fit(reml=False)
        return {str(k): round(float(v), 4) for k, v in m.params.items()} | \
               {"pvalues": {str(k): round(float(v), 5) for k, v in m.pvalues.items()}}
    except Exception as e:
        return {"error": str(e)[:200]}

# E2 review-failure (budget/format) rate per condition
e2_fail = {c: failures(c, "E2") for c in cells}
e2_fail_cells = {c: n for c, n in e2_fail.items() if n > 0}

result = {
    "n_cells": len(cells), "n_rows": len(rows),
    "seeds_per_cell_cond": {cond: round(float(np.mean([len(seedvals(c, cond, "coverage")) for c in cells])), 2) for cond in conds},
    "coverage_contrasts": {
        "E2_vs_C1": paired_contrast("E2", "C1", "coverage"),
        "E1_vs_C1": paired_contrast("E1", "C1", "coverage", sesoi=0.04),
    },
    "halluc_contrasts": {
        "E1_vs_C1": paired_contrast("E1", "C1", "n_unsupported"),
    },
    "E2_review_failures": {"cells_with_failures": e2_fail_cells,
                           "total_failed_runs": int(sum(e2_fail.values()))},
    "synthesis_variance": synth_variance(),
    "mixed_effects_coverage": mixed_effects(),
}
(MECH / "multiseed_stats.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
print(f"\n[wrote] {MECH/'multiseed_stats.json'}")
