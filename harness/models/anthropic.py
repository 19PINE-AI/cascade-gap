"""Anthropic adapter — Claude Opus 4.7 / Sonnet 4.6.

Stub: the call() method is left as NotImplementedError so Phase-1 pilot
users see a clear error rather than silent fake data. Implement against the
`anthropic` SDK when ready.
"""
from __future__ import annotations

from typing import Sequence

from .base import DecodingParams, ModelAdapter, Modality, ModelResponse, Turn


class AnthropicAdapter(ModelAdapter):
    supports: frozenset[Modality] = frozenset({"text", "image"})

    def __init__(self, version: str = "claude-opus-4-7"):
        # Valid values at time of writing: claude-opus-4-7, claude-sonnet-4-6.
        # Claude does not support audio input as of 2026-04-23 — audio cells
        # in the model × modality matrix stay empty.
        self.version = version

    def call(self, turns: Sequence[Turn], decoding: DecodingParams) -> ModelResponse:
        raise NotImplementedError(
            "Implement against anthropic.Anthropic().messages.create(). "
            "Map Turn.role → role, Turn.text → text block, Turn.media → image block. "
            "Pass decoding.reasoning_mode through extended_thinking param."
        )
