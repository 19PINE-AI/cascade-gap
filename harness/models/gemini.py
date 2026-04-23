"""Google Gemini adapter — 3.1 Pro / 3.1 Flash-Lite.

Uses google-genai's Client.models.generate_content with inline Blob parts
for audio and images. The Gemini API accepts raw bytes up to 20 MB per
Part; for larger files use the Files API (not wired here yet).

Live models ("gemini-3.1-flash-live-preview") use a different WebSocket
surface and are out of scope for the synchronous pilot.
"""
from __future__ import annotations

import mimetypes
import os
import time
from pathlib import Path
from typing import Sequence

from google import genai
from google.genai import types

from .base import DecodingParams, ModelAdapter, Modality, ModelResponse, Turn

# Models verified via client.models.list() on 2026-04-23 (post-3.0 deprecation)
_VALID_MODELS = {
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite-preview",
    # Older generation still available but not version-pinned for the paper:
    "gemini-2.5-flash",
    "gemini-flash-latest",
}


class GeminiAdapter(ModelAdapter):
    supports: frozenset[Modality] = frozenset({"text", "image", "audio", "video"})

    def __init__(self, version: str = "gemini-3.1-pro-preview", api_key: str | None = None):
        if version not in _VALID_MODELS:
            raise ValueError(f"Unknown or deprecated Gemini version: {version}")
        self.version = version
        self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])

    def call(self, turns: Sequence[Turn], decoding: DecodingParams) -> ModelResponse:
        # Gemini's generate_content takes a flat list of Parts, not a
        # turn-structured conversation. For our two-pass protocol a single
        # user turn is sufficient (system prompt prepended as text).
        parts: list = []
        for t in turns:
            if t.role == "system":
                parts.append(f"[system]\n{t.text}\n[/system]")
            elif t.text:
                parts.append(t.text)
            for m in t.media:
                data = Path(m.path_or_url).read_bytes()
                mime = m.mime or mimetypes.guess_type(m.path_or_url)[0] or "application/octet-stream"
                parts.append(types.Part.from_bytes(data=data, mime_type=mime))

        cfg = types.GenerateContentConfig(
            temperature=decoding.temperature,
            top_p=decoding.top_p,
            max_output_tokens=decoding.max_output_tokens,
        )
        t0 = time.time()
        resp = self._client.models.generate_content(
            model=self.version, contents=parts, config=cfg
        )
        latency_ms = int((time.time() - t0) * 1000)
        usage = resp.usage_metadata
        return ModelResponse(
            text=(resp.text or "").strip(),
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            latency_ms=latency_ms,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else {},
        )
