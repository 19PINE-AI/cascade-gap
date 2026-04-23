"""Task interface.

A Task knows how to load its items, present each item to the model in the
three conditions (C0 / C1 / C2), and score a response. The Task does NOT
know about model vendors — it emits Turns that any adapter can consume.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Sequence

from ..models import MediaRef, Turn

Condition = Literal["C0", "C1", "C2", "C3"]
Modality = Literal["audio", "document", "gui"]


@dataclass(frozen=True)
class TaskItem:
    item_id: str
    media: Sequence[MediaRef]
    question: str
    reference: str  # gold answer or rubric anchor


@dataclass(frozen=True)
class TaskClassFeatures:
    """§4.6 predictive-rule features for this task.

    Values are 0 / 1 / 2 (absent / minor / dominant) so a logistic regression
    can train on them directly.
    """
    lexical_content: int
    paralinguistic_content: int
    spatial_layout: int
    dynamic_ui: int


class Task(ABC):
    name: str
    modality: Modality
    features: TaskClassFeatures

    @abstractmethod
    def load(self, n_items: int | None = None, seed: int = 0) -> Sequence[TaskItem]:
        ...

    @abstractmethod
    def turns_for(self, item: TaskItem, condition: Condition, pass_1_output: str | None = None) -> Sequence[Turn]:
        """Return the Turns to send the model.

        For C1/C2/C3 Pass 2, pass_1_output contains the structured text from
        the earlier perception pass.
        """
        ...

    @abstractmethod
    def score(self, item: TaskItem, response_text: str) -> float:
        """Return a per-item score in [0, 1]."""
        ...
