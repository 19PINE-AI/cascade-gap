"""On-disk response cache.

Every adapter call is keyed by
  (provider, model_version, decoding_hash, turns_hash)
and stored as JSON on disk. Re-running a pilot after a crash costs nothing.

Implementation notes for the Phase-1 implementer:
- Hash the full decoding params dict, not just temperature/seed, so
  reasoning-mode toggles don't silently collide.
- For media inputs, hash the file contents, not the path. Turns that cite
  /tmp/audio_42.wav vs /home/ubuntu/audio_42.wav with identical content
  should share a cache entry.
- Store `raw` vendor response verbatim so we can re-score later without
  re-calling.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .models import DecodingParams, ModelResponse, Turn


def _hash_turns(turns: Sequence[Turn]) -> str:
    h = hashlib.sha256()
    for t in turns:
        h.update(t.role.encode())
        h.update(b"\x00")
        h.update(t.text.encode())
        for m in t.media:
            h.update(b"\x01")
            h.update(m.modality.encode())
            # TODO: hash file content, not path. Path is a placeholder.
            h.update(m.path_or_url.encode())
    return h.hexdigest()


def _hash_decoding(d: DecodingParams) -> str:
    payload = json.dumps(asdict(d), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def cache_key(provider: str, version: str, turns: Sequence[Turn], decoding: DecodingParams) -> str:
    return f"{provider}/{version}/{_hash_decoding(decoding)[:16]}-{_hash_turns(turns)[:16]}"


def load(cache_dir: Path, key: str) -> ModelResponse | None:
    p = cache_dir / f"{key}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    d["cached"] = True
    return ModelResponse(**d)


def save(cache_dir: Path, key: str, response: ModelResponse) -> None:
    p = cache_dir / f"{key}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "text": response.text,
        "output_tokens": response.output_tokens,
        "input_tokens": response.input_tokens,
        "latency_ms": response.latency_ms,
        "raw": response.raw,
        "cached": False,
    }
    p.write_text(json.dumps(payload))
