"""Cross-vendor variant of pilot_paper_review.py using Claude Opus 4.7.

Reuses the existing Gemini-generated reference transcript and probes for the
target run-dir, only re-running C0 (multimodal end-to-end) and C1 (chunked
OCR + Pass-2) with Claude. The judge is still GPT-5.4 (reasoning_effort=high).

Goal: test whether the cascade pattern (cascade reduces hallucinations and
improves coverage) replicates with a different model family. Same paper,
same reference, same probes, same judge — only C0/C1 vendor changes.

Usage:
  python3 pilot/pilot_paper_review_claude.py \
      --run-dir runs/paper-review-19700023812-1777471791 \
      --sample data/longform_pdf/scanned/pilot_sample.jsonl \
      --item 19700023812
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import sys
import time
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from anthropic import Anthropic

from pilot_audio_review import (
    REVIEW_PROMPT,
    score_review,
)
from pilot_paper_review import (
    REFERENCE_OCR_PROMPT,
    pass2_review_prompt,
)


CLAUDE_MODEL_DEFAULT = "claude-opus-4-7"  # 200K context — enough for ~66pp


def _img_block(path: pathlib.Path) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.standard_b64encode(path.read_bytes()).decode(),
        },
    }


def call_claude_with_images(prompt: str, image_paths: list[str], model: str, max_tokens: int = 8_000):
    client = Anthropic()
    content: list[dict] = []
    for ip in image_paths:
        content.append(_img_block(pathlib.Path(ip)))
    content.append({"type": "text", "text": prompt})

    # Use 1M context beta when there are many images (>15 ≈ default context limit)
    extra_headers = {"anthropic-beta": "context-1m-2025-08-07"} if len(image_paths) > 15 else {}
    # Note: Claude Opus 4.7 API rejects the `temperature` parameter as
    # deprecated for this model. Determinism is therefore not controllable
    # through the API; see paper §3.5 Pass-2 stochasticity discussion.
    t0 = time.time()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
        extra_headers=extra_headers,
    )
    ms = int((time.time() - t0) * 1000)
    text_parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return ("\n".join(text_parts)).strip(), ms


def call_claude_text_only(prompt: str, model: str, max_tokens: int = 8_000):
    client = Anthropic()
    # Claude Opus 4.7 API rejects `temperature` as deprecated for this model;
    # there is no per-call determinism knob we can pin from the SDK.
    t0 = time.time()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    )
    ms = int((time.time() - t0) * 1000)
    text_parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return ("\n".join(text_parts)).strip(), ms


def call_claude_chunked_ocr(image_paths: list[str], model: str) -> tuple[str, int]:
    """Per-page chunked OCR (1 page/call) — mirrors Gemini chunked OCR."""
    chunk_prompt = (
        "Transcribe the full text of this PDF page verbatim, in reading order. "
        "Capture every paragraph, heading, figure caption, table content, and "
        "footnote you can read. Do NOT summarize, paraphrase, or add commentary "
        "— output the literal text as it appears."
    )
    pieces: list[str] = []
    total_ms = 0
    n = len(image_paths)
    for i, ip in enumerate(image_paths):
        page_marker = f"=== page {i+1} ==="
        t0 = time.time()
        try:
            text, ms = call_claude_with_images(chunk_prompt, [ip], model, max_tokens=4_096)
        except Exception as e:
            text, ms = "", 0
            print(f"      [warn] page {i+1} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
        chunk_ms = int((time.time() - t0) * 1000)
        total_ms += chunk_ms
        if not text:
            text = "(empty)"
        pieces.append(f"{page_marker}\n{text}")
        if i % 10 == 0 or i == n - 1:
            print(f"      [chunk] {i+1}/{n} pages, {chunk_ms/1000:.1f}s, {len(text.split())} words", flush=True)
    return "\n\n".join(pieces), total_ms


def run(item: dict, run_dir: pathlib.Path, model: str):
    print(f"[run_dir] {run_dir}", flush=True)
    print(f"[paper]   {item['item_id']} ({item['page_count']}pp)  {item['title']}", flush=True)
    print(f"[claude_model] {model}", flush=True)

    ref_path = run_dir / "reference_transcript.txt"
    probes_path = run_dir / "probes.json"
    if not ref_path.exists():
        raise SystemExit(f"reference_transcript.txt not found in {run_dir}")
    if not probes_path.exists():
        raise SystemExit(f"probes.json not found in {run_dir}")

    reference = ref_path.read_text()
    probes = json.loads(probes_path.read_text()).get("probes", [])
    print(f"  [ref] reusing existing ({len(reference.split())} words)", flush=True)
    print(f"  [probes] reusing existing ({len(probes)} probes)", flush=True)

    image_paths = item["image_paths"]

    # Claude C0 — multimodal end-to-end review
    c0_path = run_dir / "review_C0_claude.txt"
    c0_skipped_path = run_dir / "review_C0_claude.SKIPPED"
    if c0_path.exists():
        print(f"  [C0-claude] reusing existing", flush=True)
        review_c0 = c0_path.read_text()
    elif c0_skipped_path.exists():
        print(f"  [C0-claude] previously skipped (too large)", flush=True)
        review_c0 = None
    else:
        print(f"  [C0-claude] {model} multimodal end-to-end review on {len(image_paths)} images...", flush=True)
        try:
            review_c0, ms = call_claude_with_images(REVIEW_PROMPT, image_paths, model, max_tokens=8_192)
            c0_path.write_text(review_c0)
            print(f"    C0-claude: {len(review_c0.split())} words ({ms/1000:.1f}s)", flush=True)
        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"    [skip] C0-claude failed ({err_msg}); proceeding with C1 only", flush=True)
            c0_skipped_path.write_text(err_msg)
            review_c0 = None

    # Claude C1 Pass-1 — chunked OCR (1 page/call)
    c1p1_path = run_dir / "transcript_C1_pass1_claude.txt"
    if c1p1_path.exists():
        print(f"  [C1.p1-claude] reusing existing", flush=True)
        c1_pass1 = c1p1_path.read_text()
    else:
        print(f"  [C1.p1-claude] {model} chunked OCR (1 page/call) on {len(image_paths)} pages...", flush=True)
        c1_pass1, ms = call_claude_chunked_ocr(image_paths, model)
        c1p1_path.write_text(c1_pass1)
        print(f"    C1.p1-claude: {len(c1_pass1.split())} words ({ms/1000:.1f}s)", flush=True)
    if not c1_pass1 or len(c1_pass1.split()) < 50:
        raise RuntimeError(f"C1 Pass-1 OCR too short ({len(c1_pass1.split())} words)")

    # Claude C1 Pass-2 — text-only review from Claude's transcript
    c1_path = run_dir / "review_C1_claude.txt"
    if c1_path.exists():
        print(f"  [C1.p2-claude] reusing existing", flush=True)
        review_c1 = c1_path.read_text()
    else:
        print(f"  [C1.p2-claude] {model} review from transcript...", flush=True)
        review_c1, ms = call_claude_text_only(pass2_review_prompt(c1_pass1), model, max_tokens=8_192)
        c1_path.write_text(review_c1)
        print(f"    C1-claude: {len(review_c1.split())} words ({ms/1000:.1f}s)", flush=True)

    # Score (uses GPT-5.4 judge against the existing Gemini-generated reference + probes)
    score_c0 = score_review(review_c0, reference, probes, "C0_claude", run_dir) if review_c0 is not None else None
    score_c1 = score_review(review_c1, reference, probes, "C1_claude", run_dir)

    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    if score_c0 is not None:
        summary.setdefault("scores", {})["C0_claude"] = asdict(score_c0)
        summary["review_C0_claude_word_count"] = len(review_c0.split())
    summary.setdefault("scores", {})["C1_claude"] = asdict(score_c1)
    summary["review_C1_claude_word_count"] = len(review_c1.split())
    summary["transcript_C1_pass1_claude_word_count"] = len(c1_pass1.split())
    summary["claude_model"] = model
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f"\n=== Claude {item['item_id']} ===", flush=True)
    for s in [score_c0, score_c1]:
        if s is None:
            print(f"  C0_claude  SKIPPED (request too large)", flush=True)
            continue
        print(
            f"  {s.condition}  halluc_score={s.halluc_score} (unsupported={s.n_unsupported})  "
            f"probe_cov={s.probe_coverage:.3f} ({s.n_covered}/{s.n_probes})  "
            f"final={s.final_score:.3f}",
            flush=True,
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--sample", type=pathlib.Path, required=True)
    ap.add_argument("--item", required=True, help="item_id from sample jsonl")
    ap.add_argument("--model", default=CLAUDE_MODEL_DEFAULT)
    args = ap.parse_args()

    items = [json.loads(l) for l in args.sample.open()]
    matched = [it for it in items if it["item_id"] == args.item]
    if not matched:
        raise SystemExit(f"item {args.item} not found in sample")
    run(matched[0], args.run_dir, args.model)


if __name__ == "__main__":
    main()
