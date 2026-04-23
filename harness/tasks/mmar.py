"""MMAR audio reasoning task (arXiv 2505.13032).

1,000 audio-QA triplets with hierarchical reasoning layers:
  Signal → Perception → Semantic → Cultural

We stratify items by layer and run each layer as a separate Task so the
symbolic→perceptual axis is an empirical stratification, not an axis we
imposed post-hoc.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence

from ..models import MediaRef, Turn
from .base import Task, TaskClassFeatures, TaskItem

MMARLayer = Literal["signal", "perception", "semantic", "cultural"]

_FEATURES_BY_LAYER: dict[MMARLayer, TaskClassFeatures] = {
    # Signal: acoustic-level reasoning (pitch, pace, SNR, event detection)
    "signal": TaskClassFeatures(lexical_content=0, paralinguistic_content=2, spatial_layout=0, dynamic_ui=0),
    # Perception: perceptual categorization, speaker/music structure
    "perception": TaskClassFeatures(lexical_content=1, paralinguistic_content=2, spatial_layout=0, dynamic_ui=0),
    # Semantic: content-level QA, mostly lexical
    "semantic": TaskClassFeatures(lexical_content=2, paralinguistic_content=1, spatial_layout=0, dynamic_ui=0),
    # Cultural: world-knowledge + audio, mostly lexical
    "cultural": TaskClassFeatures(lexical_content=2, paralinguistic_content=1, spatial_layout=0, dynamic_ui=0),
}


class MMARTask(Task):
    modality = "audio"

    def __init__(self, data_dir: Path, layer: MMARLayer):
        self.data_dir = Path(data_dir)
        self.layer = layer
        self.name = f"mmar_{layer}"
        self.features = _FEATURES_BY_LAYER[layer]

    def load(self, n_items: int | None = None, seed: int = 0) -> Sequence[TaskItem]:
        raise NotImplementedError(
            "Load MMAR JSON from https://github.com/ddlBoJack/MMAR, filter by "
            "self.layer, seed-shuffle, truncate to n_items."
        )

    def turns_for(self, item: TaskItem, condition, pass_1_output=None):
        if condition == "C0":
            return [
                Turn(role="user", text=f"Listen to the audio and answer.\n\nQuestion: {item.question}\n\nAnswer:", media=item.media),
            ]
        if condition == "C1":
            if pass_1_output is None:
                return [
                    Turn(role="system", text="You are the perception pass. Transcribe the audio verbatim. Do not answer any question."),
                    Turn(role="user", text="Transcribe this audio clip verbatim.", media=item.media),
                ]
            return [
                Turn(role="user", text=_pass2_prompt(item.question, pass_1_output, rich=False)),
            ]
        if condition == "C2":
            if pass_1_output is None:
                return [
                    Turn(role="system", text=_load_schema("audio_uas.md")),
                    Turn(role="user", text="Produce the structured perception output for this audio clip.", media=item.media),
                ]
            return [
                Turn(role="user", text=_pass2_prompt(item.question, pass_1_output, rich=True)),
            ]
        raise ValueError(f"MMARTask does not support condition {condition}")

    def score(self, item: TaskItem, response_text: str) -> float:
        # Exact-match + normalized-edit-distance fallback; placeholder.
        ref = item.reference.strip().lower()
        hyp = response_text.strip().lower()
        if ref == hyp:
            return 1.0
        if ref in hyp:
            return 0.7
        return 0.0


def _pass2_prompt(question: str, pass_1: str, rich: bool) -> str:
    header = "Below is a structured perception of an audio clip." if rich else "Below is a transcript of an audio clip."
    return (
        f"{header} Answer the question using only the information below.\n\n"
        f"<perception>\n{pass_1}\n</perception>\n\n"
        f"Question: {question}\n\nAnswer:"
    )


def _load_schema(name: str) -> str:
    here = Path(__file__).resolve().parent.parent / "schemas" / name
    return here.read_text()
