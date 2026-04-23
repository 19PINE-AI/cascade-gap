"""Phase-1 vision pilot: DocVQA × {Gemini 3.1 Pro, Gemini 3 Flash, GPT-5.4,
Qwen3-VL-30B-A3B-Thinking, Qwen3-VL-235B-A22B-Thinking} × {C0, C1, C2}.

Same shape as pilot_mmar.py but with images. Pre-registered C2 schema is
harness/schemas/document_layout.md.

Scoring: case-insensitive substring match against ANY reference answer (a
lightweight proxy for DocVQA's ANLS — strict enough to rank conditions).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import time
from dataclasses import dataclass, asdict
from typing import Protocol

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = REPO / "data" / "docvqa_pilot" / "pilot_sample.jsonl"
IMAGE_DIR = REPO / "data" / "docvqa_pilot"
LAYOUT_SCHEMA_PATH = REPO / "harness" / "schemas" / "document_layout.md"


# ----- Prompts -----

def end_to_end_prompt(question: str) -> str:
    return (
        "Look at the attached document image and answer the question. "
        "Give ONLY the short answer string, no explanation.\n\n"
        f"Question: {question}\n\nAnswer:"
    )


C1_PASS1_PROMPT = (
    "Extract every piece of text visible in the attached document image, "
    "preserving the reading order. Do NOT answer any question. Just produce "
    "the plain text transcription."
)


def c2_pass1_prompt() -> str:
    schema = LAYOUT_SCHEMA_PATH.read_text()
    match = re.search(r"## Pass-1 prompt\s*```\n(.*?)\n```", schema, re.S)
    if not match:
        raise RuntimeError("Could not extract Pass-1 prompt from document_layout.md")
    return match.group(1)


def pass2_prompt(question: str, perception: str, rich: bool) -> str:
    header = (
        "Below is a structured description of a document, produced by an "
        "earlier perception pass."
        if rich
        else "Below is a plain-text transcription of a document."
    )
    return (
        f"{header} Use ONLY the information below to answer the question.\n\n"
        f"<perception>\n{perception}\n</perception>\n\n"
        f"Question: {question}\n\n"
        "Give ONLY the short answer string, no explanation."
    )


# ----- Provider abstraction -----

class Provider(Protocol):
    name: str
    model: str

    def call(self, prompt: str, image_bytes: bytes | None) -> tuple[str, int, int, int]:
        ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str):
        from google import genai
        self.model = model
        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def call(self, prompt: str, image_bytes: bytes | None):
        from google.genai import types
        parts: list = [prompt]
        if image_bytes is not None:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))
        t0 = time.time()
        resp = self._client.models.generate_content(
            model=self.model,
            contents=parts,
            config=types.GenerateContentConfig(temperature=0.0, top_p=1.0, max_output_tokens=4096),
        )
        ms = int((time.time() - t0) * 1000)
        u = resp.usage_metadata
        return (
            (resp.text or "").strip(),
            getattr(u, "prompt_token_count", 0) or 0,
            getattr(u, "candidates_token_count", 0) or 0,
            ms,
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str):
        from openai import OpenAI
        self.model = model
        self._client = OpenAI()

    def call(self, prompt: str, image_bytes: bytes | None):
        content: list = [{"type": "text", "text": prompt}]
        if image_bytes is not None:
            b64 = base64.b64encode(image_bytes).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
        t0 = time.time()
        r = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_completion_tokens=4096,
        )
        ms = int((time.time() - t0) * 1000)
        msg = r.choices[0].message
        text = (msg.content or "").strip()
        usage = r.usage
        in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
        out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
        return text, in_tok, out_tok, ms


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, model: str):
        from openai import OpenAI
        self.model = model
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

    def call(self, prompt: str, image_bytes: bytes | None):
        content: list = [{"type": "text", "text": prompt}]
        if image_bytes is not None:
            b64 = base64.b64encode(image_bytes).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
        t0 = time.time()
        r = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0.0,
            top_p=1.0,
            max_tokens=4096,
        )
        ms = int((time.time() - t0) * 1000)
        msg = r.choices[0].message
        text = (msg.content or "").strip()
        usage = r.usage
        in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
        out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
        return text, in_tok, out_tok, ms


# ----- Core -----

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


def score(item: dict, output_text: str) -> float:
    refs = [str(a).lower().strip() for a in item.get("answers", [])]
    hyp = output_text.lower().strip()
    # Strip trailing punctuation
    hyp_core = re.sub(r"[\.,;:!\?\s]+$", "", hyp)
    for ref in refs:
        if not ref:
            continue
        if ref == hyp_core:
            return 1.0
        if ref in hyp:
            return 1.0
    return 0.0


def run_one(provider: Provider, item: dict, run_dir: pathlib.Path) -> dict:
    img_path = IMAGE_DIR / item["image_path"]
    if not img_path.exists():
        return {"item_id": item["item_id"], "error": f"image missing: {img_path}"}
    img_bytes = img_path.read_bytes()

    logs: list[CallLog] = []

    # C0
    text, it, ot, ms = provider.call(end_to_end_prompt(item["question"]), img_bytes)
    logs.append(CallLog(item["item_id"], provider.name, provider.model, "C0", "e2e", it, ot, ms, text))
    c0 = score(item, text)

    # C1
    p1, p1_in, p1_out, p1_ms = provider.call(C1_PASS1_PROMPT, img_bytes)
    logs.append(CallLog(item["item_id"], provider.name, provider.model, "C1", "pass1", p1_in, p1_out, p1_ms, p1))
    p2, p2_in, p2_out, p2_ms = provider.call(pass2_prompt(item["question"], p1, rich=False), None)
    logs.append(CallLog(item["item_id"], provider.name, provider.model, "C1", "pass2", p2_in, p2_out, p2_ms, p2))
    c1 = score(item, p2)

    # C2
    p1b, p1b_in, p1b_out, p1b_ms = provider.call(c2_pass1_prompt(), img_bytes)
    logs.append(CallLog(item["item_id"], provider.name, provider.model, "C2", "pass1", p1b_in, p1b_out, p1b_ms, p1b))
    p2b, p2b_in, p2b_out, p2b_ms = provider.call(pass2_prompt(item["question"], p1b, rich=True), None)
    logs.append(CallLog(item["item_id"], provider.name, provider.model, "C2", "pass2", p2b_in, p2b_out, p2b_ms, p2b))
    c2 = score(item, p2b)

    with (run_dir / "calls.jsonl").open("a") as f:
        for log in logs:
            f.write(json.dumps(asdict(log)) + "\n")

    return {
        "item_id": item["item_id"],
        "question_type": item["question_type"],
        "answers": item["answers"],
        "C0_score": c0,
        "C1_score": c1,
        "C2_score": c2,
        "C0_output": logs[0].output_text,
        "C1_output": logs[2].output_text,
        "C2_output": logs[4].output_text,
        "C0_ms": logs[0].latency_ms,
        "C1_ms": logs[1].latency_ms + logs[2].latency_ms,
        "C2_ms": logs[3].latency_ms + logs[4].latency_ms,
        "C0_out_tok": logs[0].output_tokens,
        "C1_out_tok": logs[1].output_tokens + logs[2].output_tokens,
        "C2_out_tok": logs[3].output_tokens + logs[4].output_tokens,
    }


def make_provider(provider: str, model: str) -> Provider:
    if provider == "gemini":
        return GeminiProvider(model)
    if provider == "openai":
        return OpenAIProvider(model)
    if provider == "openrouter":
        return OpenRouterProvider(model)
    raise ValueError(provider)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["gemini", "openai", "openrouter"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--run-dir", type=pathlib.Path, default=None)
    args = ap.parse_args()

    run_tag = f"vision-{args.provider}-{args.model.replace('/', '--')}-{int(time.time())}"
    run_dir = args.run_dir or REPO / "runs" / run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run_dir] {run_dir}")

    provider = make_provider(args.provider, args.model)
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
            print(f"  [{i+1}/{len(items)}] {item['item_id']} FAILED: {type(e).__name__}: {str(e)[:160]}")
            r = {"item_id": item["item_id"], "error": str(e), "question_type": item.get("question_type", "?")}
        results.append(r)
        if "error" not in r:
            print(
                f"  [{i+1}/{len(items)}] {item['question_type']:14s} {item['item_id']:>10}  "
                f"C0={r['C0_score']:.0f} C1={r['C1_score']:.0f} C2={r['C2_score']:.0f}  "
                f"({int(time.time()-t0):3d}s)"
            )
        with (run_dir / "items.jsonl").open("a") as f:
            f.write(json.dumps(r) + "\n")

    valid = [r for r in results if "error" not in r]
    print(f"\n=== Aggregate === N={len(valid)} errors={len(results)-len(valid)}")
    for cond in ["C0", "C1", "C2"]:
        scores = [r[f"{cond}_score"] for r in valid]
        if scores:
            print(
                f"  {cond}  acc={sum(scores)/len(scores):.3f}  "
                f"out_tok_mean={sum(r[f'{cond}_out_tok'] for r in valid)/len(valid):6.0f}  "
                f"lat_mean={sum(r[f'{cond}_ms'] for r in valid)/len(valid):5.0f}ms"
            )

    print("\n=== By question type ===")
    by_type: dict[str, list] = {}
    for r in valid:
        by_type.setdefault(r["question_type"], []).append(r)
    for qt, rs in sorted(by_type.items()):
        c0 = sum(r["C0_score"] for r in rs) / len(rs)
        c1 = sum(r["C1_score"] for r in rs) / len(rs)
        c2 = sum(r["C2_score"] for r in rs) / len(rs)
        print(
            f"  {qt:15s} n={len(rs)}  C0={c0:.3f}  C1={c1:.3f}  C2={c2:.3f}  "
            f"Δ(C1-C0)={c1-c0:+.3f}  Δ(C2-C0)={c2-c0:+.3f}  Δ(C2-C1)={c2-c1:+.3f}"
        )

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
                "by_question_type": {
                    qt: {
                        "n": len(rs),
                        **{f"{cond}_acc": sum(r[f"{cond}_score"] for r in rs) / len(rs) for cond in ["C0", "C1", "C2"]},
                    }
                    for qt, rs in by_type.items()
                },
            },
            indent=2,
        )
    )
    print(f"[wrote] {run_dir}/summary.json")


if __name__ == "__main__":
    main()
