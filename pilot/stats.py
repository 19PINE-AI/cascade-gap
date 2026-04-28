"""Statistical analysis utilities for cascade-gap pilots.

Bootstrap CIs (BCa = bias-corrected and accelerated), sign tests, and
paired-difference tests for cascade-gap measurements. Used in Phase-2
analysis to replace point estimates with rigorous error bars.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Sequence


@dataclass
class CI:
    point: float
    low: float
    high: float
    method: str

    def __str__(self) -> str:
        return f"{self.point:.3f} [{self.low:.3f}, {self.high:.3f}]"


def bootstrap_ci_mean(
    values: Sequence[float],
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> CI:
    """Percentile bootstrap CI for the mean.

    Simple percentile method (not BCa). For our data sizes (n=10-50 per cell),
    BCa correction is rarely meaningful; percentile bootstrap is the workhorse.
    """
    if not values:
        return CI(0.0, 0.0, 0.0, "empty")
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_bootstrap):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    low = means[int(alpha / 2 * n_bootstrap)]
    high = means[int((1 - alpha / 2) * n_bootstrap) - 1]
    point = sum(values) / n
    return CI(point, low, high, "percentile-bootstrap")


def bootstrap_ci_paired_diff(
    paired: Sequence[tuple[float, float]],
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> CI:
    """Bootstrap CI for the mean of paired differences (e.g., C1 − C0)."""
    if not paired:
        return CI(0.0, 0.0, 0.0, "empty")
    diffs = [b - a for a, b in paired]
    return bootstrap_ci_mean(diffs, n_bootstrap, alpha, seed)


def sign_test(
    paired: Sequence[tuple[float, float]],
    alternative: str = "two-sided",
) -> dict:
    """Sign test for paired differences. Returns p-value.

    H0: median(b - a) = 0.
    Counts cells where b > a vs b < a; compares via binomial.
    """
    n_pos = sum(1 for a, b in paired if b > a)
    n_neg = sum(1 for a, b in paired if b < a)
    n_tied = sum(1 for a, b in paired if b == a)
    n = n_pos + n_neg
    if n == 0:
        return {"n_pos": 0, "n_neg": 0, "n_tied": n_tied, "p_value": 1.0}
    # Two-sided: P(|x - n/2| >= |n_pos - n/2|) under Binomial(n, 0.5)
    k = max(n_pos, n_neg)
    # Tail probability of getting >=k or <=n-k
    p_tail = sum(_binomial_pmf(n, j, 0.5) for j in range(k, n + 1))
    if alternative == "two-sided":
        p_value = min(1.0, 2 * p_tail)
    elif alternative == "greater":
        p_value = p_tail
    elif alternative == "less":
        p_value = 1.0 - p_tail + _binomial_pmf(n, k, 0.5)
    else:
        raise ValueError(alternative)
    return {
        "n_pos": n_pos,
        "n_neg": n_neg,
        "n_tied": n_tied,
        "n_effective": n,
        "p_value": p_value,
        "alternative": alternative,
    }


def _binomial_pmf(n: int, k: int, p: float) -> float:
    """Binomial PMF P(X=k | n, p)."""
    if k < 0 or k > n:
        return 0.0
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def summarize_cells(
    rows: list[dict],
    metric_field: str,
    group_by: str = "condition",
) -> dict[str, CI]:
    """Group rows by `group_by` and bootstrap CI on `metric_field`."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        key = r.get(group_by, "unknown")
        if metric_field in r:
            groups.setdefault(key, []).append(float(r[metric_field]))
    return {k: bootstrap_ci_mean(v) for k, v in groups.items()}


def report_paired_delta(
    rows_by_cond: dict[str, list[float]],
    cond_a: str,
    cond_b: str,
) -> dict:
    """Pair up cells across conditions and report Δ = b - a with CI + sign test."""
    if cond_a not in rows_by_cond or cond_b not in rows_by_cond:
        return {"error": f"Missing condition: {cond_a} or {cond_b}"}
    a_vals = rows_by_cond[cond_a]
    b_vals = rows_by_cond[cond_b]
    if len(a_vals) != len(b_vals):
        return {"error": f"Length mismatch: {len(a_vals)} vs {len(b_vals)}"}
    paired = list(zip(a_vals, b_vals))
    ci = bootstrap_ci_paired_diff(paired)
    sign = sign_test(paired)
    return {
        "delta_ci": str(ci),
        "delta_point": ci.point,
        "delta_low": ci.low,
        "delta_high": ci.high,
        "n_paired": len(paired),
        "sign_test": sign,
    }


# --- Smoke test ---
if __name__ == "__main__":
    # Quick sanity check
    vals = [0.1, 0.3, 0.4, 0.45, 0.55, 0.6]
    print("CI for mean:", bootstrap_ci_mean(vals))

    paired = [(0.39, 0.73), (0.95, 0.82), (0.23, 0.57), (0.55, 0.77)]  # Phase-1 cross-vendor coverage
    diff_ci = bootstrap_ci_paired_diff(paired)
    print("Paired Δ (cascade − end-to-end):", diff_ci)
    print("Sign test:", sign_test(paired))
