"""Mimo v2-omni cross-vendor variant for paper-modality cells.

Tests whether the audio-modality cascade wash on Mimo (no gain, no loss)
generalizes to paper modality, or is specific to audio. Same paper, same
reference (Gemini), same probes, same judge (GPT-5.4) — only C0/C1 model
changes to xiaomi/mimo-v2-omni via OpenRouter.

Usage:
  python3 pilot/pilot_paper_review_mimo.py \
      --run-dir runs/paper-review-19700023812-1777471791 \
      --sample data/longform_pdf/scanned/pilot_sample.jsonl \
      --item 19700023812
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import sys
import time
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from openai import OpenAI

from pilot_audio_review import REVIEW_PROMPT, score_review
from pilot_paper_review import pass2_review_prompt


MIMO_MODEL_DEFAULT = "xiaomi/mimo-v2-omni"


def _client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )


def call_mimo_with_images(prompt: str, image_paths: list[str], model: str, max_tokens: int = 8_000) -> tuple[str, int]:
    client = _client()
    content: list[dict] = []
    for ip in image_paths:
        with open(ip, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })
    content.append({"type": "text", "text": prompt})

    t0 = time.time()
    r = client.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    ms = int((time.time() - t0) * 1000)
    if not (r.choices and r.choices[0].message):
        return "", ms
    return (r.choices[0].message.content or "").strip(), ms


def call_mimo_text(prompt: str, model: str, max_tokens: int = 8_000) -> tuple[str, int]:
    client = _client()
    t0 = time.time()
    r = client.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    )
    ms = int((time.time() - t0) * 1000)
    if not (r.choices and r.choices[0].message):
        return "", ms
    return (r.choices[0].message.content or "").strip(), ms


def call_mimo_chunked_ocr(image_paths: list[str], model: str) -> tuple[str, int]:
    chunk_prompt = (
        "Transcribe the full text of this PDF page verbatim, in reading "
        "order. Capture every paragraph, heading, figure caption, table "
        "content, and footnote you can read. Do NOT summarize, paraphrase, "
        "or add commentary — output the literal text as it appears."
    )
    pieces: list[str] = []
    total_ms = 0
    n = len(image_paths)
    for i, ip in enumerate(image_paths):
        page_marker = f"=== page {i+1} ==="
        try:
            text, ms = call_mimo_with_images(chunk_prompt, [ip], model, max_tokens=4_000)
        except Exception as e:
            text, ms = "", 0
            print(f"      [warn] page {i+1} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
        total_ms += ms
        if not text:
            text = "(empty)"
        pieces.append(f"{page_marker}\n{text}")
        if i % 10 == 0 or i == n - 1:
            print(f"      [chunk] {i+1}/{n} pages, {ms/1000:.1f}s, {len(text.split())} words", flush=True)
    return "\n\n".join(pieces), total_ms


def run(item: dict, run_dir: pathlib.Path, model: str):
    print(f"[run_dir] {run_dir}", flush=True)
    print(f"[paper]   {item['item_id']} ({item['page_count']}pp)  {item['title']}", flush=True)
    print(f"[mimo_model] {model}", flush=True)

    ref_path = run_dir / "reference_transcript.txt"
    probes_path = run_dir / "probes.json"
    if not ref_path.exists() or not probes_path.exists():
        raise SystemExit(f"reference or probes missing in {run_dir}")
    reference = ref_path.read_text()
    probes = json.loads(probes_path.read_text()).get("probes", [])
    print(f"  [ref] reusing existing ({len(reference.split())} words)", flush=True)
    print(f"  [probes] reusing existing ({len(probes)} probes)", flush=True)

    image_paths = item["image_paths"]

    # C0_mimo
    c0_path = run_dir / "review_C0_mimo.txt"
    c0_skipped_path = run_dir / "review_C0_mimo.SKIPPED"
    if c0_path.exists():
        print(f"  [C0_mimo] reusing existing", flush=True)
        review_c0 = c0_path.read_text()
    elif c0_skipped_path.exists():
        print(f"  [C0_mimo] previously skipped", flush=True)
        review_c0 = None
    else:
        print(f"  [C0_mimo] {model} multimodal review on {len(image_paths)} images...", flush=True)
        try:
            review_c0, ms = call_mimo_with_images(REVIEW_PROMPT, image_paths, model, max_tokens=8_000)
            if not review_c0 or len(review_c0.split()) < 50:
                err_msg = f"C0 too short ({len(review_c0.split())} words) — likely silent input-size rejection"
                print(f"    [skip] {err_msg}; proceeding with C1 only", flush=True)
                c0_skipped_path.write_text(err_msg)
                review_c0 = None
            else:
                c0_path.write_text(review_c0)
                print(f"    C0_mimo: {len(review_c0.split())} words ({ms/1000:.1f}s)", flush=True)
        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"    [skip] C0_mimo failed ({err_msg}); proceeding with C1 only", flush=True)
            c0_skipped_path.write_text(err_msg)
            review_c0 = None

    # C1_mimo Pass-1
    c1p1_path = run_dir / "transcript_C1_pass1_mimo.txt"
    if c1p1_path.exists():
        print(f"  [C1.p1_mimo] reusing existing", flush=True)
        c1_pass1 = c1p1_path.read_text()
    else:
        print(f"  [C1.p1_mimo] {model} chunked OCR on {len(image_paths)} pages...", flush=True)
        c1_pass1, ms = call_mimo_chunked_ocr(image_paths, model)
        c1p1_path.write_text(c1_pass1)
        print(f"    C1.p1_mimo: {len(c1_pass1.split())} words ({ms/1000:.1f}s)", flush=True)
    if not c1_pass1 or len(c1_pass1.split()) < 50:
        raise RuntimeError(f"C1 Pass-1 OCR too short ({len(c1_pass1.split())} words)")

    # C1_mimo Pass-2 (text-only)
    c1_path = run_dir / "review_C1_mimo.txt"
    if c1_path.exists():
        print(f"  [C1.p2_mimo] reusing existing", flush=True)
        review_c1 = c1_path.read_text()
    else:
        print(f"  [C1.p2_mimo] {model} review from transcript...", flush=True)
        review_c1, ms = call_mimo_text(pass2_review_prompt(c1_pass1), model, max_tokens=8_000)
        c1_path.write_text(review_c1)
        print(f"    C1_mimo: {len(review_c1.split())} words ({ms/1000:.1f}s)", flush=True)

    # Score
    score_c0 = score_review(review_c0, reference, probes, "C0_mimo", run_dir) if review_c0 is not None else None
    score_c1 = score_review(review_c1, reference, probes, "C1_mimo", run_dir)

    sp = run_dir / "summary.json"
    s = json.loads(sp.read_text()) if sp.exists() else {}
    if score_c0 is not None:
        s.setdefault("scores", {})["C0_mimo"] = asdict(score_c0)
        s["review_C0_mimo_word_count"] = len(review_c0.split())
    s.setdefault("scores", {})["C1_mimo"] = asdict(score_c1)
    s["review_C1_mimo_word_count"] = len(review_c1.split())
    s["transcript_C1_pass1_mimo_word_count"] = len(c1_pass1.split())
    s["mimo_model"] = model
    sp.write_text(json.dumps(s, indent=2))

    print(f"\n=== Mimo {item['item_id']} ===", flush=True)
    for sc in [score_c0, score_c1]:
        if sc is None:
            print(f"  C0_mimo  SKIPPED", flush=True)
            continue
        print(
            f"  {sc.condition}  halluc={sc.n_unsupported}  "
            f"cov={sc.probe_coverage:.3f} ({sc.n_covered}/{sc.n_probes})",
            flush=True,
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--sample", type=pathlib.Path, required=True)
    ap.add_argument("--item", required=True)
    ap.add_argument("--model", default=MIMO_MODEL_DEFAULT)
    args = ap.parse_args()

    items = [json.loads(l) for l in args.sample.open()]
    matched = [it for it in items if it["item_id"] == args.item]
    if not matched:
        raise SystemExit(f"item {args.item} not found")
    run(matched[0], args.run_dir, args.model)


if __name__ == "__main__":
    main()
