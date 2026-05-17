"""Phase-3 statistical analyses on the existing cells.

Outputs:
  - Wilson 95% CIs for every (cell, condition) coverage rate.
  - Bootstrap 95% CIs for the mean Δ_cov across cells (with and without
    meeting-minutes cells; sign test against zero).
  - Bootstrap 95% CIs for Pearson r between C0 baseline and Δ_cov.
  - Held-out predictor: logistic regression on cell features (now including
    citation-surface-form density per 1k transcript words) predicting
    sign(Δ_cov > 0); LOOCV AUC.
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
DATA = json.loads((REPO / "paper/figures/phase3_data.json").read_text())


# Citation-surface-form regexes (mirror citation_strip.py)
_CITE_RE = [
    re.compile(r"\[\s*\d+(?:\s*[-–,]\s*\d+)*\s*\]"),
    re.compile(r"\b(?:references?|refs?\.?)\s+\d+(?:\s*(?:[-–,]|\band\b)\s*\d+)*",
               re.IGNORECASE),
]


def citation_density_per_1k(run_dir: pathlib.Path) -> float:
    """Count citation surface forms per 1k words in transcript_C1_pass1.txt.
    Returns 0.0 if the transcript is missing (e.g., audio cells where C1 Pass-1
    is an ASR transcript with no formal citations).
    """
    t = run_dir / "transcript_C1_pass1.txt"
    if not t.exists():
        return 0.0
    text = t.read_text()
    n_words = max(1, len(text.split()))
    n_cites = sum(len(p.findall(text)) for p in _CITE_RE)
    return n_cites * 1000.0 / n_words


# ----------------------------------------------------------------------
# Wilson interval — exact closed form for binomial proportion.
# ----------------------------------------------------------------------
def wilson_ci(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score 95% CI for a binomial proportion k/n.
    Returns (low, high). Handles k=0 and k=n correctly.
    """
    if n == 0:
        return (0.0, 1.0)
    z = 1.959963984540054  # 2.5/97.5 normal
    phat = k / n
    denom = 1 + z**2 / n
    center = phat + z**2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    low = (center - margin) / denom
    high = (center + margin) / denom
    return (max(0.0, low), min(1.0, high))


# ----------------------------------------------------------------------
# Bootstrap helpers (percentile method; seeded).
# ----------------------------------------------------------------------
def bootstrap_mean(x, n_boot: int = 10_000, seed: int = 42) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    arr = np.asarray(x, dtype=float)
    n = len(arr)
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    idx = rng.integers(0, n, size=(n_boot, n))
    means = arr[idx].mean(axis=1)
    return float(arr.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def bootstrap_pearson_r(x, y, n_boot: int = 10_000, seed: int = 42):
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    rs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        xs, ys = x[idx], y[idx]
        if xs.std() == 0 or ys.std() == 0:
            continue
        rs.append(np.corrcoef(xs, ys)[0, 1])
    rs = np.array(rs)
    point = float(np.corrcoef(x, y)[0, 1])
    return point, float(np.percentile(rs, 2.5)), float(np.percentile(rs, 97.5)), float((rs >= 0).mean())


def sign_test_p(paired):
    """Two-sided sign test (binomial against H0: P(+)=0.5)."""
    pos = sum(1 for a, b in paired if b > a)
    neg = sum(1 for a, b in paired if b < a)
    n = pos + neg
    if n == 0:
        return 1.0
    k = max(pos, neg)
    # two-sided
    p = 0.0
    for j in range(k, n + 1):
        p += math.comb(n, j) * 0.5 ** n
    return min(1.0, 2 * p)


# ----------------------------------------------------------------------
# Build the cells table.
# ----------------------------------------------------------------------
def build_cells():
    rows = []
    for c in DATA["cells"]:
        s = c["scores"]
        n_probes = s["C0"]["n_probes"]
        for cond in s:
            sc = s[cond]
            rows.append({
                "cell": c["cell"],
                "modality": c.get("modality"),
                "task": c.get("task"),
                "source_words": c.get("source_words"),
                "page_count": c.get("page_count"),
                "condition": cond,
                "n_unsupported": sc["n_unsupported"],
                "n_probes": sc["n_probes"],
                "n_covered": sc["n_covered"],
                "coverage": sc["probe_coverage"],
            })
    return rows


def coverage_table_with_wilson():
    """Print one row per (cell, condition) with k/n + Wilson CI."""
    rows = build_cells()
    print("\n=== Wilson 95% CI on probe coverage (per cell × condition) ===")
    print(f"{'cell':<22} {'condition':<28} {'covered/n':>10}  {'cov':>5}  {'95% CI':>16}")
    for r in rows:
        low, high = wilson_ci(r["n_covered"], r["n_probes"])
        kn = f"{r['n_covered']}/{r['n_probes']}"
        print(
            f"{r['cell'][:22]:<22} {r['condition'][:28]:<28} {kn:>10}  "
            f"{r['coverage']:.3f}  [{low:.3f}, {high:.3f}]"
        )
    return rows


def figure1_analysis(rows):
    """Inverse correlation r and CIs for Gemini base cells.
    Returns (full_n9, excluding_mtgmin).
    """
    print("\n=== Figure 1 (inverse correlation) bootstrap r CI ===")
    base = {}
    for r in rows:
        if r["condition"] in ("C0", "C1"):
            base.setdefault(r["cell"], {})[r["condition"]] = r
    cells = []
    for name, conds in base.items():
        if "C0" in conds and "C1" in conds:
            c0 = conds["C0"]["coverage"]
            c1 = conds["C1"]["coverage"]
            cells.append((name, c0, c1, c1 - c0))
    cells.sort(key=lambda c: c[1])
    xs = np.array([c[1] for c in cells])
    ys = np.array([c[3] for c in cells])
    r, lo, hi, p_geq0 = bootstrap_pearson_r(xs, ys)
    print(f"All n={len(cells)} cells:  r={r:.3f}  95% CI [{lo:.3f}, {hi:.3f}]  fraction(r>=0)={p_geq0:.3f}")

    keep = [c for c in cells if "mtg-min" not in c[0]]
    xs2 = np.array([c[1] for c in keep])
    ys2 = np.array([c[3] for c in keep])
    if len(keep) >= 3:
        r2, lo2, hi2, p2 = bootstrap_pearson_r(xs2, ys2)
        print(f"Without mtg-min n={len(keep)}:  r={r2:.3f}  95% CI [{lo2:.3f}, {hi2:.3f}]  fraction(r>=0)={p2:.3f}")
    return cells


def mean_delta_test(rows):
    """Bootstrap CI for mean Δ_cov, mean Δ_halluc, and sign tests."""
    print("\n=== Bootstrap CIs for mean cascade effects (Gemini base cells) ===")
    base = {}
    for r in rows:
        if r["condition"] in ("C0", "C1"):
            base.setdefault(r["cell"], {})[r["condition"]] = r
    paired_cov = []
    paired_halluc = []
    for name, conds in base.items():
        if "C0" in conds and "C1" in conds:
            paired_cov.append((conds["C0"]["coverage"], conds["C1"]["coverage"]))
            paired_halluc.append((conds["C0"]["n_unsupported"], conds["C1"]["n_unsupported"]))
    d_cov = [b - a for a, b in paired_cov]
    d_h = [b - a for a, b in paired_halluc]
    m_cov, lo_cov, hi_cov = bootstrap_mean(d_cov)
    m_h, lo_h, hi_h = bootstrap_mean(d_h)
    print(f"Δ_cov   mean = {m_cov:+.3f}  95% CI [{lo_cov:+.3f}, {hi_cov:+.3f}]  "
          f"sign-test p = {sign_test_p(paired_cov):.4f}  (n={len(paired_cov)})")
    print(f"Δ_halluc mean = {m_h:+.2f}  95% CI [{lo_h:+.2f}, {hi_h:+.2f}]  "
          f"sign-test p = {sign_test_p(paired_halluc):.4f}  (n={len(paired_halluc)})")


# ----------------------------------------------------------------------
# Held-out predictor.
# ----------------------------------------------------------------------
def held_out_predictor():
    """Predict sign(cascade_helps) from cell features via LOOCV.

    Two prediction tasks:
      A. sign(Δ_cov > 0)   — does cascade improve coverage at all?
      B. sign(Δ_cov > +noise_floor or Δ_halluc < -noise_floor) — substantive win on either axis.

    Features tested:
      - baseline_cov (C0 probe coverage)
      - log10 source_words
      - baseline_halluc (C0 unsupported claims)
      - modality dummy (1=paper, 0=audio)
      - citation surface forms per 1k transcript words (Mode-B trigger)
    """
    print("\n=== Held-out predictor (logistic regression, LOOCV) ===")
    X = []
    y_pos = []        # Δ_cov > 0
    y_strict = []     # |Δ_cov| > 0.04 OR |Δ_halluc| > 1 in cascade-favorable direction
    names = []
    for c in DATA["cells"]:
        s = c["scores"]
        if "C0" not in s or "C1" not in s:
            continue
        c0 = s["C0"]["probe_coverage"]
        c1 = s["C1"]["probe_coverage"]
        h0 = s["C0"]["n_unsupported"]
        h1 = s["C1"]["n_unsupported"]
        sw = c.get("source_words") or 1
        modality_p = 1 if c.get("modality") == "paper" else 0
        run_dir = REPO / c.get("run_dir", "")
        cite_density = citation_density_per_1k(run_dir) if run_dir.exists() else 0.0
        X.append([c0, math.log10(sw), h0, modality_p, cite_density])
        y_pos.append(1 if (c1 - c0) > 0 else 0)
        # Strict cascade win: improves on at least one axis outside noise floor, and not worse on the other.
        d_cov = c1 - c0
        d_h = h1 - h0
        cov_better = d_cov > 0.04
        cov_worse = d_cov < -0.04
        h_better = d_h < -1
        h_worse = d_h > 1
        win = (cov_better or h_better) and not (cov_worse or h_worse)
        y_strict.append(1 if win else 0)
        names.append(c["cell"])

    X = np.array(X)
    feat_names = ["C0_cov", "log10_words", "C0_halluc", "is_paper", "cite_density_per1k"]
    n = len(X)

    for task_label, y in [("sign(Δ_cov > 0)", np.array(y_pos)),
                          ("strict cascade win (outside noise on either axis)", np.array(y_strict))]:
        print(f"\n  Task: {task_label}")
        print(f"  n={n}  positive class: {y.sum()}/{n}")
        if y.sum() in (0, n):
            print("  cannot fit predictor: single-class outcome")
            continue
        # Leave-one-out CV
        preds = np.zeros(n, dtype=float)
        for i in range(n):
            mask = np.ones(n, dtype=bool)
            mask[i] = False
            if y[mask].sum() in (0, mask.sum()):
                preds[i] = float(y.mean())  # marginal probability
                continue
            lr = LogisticRegression(max_iter=2000, solver="lbfgs")
            lr.fit(X[mask], y[mask])
            preds[i] = lr.predict_proba(X[i:i + 1])[0, 1]
        try:
            auc = roc_auc_score(y, preds)
        except Exception:
            auc = float("nan")
        thresh = 0.5
        correct = ((preds > thresh).astype(int) == y).mean()
        # majority-baseline accuracy
        maj = max(y.mean(), 1 - y.mean())
        print(f"  LOOCV AUC = {auc:.3f}   accuracy = {correct:.3f} (majority baseline = {maj:.3f})")
        # Fit one model on full data for coefficient inspection
        lr_full = LogisticRegression(max_iter=2000, solver="lbfgs")
        lr_full.fit(X, y)
        coefs = dict(zip(feat_names, lr_full.coef_[0]))
        print(f"  full-fit coefs: " + ", ".join(f"{k}={v:+.3f}" for k, v in coefs.items()))
        # Show only negative-class cells (the interesting ones)
        print("  negative-class cells (cascade did NOT win):")
        for nm, xi, yi, pi in zip(names, X, y, preds):
            if yi == 0:
                tag = "MISS" if pi > thresh else "HIT"
                print(
                    f"    [{tag}] {nm[:22]:<22}  C0={xi[0]:.3f}  "
                    f"log10_sw={xi[1]:.3f}  h0={int(xi[2])}  paper={int(xi[3])}  "
                    f"cite/1k={xi[4]:.2f}  pred={pi:.3f}"
                )

    # Also report a no-cite-density baseline so we can show what the new feature buys.
    print("\n=== Predictor ablation: 4-feature baseline (no cite density) ===")
    X4 = X[:, :4]
    for task_label, y in [("sign(Δ_cov > 0)", np.array(y_pos)),
                          ("strict cascade win", np.array(y_strict))]:
        if y.sum() in (0, n):
            continue
        preds = np.zeros(n, dtype=float)
        for i in range(n):
            mask = np.ones(n, dtype=bool); mask[i] = False
            if y[mask].sum() in (0, mask.sum()):
                preds[i] = float(y.mean()); continue
            lr = LogisticRegression(max_iter=2000, solver="lbfgs")
            lr.fit(X4[mask], y[mask])
            preds[i] = lr.predict_proba(X4[i:i + 1])[0, 1]
        try:
            auc4 = roc_auc_score(y, preds)
        except Exception:
            auc4 = float("nan")
        acc4 = ((preds > 0.5).astype(int) == y).mean()
        print(f"  {task_label}:  LOOCV AUC = {auc4:.3f}  accuracy = {acc4:.3f}")


def main():
    rows = coverage_table_with_wilson()
    figure1_analysis(rows)
    mean_delta_test(rows)
    held_out_predictor()


if __name__ == "__main__":
    main()
