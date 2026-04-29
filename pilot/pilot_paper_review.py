"""Phase-3 paper-as-images review protocol.

Mirrors `pilot_audio_review.py` but for multi-page PDFs treated as image
sequences (the scanned-paper case). Used for both:
  - Obscure scanned papers (NASA NTRS 1968-1972, etc.) where the model
    cannot rely on memorized content.
  - Recent papers where we want to compare the cascade against
    deterministic-OCR (pdftotext) as an additional baseline.

Same protocol as audio:
  - Reference: Gemini 3 Flash performs OCR on all page images.
  - C0: Gemini 3.1 Pro multimodal end-to-end → review article.
  - C1 cascade: Gemini 3.1 Pro Pass-1 OCR from images, Pass-2 review
    from own transcript (no images in Pass-2).
  - Probes: GPT-5.4 (reasoning_effort=high) extracts 30-50 atomic
    factual probes from the reference.
  - Judge: GPT-5.4 (reasoning_effort=high) hallucination + probe coverage.
  - Score: zero if any hallucination; else probe coverage rate.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from dataclasses import asdict, dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from google import genai
from google.genai import types
from openai import OpenAI

from pilot_audio_review import (
    HALLUCINATION_PROMPT,
    PROBE_CHECK_PROMPT,
    PROBE_EXTRACTION_PROMPT,
    REVIEW_PROMPT,
    call_gpt5_judge,
    parse_json,
    score_review,
)

REPO = pathlib.Path(__file__).resolve().parent.parent

# Paper-specific reference and Pass-1 prompt — asks for OCR rather than ASR.
REFERENCE_OCR_PROMPT = """\
Transcribe the full text of this multi-page document, page by page, in
reading order. Capture every paragraph, heading, figure caption, table
content, and footnote you can read. Use page markers like '=== page 1 ===',
'=== page 2 ===', etc. Do NOT summarize, paraphrase, or add commentary —
output the literal text as it appears."""


C1_PASS1_PROMPT = REFERENCE_OCR_PROMPT  # same prompt used by Pro for cascade Pass-1


def pass2_review_prompt(transcript: str) -> str:
    return (
        "Below is the transcribed full text of a multi-page document. "
        "Use ONLY this text to write the review article — do not assume "
        "anything not present here.\n\n"
        f"<document>\n{transcript}\n</document>\n\n"
        f"Task:\n{REVIEW_PROMPT}"
    )


def call_gemini_with_images(prompt: str, image_paths: list[str], model: str, max_output_tokens: int = 65_536):
    """Single Gemini call with all images attached — used for C0 review."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    parts: list = [prompt]
    for ip in image_paths:
        parts.append(types.Part.from_bytes(
            data=pathlib.Path(ip).read_bytes(),
            mime_type="image/png",
        ))
    t0 = time.time()
    resp = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.0, top_p=1.0, max_output_tokens=max_output_tokens
        ),
    )
    ms = int((time.time() - t0) * 1000)
    text = (resp.text or "").strip()
    if not text:
        cand = resp.candidates[0] if resp.candidates else None
        fr = getattr(cand, "finish_reason", "?") if cand else "?"
        u = resp.usage_metadata
        print(f"      [warn] empty Gemini response; finish_reason={fr}; usage={u}", flush=True)
    return text, ms


def call_gemini_chunked_ocr(image_paths: list[str], model: str, chunk_size: int = 1) -> tuple[str, int]:
    """Chunked OCR: process pages in small batches (default 1 page at a time)
    and concatenate the per-chunk transcripts. Avoids the long-input
    degenerate-loop failure mode observed on 104-page input.
    """
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    chunk_prompt = (
        "Transcribe the full text of this PDF page (or pages) verbatim, "
        "in reading order. Capture every paragraph, heading, figure caption, "
        "table content, and footnote you can read. Do NOT summarize, "
        "paraphrase, or add commentary — output the literal text as it appears."
    )
    pieces: list[str] = []
    total_ms = 0
    n = len(image_paths)
    for chunk_start in range(0, n, chunk_size):
        chunk_pages = image_paths[chunk_start:chunk_start + chunk_size]
        first_page = chunk_start + 1
        last_page = chunk_start + len(chunk_pages)
        page_marker = f"=== page {first_page} ===" if chunk_size == 1 else f"=== pages {first_page}-{last_page} ==="
        parts: list = [chunk_prompt]
        for ip in chunk_pages:
            parts.append(types.Part.from_bytes(
                data=pathlib.Path(ip).read_bytes(), mime_type="image/png",
            ))
        t0 = time.time()
        try:
            resp = client.models.generate_content(
                model=model, contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0.0, top_p=1.0, max_output_tokens=8_192,
                ),
            )
            chunk_text = (resp.text or "").strip()
        except Exception as e:
            chunk_text = ""
            print(f"      [warn] chunk {first_page}-{last_page} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
        chunk_ms = int((time.time() - t0) * 1000)
        total_ms += chunk_ms
        if not chunk_text:
            chunk_text = "(empty)"
        pieces.append(f"{page_marker}\n{chunk_text}")
        if chunk_start % 10 == 0 or chunk_start + chunk_size >= n:
            print(f"      [chunk] {last_page}/{n} pages, {chunk_ms/1000:.1f}s, {len(chunk_text.split())} words", flush=True)
    return "\n\n".join(pieces), total_ms


def call_gemini_text_only(prompt: str, model: str, max_output_tokens: int = 65_536):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    t0 = time.time()
    resp = client.models.generate_content(
        model=model, contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.0, top_p=1.0, max_output_tokens=max_output_tokens
        ),
    )
    ms = int((time.time() - t0) * 1000)
    text = (resp.text or "").strip()
    return text, ms


def run(item: dict, out_dir: pathlib.Path, pro_model: str, reference_model: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run_dir] {out_dir}", flush=True)
    print(f"[paper]   {item['item_id']} ({item['page_count']}pp)  {item['title']}", flush=True)

    image_paths = item["image_paths"]

    # 1. Reference OCR — chunked per page (avoids long-context loop)
    ref_path = out_dir / "reference_transcript.txt"
    if ref_path.exists():
        print(f"  [ref] reusing existing", flush=True)
        reference = ref_path.read_text()
    else:
        print(f"  [ref] generating with {reference_model} (chunked, 1 page/call) on {len(image_paths)} pages...", flush=True)
        reference, ms = call_gemini_chunked_ocr(image_paths, reference_model, chunk_size=1)
        ref_path.write_text(reference)
        print(f"    ref: {len(reference.split())} words ({ms/1000:.1f}s)", flush=True)
    if not reference or len(reference.split()) < 50:
        raise RuntimeError(f"Reference OCR too short ({len(reference.split())} words).")

    # 2. C0: end-to-end review
    c0_path = out_dir / "review_C0.txt"
    if c0_path.exists():
        print(f"  [C0] reusing existing", flush=True)
        review_c0 = c0_path.read_text()
    else:
        print(f"  [C0] {pro_model} end-to-end review...", flush=True)
        review_c0, ms = call_gemini_with_images(REVIEW_PROMPT, image_paths, pro_model)
        c0_path.write_text(review_c0)
        print(f"    C0: {len(review_c0.split())} words ({ms/1000:.1f}s)", flush=True)

    # 3. C1: cascade
    c1p1_path = out_dir / "transcript_C1_pass1.txt"
    if c1p1_path.exists():
        print(f"  [C1.p1] reusing existing", flush=True)
        c1_pass1 = c1p1_path.read_text()
    else:
        print(f"  [C1.p1] {pro_model} OCR (chunked, 1 page/call) on {len(image_paths)} pages...", flush=True)
        c1_pass1, ms = call_gemini_chunked_ocr(image_paths, pro_model, chunk_size=1)
        c1p1_path.write_text(c1_pass1)
        print(f"    C1.p1: {len(c1_pass1.split())} words ({ms/1000:.1f}s)", flush=True)

    c1_path = out_dir / "review_C1.txt"
    if c1_path.exists():
        print(f"  [C1.p2] reusing existing", flush=True)
        review_c1 = c1_path.read_text()
    else:
        if not c1_pass1:
            raise RuntimeError("C1 Pass-1 OCR is empty — cannot run Pass-2.")
        print(f"  [C1.p2] {pro_model} review from transcript...", flush=True)
        review_c1, ms = call_gemini_text_only(pass2_review_prompt(c1_pass1), pro_model)
        c1_path.write_text(review_c1)
        print(f"    C1: {len(review_c1.split())} words ({ms/1000:.1f}s)", flush=True)

    # 4. Probes via GPT-5.4
    probes_path = out_dir / "probes.json"
    if probes_path.exists():
        print(f"  [probes] reusing existing", flush=True)
        probes = json.loads(probes_path.read_text()).get("probes", [])
    else:
        print(f"  [probes] extracting with GPT-5.4...", flush=True)
        pe = PROBE_EXTRACTION_PROMPT.replace("{transcript}", reference[:120_000])
        text, ms = call_gpt5_judge(pe, max_completion_tokens=16_384)
        probes = parse_json(text).get("probes", [])
        probes_path.write_text(json.dumps({"probes": probes}, indent=2))
        print(f"    probes: {len(probes)} ({ms/1000:.1f}s)", flush=True)

    # 5. Score
    score_c0 = score_review(review_c0, reference, probes, "C0", out_dir)
    score_c1 = score_review(review_c1, reference, probes, "C1", out_dir)

    summary = {
        "item_id": item["item_id"],
        "title": item["title"],
        "page_count": item["page_count"],
        "models": {
            "reference_ocr": reference_model,
            "review_under_test": pro_model,
            "judge": "gpt-5.4 (reasoning_effort=high)",
        },
        "reference_word_count": len(reference.split()),
        "pdftotext_word_count": item.get("pdftotext_word_count"),
        "review_C0_word_count": len(review_c0.split()),
        "review_C1_word_count": len(review_c1.split()),
        "transcript_C1_pass1_word_count": len(c1_pass1.split()),
        "n_probes": len(probes),
        "scores": {"C0": asdict(score_c0), "C1": asdict(score_c1)},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n=== Summary ({item['item_id']}) ===", flush=True)
    for s in [score_c0, score_c1]:
        print(
            f"  {s.condition}  halluc_score={s.halluc_score} (unsupported={s.n_unsupported})  "
            f"probe_cov={s.probe_coverage:.3f} ({s.n_covered}/{s.n_probes})  "
            f"final={s.final_score:.3f}",
            flush=True,
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=pathlib.Path, required=True,
                    help="Path to pilot_sample.jsonl with item_id, title, image_paths, page_count")
    ap.add_argument("--items", default=None, help="Comma-separated item_ids (default: all)")
    ap.add_argument("--pro-model", default="gemini-3.1-pro-preview")
    ap.add_argument("--reference-model", default="gemini-3.1-pro-preview")
    ap.add_argument("--run-dir", type=pathlib.Path, default=None,
                    help="Reuse an existing run-dir (resumes from cached files); only valid with single --items")
    args = ap.parse_args()

    items = [json.loads(l) for l in args.sample.open()]
    if args.items:
        wanted = set(args.items.split(","))
        items = [it for it in items if it["item_id"] in wanted]
    print(f"[items] {len(items)}", flush=True)
    if args.run_dir is not None and len(items) != 1:
        raise SystemExit("--run-dir requires exactly one item via --items")

    for item in items:
        out_dir = args.run_dir or REPO / "runs" / f"paper-review-{item['item_id']}-{int(time.time())}"
        try:
            run(item, out_dir, args.pro_model, args.reference_model)
        except Exception as e:
            print(f"  FAILED {item['item_id']}: {type(e).__name__}: {str(e)[:200]}", flush=True)


if __name__ == "__main__":
    main()
