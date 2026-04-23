"""Condition runners — C0 / C1 / C2 / C3.

The same adapter is used for both passes under the same-weights protocol;
a second adapter may be passed for Tier 2 cross-model cascades.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import DecodingParams, ModelAdapter
from .tasks import Condition, Task, TaskItem


@dataclass
class ConditionResult:
    condition: Condition
    score: float
    pass_1_output: str | None
    pass_2_output: str
    pass_1_tokens: int
    pass_2_tokens: int
    pass_1_latency_ms: int
    pass_2_latency_ms: int


def run_condition(
    task: Task,
    item: TaskItem,
    condition: Condition,
    perceive_model: ModelAdapter,
    reason_model: ModelAdapter | None = None,
    decoding: DecodingParams = DecodingParams(),
) -> ConditionResult:
    """Run a single (task, item, condition) cell.

    For C0, only `perceive_model` is used (end-to-end).
    For C1/C2/C3 same-weights, `reason_model` defaults to `perceive_model`.
    For Tier-2 decoupled cascades, pass a separate `reason_model`.
    """
    reason_model = reason_model or perceive_model

    if condition == "C0":
        turns = task.turns_for(item, "C0")
        r = perceive_model.call(turns, decoding)
        return ConditionResult(
            condition="C0",
            score=task.score(item, r.text),
            pass_1_output=None,
            pass_2_output=r.text,
            pass_1_tokens=0,
            pass_2_tokens=r.output_tokens,
            pass_1_latency_ms=0,
            pass_2_latency_ms=r.latency_ms,
        )

    # Pass 1 — perceive-and-transcribe
    p1_turns = task.turns_for(item, condition, pass_1_output=None)
    p1 = perceive_model.call(p1_turns, decoding)

    # Pass 2 — reason (text-only using Pass-1 output)
    p2_turns = task.turns_for(item, condition, pass_1_output=p1.text)
    p2 = reason_model.call(p2_turns, decoding)

    return ConditionResult(
        condition=condition,
        score=task.score(item, p2.text),
        pass_1_output=p1.text,
        pass_2_output=p2.text,
        pass_1_tokens=p1.output_tokens,
        pass_2_tokens=p2.output_tokens,
        pass_1_latency_ms=p1.latency_ms,
        pass_2_latency_ms=p2.latency_ms,
    )
