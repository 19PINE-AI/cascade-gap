"""Google Gemini adapter — 3.1 Pro / 3.1 Flash / 3.1 Flash-Lite.

Gemini 3.0 Pro and Flash were deprecated 2026-03-09; always use 3.1 variants.
Audio is natively supported on all three.
"""
from __future__ import annotations

from typing import Sequence

from .base import DecodingParams, ModelAdapter, Modality, ModelResponse, Turn


class GeminiAdapter(ModelAdapter):
    supports: frozenset[Modality] = frozenset({"text", "image", "audio", "video"})

    def __init__(self, version: str = "gemini-3.1-pro-preview"):
        valid = {
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-preview",
            "gemini-3.1-flash-lite-preview",
        }
        if version not in valid:
            raise ValueError(f"Unknown or deprecated Gemini version: {version}")
        self.version = version

    def call(self, turns: Sequence[Turn], decoding: DecodingParams) -> ModelResponse:
        raise NotImplementedError(
            "Implement against google.genai.Client().models.generate_content(). "
            "Gemini's thinking mode is controlled via the thinking_config param; "
            "map decoding.reasoning_mode accordingly."
        )
