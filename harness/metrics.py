"""Aggregation and the §6 Phase-1 decision gate."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, stdev

from .conditions import ConditionResult


@dataclass
class CellSummary:
    task: str
    model: str
    condition: str
    n: int
    score_mean: float
    score_ci95: float  # half-width of 95% CI = 1.96 * σ / √n
    mean_pass_1_tokens: float
    mean_pass_2_tokens: float
    mean_latency_ms: float


def summarize(task: str, model: str, condition: str, results: list[ConditionResult]) -> CellSummary:
    n = len(results)
    scores = [r.score for r in results]
    sd = stdev(scores) if n > 1 else 0.0
    ci = 1.96 * sd / max(1, n) ** 0.5
    return CellSummary(
        task=task,
        model=model,
        condition=condition,
        n=n,
        score_mean=mean(scores),
        score_ci95=ci,
        mean_pass_1_tokens=mean(r.pass_1_tokens for r in results),
        mean_pass_2_tokens=mean(r.pass_2_tokens for r in results),
        mean_latency_ms=mean(r.pass_1_latency_ms + r.pass_2_latency_ms for r in results),
    )


def cascade_gap(c0: CellSummary, c1: CellSummary) -> float:
    """Δ = Acc_cascade − Acc_end-to-end (signed)."""
    assert c0.condition == "C0" and c1.condition == "C1"
    return c1.score_mean - c0.score_mean


def phase1_gate(per_task_gaps: list[float], threshold: float = 0.03, min_tasks: int = 2) -> bool:
    """§6 Phase-1 decision gate.

    "Do C0 and C1 differ by ≥3 points on at least 2 of 6 pilot tasks per
    modality, in either direction?"
    """
    hits = sum(1 for g in per_task_gaps if abs(g) >= threshold)
    return hits >= min_tasks
