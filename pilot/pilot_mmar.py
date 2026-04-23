"""Phase-1 pilot: MMAR × (Gemini | OpenRouter) × {C0, C1, C2}.

Generalizes pilot_mmar_gemini.py to support any provider by abstracting
the single-call interface. Scoring, prompts, and per-item/aggregate
bookkeeping are identical across providers.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import Protocol

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = REPO / "data" / "mmar" / "MMAR-main" / "pilot_sample.jsonl"
AUDIO_DIR = REPO / "data" / "mmar" / "MMAR-main" / "audio"
UAS_SCHEMA_PATH = REPO / "harness" / "schemas" / "audio_uas.md"


# ----- Prompts -----

def end_to_end_prompt(question: str, choices: list[str]) -> str:
    return (
        f"Listen to the attached audio and answer.\n\n"
        f"Question: {question}\n"
        f"Choices:\n" + "\n".join(f"  {chr(65+i)}. {c}" for i, c in enumerate(choices)) + "\n\n"
        f"Answer with ONLY the single letter of the correct choice (A, B, C, or D). No explanation."
    )


C1_PASS1_PROMPT = (
    "Transcribe the attached audio clip verbatim. Include disfluencies, "
    "repetitions, and speaker labels if multiple speakers are audible. Do NOT "
    "answer any question. Just produce the transcript."
)


def c2_pass1_prompt() -> str:
    schema = UAS_SCHEMA_PATH.read_text()
    match = re.search(r"## Pass-1 prompt.*?```\n(.*?)\n```", schema, re.S)
    if not match:
        raise RuntimeError("Could not extract Pass-1 prompt from audio_uas.md")
    return match.group(1)


def pass2_prompt(question: str, choices: list[str], perception: str, rich: bool) -> str:
    header = (
        "Below is a structured perception of an audio clip."
        if rich
        else "Below is a plain transcript of an audio clip."
    )
    return (
        f"{header} Use ONLY the information below to answer the question; do not speculate beyond it.\n\n"
        f"<perception>\n{perception}\n</perception>\n\n"
        f"Question: {question}\n"
        f"Choices:\n" + "\n".join(f"  {chr(65+i)}. {c}" for i, c in enumerate(choices)) + "\n\n"
        f"Answer with ONLY the single letter of the correct choice (A, B, C, or D). No explanation."
    )


# ----- Provider abstraction -----

class Provider(Protocol):
    name: str
    model: str

    def call(self, prompt: str, audio_bytes: bytes | None) -> tuple[str, int, int, int]:
        """Return (text, input_tokens, output_tokens, latency_ms)."""
        ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str):
        from google import genai
        self.model = model
        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def call(self, prompt: str, audio_bytes: bytes | None):
        from google.genai import types
        contents: list = [prompt]
        if audio_bytes is not None:
            contents.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"))
        t0 = time.time()
        resp = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
                top_p=1.0,
                max_output_tokens=2048,
            ),
        )
        latency_ms = int((time.time() - t0) * 1000)
        usage = resp.usage_metadata
        return (
            (resp.text or "").strip(),
            getattr(usage, "prompt_token_count", 0) or 0,
            getattr(usage, "candidates_token_count", 0) or 0,
            latency_ms,
        )


class OpenRouterProvider:
    """OpenAI-compatible chat completions via OpenRouter.

    Audio is sent as `input_audio` content parts (OpenAI schema). Models known
    to support this: openai/gpt-4o-audio-preview, openai/gpt-audio,
    mistralai/voxtral-small-24b-2507, xiaomi/mimo-v2-omni.
    """
    name = "openrouter"

    def __init__(self, model: str):
        from openai import OpenAI
        self.model = model
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

    def call(self, prompt: str, audio_bytes: bytes | None):
        content: list = [{"type": "text", "text": prompt}]
        if audio_bytes is not None:
            content.append({
                "type": "input_audio",
                "input_audio": {
                    "data": base64.b64encode(audio_bytes).decode(),
                    "format": "wav",
                },
            })
        t0 = time.time()
        r = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0.0,
            top_p=1.0,
            max_tokens=2048,
        )
        latency_ms = int((time.time() - t0) * 1000)
        msg = r.choices[0].message
        text = (msg.content or "").strip()
        usage = r.usage or None
        in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
        out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
        return text, in_tok, out_tok, latency_ms


# ----- Core logic -----

@dataclass
class CallLog:
    item_id: str
    provider: str
    model: str
    condition: str
    stage: str
    prompt_tokens: int
    output_tokens: int
    latency_ms: int
    output_text: str


def score_mcq(item: dict, output_text: str) -> float:
    choices = item["choices"]
    correct_text = item["answer"]
    try:
        correct_idx = choices.index(correct_text)
    except ValueError:
        return 0.0
    correct_letter = chr(65 + correct_idx)
    out = output_text.strip().upper()
    m = re.match(r"^[^A-Z]*([A-Z])[^A-Z]*", out)
    if m and m.group(1) == correct_letter:
        return 1.0
    if correct_text.lower() in output_text.lower():
        return 1.0
    return 0.0


def run_one(provider: Provider, item: dict, run_dir: pathlib.Path) -> dict:
    audio_path = AUDIO_DIR / pathlib.Path(item["audio_path"]).name
    if not audio_path.exists():
        return {"item_id": item["id"], "error": f"audio missing: {audio_path}"}
    audio_bytes = audio_path.read_bytes()

    logs: list[CallLog] = []

    # ---- C0 end-to-end ----
    text, it, ot, ms = provider.call(end_to_end_prompt(item["question"], item["choices"]), audio_bytes)
    logs.append(CallLog(item["id"], provider.name, provider.model, "C0", "e2e", it, ot, ms, text))
    c0_score = score_mcq(item, text)

    # ---- C1 plain cascade ----
    p1_text, p1_in, p1_out, p1_ms = provider.call(C1_PASS1_PROMPT, audio_bytes)
    logs.append(CallLog(item["id"], provider.name, provider.model, "C1", "pass1", p1_in, p1_out, p1_ms, p1_text))
    p2_text, p2_in, p2_out, p2_ms = provider.call(
        pass2_prompt(item["question"], item["choices"], p1_text, rich=False), None
    )
    logs.append(CallLog(item["id"], provider.name, provider.model, "C1", "pass2", p2_in, p2_out, p2_ms, p2_text))
    c1_score = score_mcq(item, p2_text)

    # ---- C2 augmented cascade ----
    p1b_text, p1b_in, p1b_out, p1b_ms = provider.call(c2_pass1_prompt(), audio_bytes)
    logs.append(CallLog(item["id"], provider.name, provider.model, "C2", "pass1", p1b_in, p1b_out, p1b_ms, p1b_text))
    p2b_text, p2b_in, p2b_out, p2b_ms = provider.call(
        pass2_prompt(item["question"], item["choices"], p1b_text, rich=True), None
    )
    logs.append(CallLog(item["id"], provider.name, provider.model, "C2", "pass2", p2b_in, p2b_out, p2b_ms, p2b_text))
    c2_score = score_mcq(item, p2b_text)

    with (run_dir / "calls.jsonl").open("a") as f:
        for log in logs:
            f.write(json.dumps(asdict(log)) + "\n")

    return {
        "item_id": item["id"],
        "category": item["category"],
        "answer": item["answer"],
        "C0_score": c0_score,
        "C1_score": c1_score,
        "C2_score": c2_score,
        "C0_output": logs[0].output_text,
        "C1_pass1_len": len(logs[1].output_text),
        "C1_output": logs[2].output_text,
        "C2_pass1_len": len(logs[3].output_text),
        "C2_output": logs[4].output_text,
        "C0_ms": logs[0].latency_ms,
        "C1_ms": logs[1].latency_ms + logs[2].latency_ms,
        "C2_ms": logs[3].latency_ms + logs[4].latency_ms,
        "C0_out_tok": logs[0].output_tokens,
        "C1_out_tok": logs[1].output_tokens + logs[2].output_tokens,
        "C2_out_tok": logs[3].output_tokens + logs[4].output_tokens,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["gemini", "openrouter"], required=True)
    ap.add_argument("--model", required=True, help="Model ID; e.g. gemini-3.1-pro-preview or openai/gpt-4o-audio-preview")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--run-dir", type=pathlib.Path, default=None)
    args = ap.parse_args()

    run_tag = f"{args.provider}-{args.model.replace('/', '--')}-{int(time.time())}"
    run_dir = args.run_dir or REPO / "runs" / run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run_dir] {run_dir}")

    if args.provider == "gemini":
        provider: Provider = GeminiProvider(args.model)
    else:
        provider = OpenRouterProvider(args.model)

    items = [json.loads(l) for l in SAMPLE.open()]
    if args.limit > 0:
        items = items[: args.limit]
    print(f"[items] {len(items)}   [provider] {provider.name}   [model] {provider.model}")

    results = []
    for i, item in enumerate(items):
        t0 = time.time()
        try:
            r = run_one(provider, item, run_dir)
        except Exception as e:
            print(f"  [{i+1}/{len(items)}] {item['id']} FAILED: {type(e).__name__}: {str(e)[:200]}")
            r = {"item_id": item["id"], "error": str(e), "category": item["category"]}
        results.append(r)
        if "error" not in r:
            print(
                f"  [{i+1}/{len(items)}] {item['category']:18s} {item['id']:40s}  "
                f"C0={r['C0_score']:.0f} C1={r['C1_score']:.0f} C2={r['C2_score']:.0f}  "
                f"({int(time.time()-t0):3d}s)"
            )
        with (run_dir / "items.jsonl").open("a") as f:
            f.write(json.dumps(r) + "\n")

    # Aggregate
    valid = [r for r in results if "error" not in r]
    print(f"\n=== Aggregate === N={len(valid)} errors={len(results)-len(valid)}")
    for cond in ["C0", "C1", "C2"]:
        scores = [r[f"{cond}_score"] for r in valid]
        toks = [r[f"{cond}_out_tok"] for r in valid]
        lat = [r[f"{cond}_ms"] for r in valid]
        if scores:
            print(
                f"  {cond}  acc={sum(scores)/len(scores):.3f}  "
                f"out_tok_mean={sum(toks)/len(toks):6.0f}  "
                f"lat_mean={sum(lat)/len(lat):5.0f}ms"
            )

    print("\n=== Per-category ===")
    cats: dict[str, list] = {}
    for r in valid:
        cats.setdefault(r["category"], []).append(r)
    for cat in ["Signal Layer", "Perception Layer", "Semantic Layer", "Cultural Layer"]:
        rs = cats.get(cat, [])
        if not rs:
            continue
        c0 = sum(r["C0_score"] for r in rs) / len(rs)
        c1 = sum(r["C1_score"] for r in rs) / len(rs)
        c2 = sum(r["C2_score"] for r in rs) / len(rs)
        print(
            f"  {cat:18s} n={len(rs)}  C0={c0:.3f}  C1={c1:.3f}  C2={c2:.3f}  "
            f"Δ(C1-C0)={c1-c0:+.3f}  Δ(C2-C0)={c2-c0:+.3f}  Δ(C2-C1)={c2-c1:+.3f}"
        )

    print("\n=== Phase-1 gate ===")
    gaps = []
    for cat, rs in cats.items():
        c0 = sum(r["C0_score"] for r in rs) / len(rs)
        c1 = sum(r["C1_score"] for r in rs) / len(rs)
        c2 = sum(r["C2_score"] for r in rs) / len(rs)
        gaps.append((cat, "C1-C0", c1 - c0))
        gaps.append((cat, "C2-C0", c2 - c0))
    hits = sum(1 for _, _, g in gaps if abs(g) >= 0.03)
    verdict = "PASS" if hits >= 2 else "FAIL"
    print(f"  cells crossing ±3pt: {hits} / {len(gaps)}  →  {verdict}")

    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "provider": provider.name,
                "model": provider.model,
                "n": len(valid),
                "errors": len(results) - len(valid),
                "by_condition": {
                    cond: {
                        "acc": (sum(r[f"{cond}_score"] for r in valid) / len(valid)) if valid else 0.0,
                        "out_tok_mean": (sum(r[f"{cond}_out_tok"] for r in valid) / len(valid)) if valid else 0,
                        "lat_ms_mean": (sum(r[f"{cond}_ms"] for r in valid) / len(valid)) if valid else 0,
                    }
                    for cond in ["C0", "C1", "C2"]
                },
                "by_category": {
                    cat: {
                        "n": len(rs),
                        **{f"{cond}_acc": sum(r[f"{cond}_score"] for r in rs) / len(rs) for cond in ["C0", "C1", "C2"]},
                    }
                    for cat, rs in cats.items()
                },
                "phase1_gate": verdict,
            },
            indent=2,
        )
    )
    print(f"[wrote] {run_dir}/summary.json")


if __name__ == "__main__":
    main()
