"""Shared registry + helpers for the mechanistic experiments (E1/E2/E4/E5).

Reuses the exact prompts and GPT-5.4 judge from pilot_audio_review so every new
condition is scored identically to the original C0/C1 cells. New judge artifacts
are written into the original run dir under fresh labels (E1/E2/E5/...), so the
original judge_*_C0/C1.json files are never overwritten.
"""
from __future__ import annotations
import json, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pilot_audio_review import (
    REVIEW_PROMPT, score_review,
)
from google import genai
from google.genai import types
import os

REPO = pathlib.Path(__file__).resolve().parent.parent
PDF_DIR = REPO / "data" / "longform_pdf" / "scanned"
AUDIO_DIR = REPO / "data" / "longform_audio"
MECH = REPO / "runs" / "mechanism"
MECH.mkdir(parents=True, exist_ok=True)

PRO = "gemini-3.1-pro-preview"

# Representative subset spanning regimes. modality: 'paper' | 'audio'.
# born_digital marks arxiv PDFs that have a real text layer (needed for E5).
REGISTRY = {
    "mit_6034":           dict(run="audio-review-mit_6034_winston-1778857365", modality="audio",
                               asset="mit_6034_winston_intro_32k.mp3", regime="audio strong-win"),
    "3b1b_attention":     dict(run="audio-review-3b1b_attention-1778857367", modality="audio",
                               asset="3blue1brown_attention_32k.mp3", regime="audio clean-halluc-win"),
    "wagging_tail_9pp":   dict(run="paper-review-19720009221-1777458461", modality="paper",
                               item="19720009221", born_digital=False, regime="paper high-baseline"),
    "natural_vib_42pp":   dict(run="paper-review-19690013408-1777471789", modality="paper",
                               item="19690013408", born_digital=False, regime="paper Mode-B counter"),
    "thermal_66pp":       dict(run="paper-review-19700023812-1777471791", modality="paper",
                               item="19700023812", born_digital=False, regime="paper strong-win"),
    "heat_pipes_104pp":   dict(run="paper-review-19700025120-1777462513", modality="paper",
                               item="19700025120", born_digital=False, regime="paper Mode-A/B long"),
    "arxiv_fairness_53pp":dict(run="paper-review-2605.09852-1778859219", modality="paper",
                               item="2605.09852", born_digital=True, regime="arxiv Mode-A reversal"),
    "arxiv_perovskite_80pp":dict(run="paper-review-2605.13991-1778859221", modality="paper",
                               item="2605.13991", born_digital=True, regime="arxiv near-noise"),
}


def run_dir(cell: str) -> pathlib.Path:
    return REPO / "runs" / REGISTRY[cell]["run"]


def image_paths(cell: str) -> list[str]:
    item = REGISTRY[cell]["item"]
    d = PDF_DIR / f"rendered_{item}"
    return [str(p) for p in sorted(d.glob("*.png"))]


def audio_path(cell: str) -> str:
    return str(AUDIO_DIR / REGISTRY[cell]["asset"])


def pdf_path(cell: str) -> pathlib.Path:
    return PDF_DIR / f"{REGISTRY[cell]['item']}.pdf"


def load_cell(cell: str):
    rd = run_dir(cell)
    transcript = (rd / "transcript_C1_pass1.txt").read_text()
    reference = (rd / "reference_transcript.txt").read_text()
    probes = json.loads((rd / "probes.json").read_text()).get("probes", [])
    return rd, transcript, reference, probes


_CLIENT = None


def _client():
    # Cache a single client; a temporary genai.Client gets GC'd mid-request,
    # which closes its httpx transport ("Cannot send a request, ... closed").
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _CLIENT


def gemini_call(prompt: str, *, images: list[str] | None = None, audio: str | None = None,
                max_output_tokens: int = 65_536, temperature: float = 0.0,
                seed: int | None = None, retries: int = 4) -> tuple[str, int]:
    """Single Gemini call with optional images and/or audio attached, optional seed/temperature, with retry/backoff."""
    parts: list = [prompt]
    for ip in (images or []):
        parts.append(types.Part.from_bytes(data=pathlib.Path(ip).read_bytes(), mime_type="image/png"))
    if audio is not None:
        ext = pathlib.Path(audio).suffix.lstrip(".").lower()
        mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg"}.get(ext, "audio/mpeg")
        parts.append(types.Part.from_bytes(data=pathlib.Path(audio).read_bytes(), mime_type=mime))
    cfg_kw = dict(temperature=temperature, top_p=1.0, max_output_tokens=max_output_tokens)
    if seed is not None:
        cfg_kw["seed"] = seed
    client = _client()
    t0 = time.time()
    last_err = None
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(
                model=PRO, contents=parts, config=types.GenerateContentConfig(**cfg_kw))
            break
        except Exception as e:
            last_err = e
            wait = min(60, 5 * (2 ** attempt))
            print(f"      [retry {attempt+1}/{retries}] {type(e).__name__}: {str(e)[:120]} (sleep {wait}s)", flush=True)
            time.sleep(wait)
    else:
        raise RuntimeError(f"gemini_call failed after {retries} retries: {last_err}")
    ms = int((time.time() - t0) * 1000)
    text = (resp.text or "").strip()
    if not text:
        cand = resp.candidates[0] if resp.candidates else None
        fr = getattr(cand, "finish_reason", "?") if cand else "?"
        print(f"      [warn] empty Gemini response; finish_reason={fr}; usage={resp.usage_metadata}", flush=True)
    return text, ms


def score_and_record(review_text: str, reference: str, probes: list[dict], label: str,
                     rd: pathlib.Path) -> dict:
    """Run the standard halluc+probe judge, return a compact dict; writes judge_*_{label}.json into rd."""
    s = score_review(review_text, reference, probes, label, rd)
    return {
        "label": label,
        "n_unsupported": s.n_unsupported,
        "n_probes": s.n_probes,
        "n_covered": s.n_covered,
        "coverage": round(s.probe_coverage, 3),
    }


def existing_c0_c1(rd: pathlib.Path) -> dict:
    out = {}
    for lab in ("C0", "C1"):
        jh = rd / f"judge_halluc_{lab}.json"
        jp = rd / f"judge_probes_{lab}.json"
        h = json.loads(jh.read_text()).get("n_unsupported") if jh.exists() else None
        d = json.loads(jp.read_text()) if jp.exists() else {}
        out[lab] = {"n_unsupported": h, "coverage": round(d.get("coverage", 0), 3),
                    "n_covered": d.get("n_covered"), "n_probes": d.get("n_probes")}
    return out
