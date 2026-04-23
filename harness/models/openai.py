"""OpenAI adapter — GPT-4o-audio-preview, GPT-5.x, o3/o4-mini.

Audio input uses the `gpt-4o-audio-preview` Chat Completions branch. Text
and vision use GPT-5.x. Reasoning-mode side study uses o-series.
"""
from __future__ import annotations

from typing import Sequence

from .base import DecodingParams, ModelAdapter, Modality, ModelResponse, Turn


class OpenAIAdapter(ModelAdapter):
    def __init__(self, version: str = "gpt-5"):
        self.version = version
        self.supports = self._supports_for_version(version)

    @staticmethod
    def _supports_for_version(v: str) -> frozenset[Modality]:
        if "audio" in v:
            return frozenset({"text", "audio"})
        if v.startswith("o"):
            return frozenset({"text"})  # o-series is text-reasoning-only
        return frozenset({"text", "image"})

    def call(self, turns: Sequence[Turn], decoding: DecodingParams) -> ModelResponse:
        raise NotImplementedError(
            "Implement against openai.OpenAI().chat.completions.create() for "
            "text/vision; use the audio variant of the same endpoint for audio "
            "inputs. Audio output pricing is $100/$200 per M tokens — enforce "
            "a hard per-call ceiling."
        )
