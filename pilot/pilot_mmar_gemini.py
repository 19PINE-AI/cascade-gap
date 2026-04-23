"""Phase-1 pilot: MMAR × Gemini 3.1 × {C0, C1, C2}.

Reads 20 stratified MMAR items from data/mmar/MMAR-main/pilot_sample.jsonl,
runs each item through three conditions on Gemini 3.1 Pro, writes one
JSONL row per call to runs/<stamp>/items.jsonl, and prints per-cell scores
plus the §6 Phase-1 decision gate.

No post-hoc knobs: decoding params identical across conditions, UAS prompt
loaded from harness/schemas/audio_uas.md, seed fixed.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
from dataclasses import dataclass, asdict

from google import genai
from google.genai import types

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = REPO / "data" / "mmar" / "MMAR-main" / "pilot_sample.jsonl"
AUDIO_DIR = REPO / "data" / "mmar" / "MMAR-main" / "audio"
UAS_SCHEMA_PATH = REPO / "harness" / "schemas" / "audio_uas.md"

MODEL_PRO = "gemini-3.1-pro-preview"
MODEL_FLASH_LITE = "gemini-3.1-flash-lite-preview"


# Pass-2 reasoning prompt shared by C1 and C2
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
    # Extract the Pass-1 prompt section verbatim from the schema file so we
    # stay consistent with the pre-registered schema.
    match = re.search(r"## Pass-1 prompt.*?```\n(.*?)\n```", schema, re.S)
    if not match:
        raise RuntimeError("Could not extract Pass-1 prompt from audio_uas.md")
    return match.group(1)


@dataclass
class CallLog:
    item_id: str
    model: str
    condition: str
    stage: str  # "pass1" or "pass2" or "e2e"
    prompt_tokens: int
    output_tokens: int
    latency_ms: int
    output_text: str


def call_gemini(
    client: genai.Client,
    model: str,
    prompt: str,
    audio_bytes: bytes | None,
) -> tuple[str, int, int, int]:
    """Returns (text, input_tokens, output_tokens, latency_ms)."""
    contents: list = [prompt]
    if audio_bytes is not None:
        contents.append(
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
        )
    t0 = time.time()
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.0,
            top_p=1.0,
            max_output_tokens=2048,
        ),
    )
    latency_ms = int((time.time() - t0) * 1000)
    text = (resp.text or "").strip()
    usage = resp.usage_metadata
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    return text, in_tok, out_tok, latency_ms


def score_mcq(item: dict, output_text: str) -> float:
    """Return 1.0 if model picked the correct letter, else 0.0.

    Accepts 'A', 'A.', 'A)', '**A**', or the choice text itself.
    """
    choices = item["choices"]
    correct_text = item["answer"]
    try:
        correct_idx = choices.index(correct_text)
    except ValueError:
        return 0.0
    correct_letter = chr(65 + correct_idx)

    out = output_text.strip().upper()
    # Strip markdown / punctuation around a leading letter
    m = re.match(r"^[^A-Z]*([A-Z])[^A-Z]*", out)
    if m and m.group(1) == correct_letter:
        return 1.0
    # Fallback: exact substring match on answer text
    if correct_text.lower() in output_text.lower():
        return 1.0
    return 0.0


def run_one(
    client: genai.Client,
    item: dict,
    model: str,
    run_dir: pathlib.Path,
) -> dict:
    audio_path = AUDIO_DIR / pathlib.Path(item["audio_path"]).name
    if not audio_path.exists():
        return {"item_id": item["id"], "error": f"audio missing: {audio_path}"}
    audio_bytes = audio_path.read_bytes()

    logs: list[CallLog] = []

    # ---- C0 end-to-end ----
    text, it, ot, ms = call_gemini(
        client, model, end_to_end_prompt(item["question"], item["choices"]), audio_bytes
    )
    c0_score = score_mcq(item, text)
    logs.append(CallLog(item["id"], model, "C0", "e2e", it, ot, ms, text))

    # ---- C1 plain self-cascade ----
    p1_text, p1_in, p1_out, p1_ms = call_gemini(client, model, C1_PASS1_PROMPT, audio_bytes)
    logs.append(CallLog(item["id"], model, "C1", "pass1", p1_in, p1_out, p1_ms, p1_text))
    p2_text, p2_in, p2_out, p2_ms = call_gemini(
        client, model, pass2_prompt(item["question"], item["choices"], p1_text, rich=False), None
    )
    c1_score = score_mcq(item, p2_text)
    logs.append(CallLog(item["id"], model, "C1", "pass2", p2_in, p2_out, p2_ms, p2_text))

    # ---- C2 augmented self-cascade ----
    p1b_text, p1b_in, p1b_out, p1b_ms = call_gemini(
        client, model, c2_pass1_prompt(), audio_bytes
    )
    logs.append(CallLog(item["id"], model, "C2", "pass1", p1b_in, p1b_out, p1b_ms, p1b_text))
    p2b_text, p2b_in, p2b_out, p2b_ms = call_gemini(
        client, model, pass2_prompt(item["question"], item["choices"], p1b_text, rich=True), None
    )
    c2_score = score_mcq(item, p2b_text)
    logs.append(CallLog(item["id"], model, "C2", "pass2", p2b_in, p2b_out, p2b_ms, p2b_text))

    # Persist every call
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
    ap.add_argument("--model", default=MODEL_PRO, choices=[MODEL_PRO, MODEL_FLASH_LITE])
    ap.add_argument("--limit", type=int, default=20, help="Items to run; 0 = all in sample")
    ap.add_argument("--run-dir", type=pathlib.Path, default=REPO / "runs" / f"pilot-{int(time.time())}")
    args = ap.parse_args()

    if "GEMINI_API_KEY" not in os.environ:
        sys.exit("GEMINI_API_KEY not set")

    args.run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run_dir] {args.run_dir}")

    items = [json.loads(l) for l in SAMPLE.open()]
    if args.limit > 0:
        items = items[: args.limit]
    print(f"[items] {len(items)} from {SAMPLE.name}")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    results: list[dict] = []
    for i, item in enumerate(items):
        t0 = time.time()
        try:
            r = run_one(client, item, args.model, args.run_dir)
        except Exception as e:
            print(f"  [{i+1}/{len(items)}] {item['id']} FAILED: {e}")
            r = {"item_id": item["id"], "error": str(e)}
        results.append(r)
        if "error" not in r:
            print(
                f"  [{i+1}/{len(items)}] {item['category']:18s} {item['id']:40s}  "
                f"C0={r['C0_score']:.0f} C1={r['C1_score']:.0f} C2={r['C2_score']:.0f}  "
                f"({int(time.time()-t0):3d}s)"
            )
        with (args.run_dir / "items.jsonl").open("a") as f:
            f.write(json.dumps(r) + "\n")

    # Aggregate
    print("\n=== Aggregate ===")
    valid = [r for r in results if "error" not in r]
    print(f"N={len(valid)}  (errors={len(results)-len(valid)})")
    for cond in ["C0", "C1", "C2"]:
        scores = [r[f"{cond}_score"] for r in valid]
        toks = [r[f"{cond}_out_tok"] for r in valid]
        lat = [r[f"{cond}_ms"] for r in valid]
        mean = sum(scores) / len(scores) if scores else 0.0
        print(
            f"  {cond}  acc={mean:.3f}  out_tok_mean={sum(toks)/len(toks):6.0f}  "
            f"lat_mean={sum(lat)/len(lat):5.0f}ms"
        )

    # Per-category
    print("\n=== Per-category ===")
    cats = {}
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

    # Phase-1 gate per §6: ≥3-point abs difference on ≥2/N cells
    print("\n=== Phase-1 gate ===")
    gaps_c1 = []
    gaps_c2 = []
    for cat, rs in cats.items():
        c0 = sum(r["C0_score"] for r in rs) / len(rs)
        c1 = sum(r["C1_score"] for r in rs) / len(rs)
        c2 = sum(r["C2_score"] for r in rs) / len(rs)
        gaps_c1.append((cat, c1 - c0))
        gaps_c2.append((cat, c2 - c0))
    hits = sum(1 for _, g in gaps_c1 if abs(g) >= 0.03) + sum(1 for _, g in gaps_c2 if abs(g) >= 0.03)
    verdict = "PASS" if hits >= 2 else "FAIL"
    print(f"  cells crossing ±3pt: {hits} / {len(gaps_c1)+len(gaps_c2)}  →  {verdict}")

    (args.run_dir / "summary.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "n": len(valid),
                "by_condition": {
                    cond: {
                        "acc": sum(r[f"{cond}_score"] for r in valid) / len(valid),
                        "out_tok_mean": sum(r[f"{cond}_out_tok"] for r in valid) / len(valid),
                        "lat_ms_mean": sum(r[f"{cond}_ms"] for r in valid) / len(valid),
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
    print(f"[wrote] {args.run_dir}/summary.json")


if __name__ == "__main__":
    main()
