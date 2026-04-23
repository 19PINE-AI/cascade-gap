"""HuggingFace open-weight adapter — Qwen3-Omni, Step-Audio-R1.1, UI-TARS-2.

Runs inference locally via transformers / vLLM. The model registry below
captures modality support and the HF path; Phase-1 implementer wires in the
specific chat templates per model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .base import DecodingParams, ModelAdapter, Modality, ModelResponse, Turn


@dataclass(frozen=True)
class HFModelSpec:
    hf_path: str
    supports: frozenset[Modality]
    dtype: str = "bfloat16"
    tp_size: int = 1  # tensor parallel


REGISTRY: dict[str, HFModelSpec] = {
    "qwen3_omni_30b": HFModelSpec(
        hf_path="Qwen/Qwen3-Omni-30B-A3B-Instruct",
        supports=frozenset({"text", "image", "audio", "video"}),
        tp_size=2,
    ),
    "qwen25_omni_7b": HFModelSpec(
        hf_path="Qwen/Qwen2.5-Omni-7B",
        supports=frozenset({"text", "image", "audio", "video"}),
    ),
    "step_audio_r1_1": HFModelSpec(
        hf_path="stepfun-ai/Step-Audio-R1.1",
        supports=frozenset({"text", "audio"}),
    ),
    "ui_tars_2_72b_dpo": HFModelSpec(
        hf_path="ByteDance-Seed/UI-TARS-72B-DPO",
        supports=frozenset({"text", "image"}),
        tp_size=4,
    ),
    "ui_tars_2_7b_dpo": HFModelSpec(
        hf_path="ByteDance-Seed/UI-TARS-7B-DPO",
        supports=frozenset({"text", "image"}),
    ),
}


class HFAdapter(ModelAdapter):
    def __init__(self, short_name: str):
        if short_name not in REGISTRY:
            raise ValueError(f"Unknown HF model short name: {short_name}")
        spec = REGISTRY[short_name]
        self.version = spec.hf_path
        self.supports = spec.supports
        self._spec = spec

    def call(self, turns: Sequence[Turn], decoding: DecodingParams) -> ModelResponse:
        raise NotImplementedError(
            "Implement against transformers or vLLM. Per-model chat templates "
            "and multimodal preprocessors differ; see each model's HF card."
        )
