"""Model adapter interface.

Every adapter exposes the same call surface regardless of vendor. This lets
conditions.py switch between same-weights passes and cross-model passes
without branching on provider.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Sequence

Modality = Literal["text", "image", "audio", "video"]


@dataclass(frozen=True)
class MediaRef:
    """Reference to a media input. Either a local path or a URL.

    The adapter is responsible for turning this into the vendor-specific
    upload or base64 encoding. `modality` lets the adapter validate support.
    """
    modality: Modality
    path_or_url: str
    mime: str | None = None  # e.g. "audio/wav", "image/png"


@dataclass(frozen=True)
class Turn:
    """One turn in the conversation.

    Multimodal content is ordered: text + media are interleaved in the
    order the caller wants the model to see them.
    """
    role: Literal["system", "user", "assistant"]
    text: str = ""
    media: Sequence[MediaRef] = field(default_factory=tuple)


@dataclass(frozen=True)
class DecodingParams:
    """Decoding parameters. Identity across conditions is a §4.4 control."""
    temperature: float = 0.0
    top_p: float = 1.0
    max_output_tokens: int = 2048
    reasoning_mode: bool = False  # Opus/Gemini thinking, o-series reasoning
    seed: int | None = None


@dataclass
class ModelResponse:
    text: str
    output_tokens: int
    input_tokens: int
    latency_ms: int
    raw: dict  # vendor-native response for audits
    cached: bool = False


class ModelAdapter(ABC):
    """Abstract base. Every concrete adapter pins its model version."""

    version: str  # e.g. "claude-opus-4-7", "gemini-3.1-pro-preview"
    supports: frozenset[Modality]

    @abstractmethod
    def call(self, turns: Sequence[Turn], decoding: DecodingParams) -> ModelResponse:
        ...

    def supports_modality(self, m: Modality) -> bool:
        return m in self.supports
