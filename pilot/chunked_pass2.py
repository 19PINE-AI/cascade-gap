"""Chunked Pass-2 variant (C1*) for paper-review cells.

Pre-registered prediction from research_log/2026-04-29_phase3_heatpipes.md:
the +6 pp coverage gain on Heat Pipes (104pp, 22k-word transcript) is bottlenecked
by Pass-2 having to compress 22k -> 1.8k. Splitting Pass-2 into chunked
summarization should relieve that bottleneck and bring coverage closer to the
+12-16 pp range seen on smaller papers.

This script reuses an existing run-dir (with reference_transcript.txt,
probes.json, transcript_C1_pass1.txt, review_C0.txt) and produces a new
C1c (chunked Pass-2) review + judge outputs.

Usage:
  python3 pilot/chunked_pass2.py --run-dir runs/paper-review-19700025120-1777462513
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from pilot_audio_review import (
    REVIEW_PROMPT,
    parse_json,
    score_review,
)
from pilot_paper_review import call_gemini_text_only
from pilot_paper_review_claude import call_claude_text_only


def _text_only(prompt: str, vendor: str, model: str, max_tokens: int = 8_192) -> tuple[str, int]:
    if vendor == "gemini":
        return call_gemini_text_only(prompt, model, max_output_tokens=max_tokens)
    if vendor == "claude":
        return call_claude_text_only(prompt, model, max_tokens=max_tokens)
    raise ValueError(f"unknown vendor: {vendor}")


SUB_SUMMARY_PROMPT_TMPL = """\
Below is section {i}/{N} of a longer multi-page document's transcript. Extract
the substantive content of THIS SECTION as a faithful prose summary, covering:
- main points and arguments made in this section,
- quantitative claims (numbers, equations, parameters, dates),
- specific named entities (authors, materials, instruments, prior work cited),
- key examples, figures, or tables.

Target length: ~{target_words} words. Be exhaustive about substantive points but
do not add anything not stated in this section.

<section>
{chunk}
</section>
"""


MERGE_PROMPT_TMPL = """\
Below are consecutive section summaries of a longer document, in reading order.
Merge them into a single coherent comprehensive review article.

Use ONLY the content in these section summaries — do not add anything not present.
Preserve every substantive point, quantitative claim, named entity, and key
example. Do not drop content for stylistic flow.

<section_summaries>
{sub_summaries}
</section_summaries>

Task:
""" + REVIEW_PROMPT


def split_transcript(transcript: str, n_chunks: int) -> list[str]:
    """Split by word count, breaking on the closest paragraph (\\n\\n) boundary
    to avoid mid-paragraph cuts."""
    paragraphs = transcript.split("\n\n")
    total_words = sum(len(p.split()) for p in paragraphs)
    target_per_chunk = total_words / n_chunks

    chunks: list[list[str]] = [[]]
    word_count = 0
    for p in paragraphs:
        chunks[-1].append(p)
        word_count += len(p.split())
        if word_count >= target_per_chunk and len(chunks) < n_chunks:
            chunks.append([])
            word_count = 0
    return ["\n\n".join(c) for c in chunks if c]


def chunked_pass2(
    transcript: str,
    vendor: str,
    model: str,
    n_chunks: int,
    sub_summary_words: int,
) -> tuple[str, list[str], int]:
    """Map: per-chunk sub-summary. Reduce: merge into single review."""
    chunks = split_transcript(transcript, n_chunks)
    print(f"  [C1c-{vendor}] split transcript ({len(transcript.split())} words) into {len(chunks)} chunk(s)", flush=True)

    sub_summaries: list[str] = []
    total_ms = 0
    for i, chunk in enumerate(chunks, 1):
        prompt = SUB_SUMMARY_PROMPT_TMPL.format(
            i=i, N=len(chunks), target_words=sub_summary_words, chunk=chunk,
        )
        print(f"    [chunk {i}/{len(chunks)}] {len(chunk.split())} words -> sub-summary...", flush=True)
        sub, ms = _text_only(prompt, vendor, model)
        total_ms += ms
        if not sub:
            sub = "(empty)"
        sub_summaries.append(f"=== Section {i}/{len(chunks)} ===\n{sub}")
        print(f"      sub-summary: {len(sub.split())} words ({ms/1000:.1f}s)", flush=True)

    print(f"  [C1c-{vendor}] merging {len(sub_summaries)} sub-summaries...", flush=True)
    merge_input = "\n\n".join(sub_summaries)
    print(f"    merge-input: {len(merge_input.split())} words", flush=True)
    merge_prompt = MERGE_PROMPT_TMPL.format(sub_summaries=merge_input)
    review, ms = _text_only(merge_prompt, vendor, model)
    total_ms += ms
    print(f"    C1c review: {len(review.split())} words ({ms/1000:.1f}s)", flush=True)
    return review, sub_summaries, total_ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--vendor", choices=["gemini", "claude"], default="gemini")
    ap.add_argument("--model", default=None,
                    help="Defaults: gemini-3.1-pro-preview for gemini; claude-opus-4-7 for claude")
    ap.add_argument("--label", default=None,
                    help="Label suffix for outputs. Default: C1c (gemini) or C1c_claude (claude)")
    ap.add_argument("--transcript-file", default=None,
                    help="Filename within run-dir to use as the transcript source. "
                         "Default: transcript_C1_pass1.txt (gemini) or transcript_C1_pass1_claude.txt (claude)")
    ap.add_argument("--n-chunks", type=int, default=5)
    ap.add_argument("--sub-summary-words", type=int, default=500)
    args = ap.parse_args()

    rd = args.run_dir
    if not rd.exists():
        raise SystemExit(f"run-dir not found: {rd}")

    if args.model is None:
        args.model = {"gemini": "gemini-3.1-pro-preview", "claude": "claude-opus-4-7"}[args.vendor]
    if args.label is None:
        args.label = {"gemini": "C1c", "claude": "C1c_claude"}[args.vendor]
    if args.transcript_file is None:
        args.transcript_file = {
            "gemini": "transcript_C1_pass1.txt",
            "claude": "transcript_C1_pass1_claude.txt",
        }[args.vendor]

    ref = (rd / "reference_transcript.txt").read_text()
    transcript = (rd / args.transcript_file).read_text()
    probes = json.loads((rd / "probes.json").read_text()).get("probes", [])
    if not probes:
        raise SystemExit("probes.json missing or empty")

    print(f"[vendor] {args.vendor} ({args.model})", flush=True)
    print(f"[label]  {args.label}", flush=True)
    print(f"[transcript] {args.transcript_file} ({len(transcript.split())} words)", flush=True)

    # Run chunked Pass-2 (skip if cached)
    c1c_path = rd / f"review_{args.label}.txt"
    sub_path = rd / f"review_{args.label}_subsummaries.txt"
    if c1c_path.exists():
        print(f"  [{args.label}] reusing existing {c1c_path.name}", flush=True)
        review_c1c = c1c_path.read_text()
    else:
        review_c1c, sub_summaries, _ms = chunked_pass2(
            transcript, args.vendor, args.model, args.n_chunks, args.sub_summary_words,
        )
        c1c_path.write_text(review_c1c)
        sub_path.write_text("\n\n".join(sub_summaries))

    # Also write the concatenated sub-summaries as a separate condition for completeness
    concat_label = f"{args.label}_concat"
    concat_path = rd / f"review_{concat_label}.txt"
    if not concat_path.exists() and sub_path.exists():
        concat_path.write_text(sub_path.read_text())

    # Score both
    score_c1c = score_review(review_c1c, ref, probes, args.label, rd)
    if concat_path.exists():
        review_concat = concat_path.read_text()
        score_concat = score_review(review_concat, ref, probes, concat_label, rd)
    else:
        score_concat = None

    # Update / write summary
    main_summary_path = rd / "summary.json"
    main_summary = json.loads(main_summary_path.read_text()) if main_summary_path.exists() else {}
    scores = main_summary.setdefault("scores", {})
    scores[args.label] = asdict(score_c1c)
    main_summary[f"review_{args.label}_word_count"] = len(review_c1c.split())
    if score_concat:
        scores[concat_label] = asdict(score_concat)
        main_summary[f"review_{concat_label}_word_count"] = len(concat_path.read_text().split())
    main_summary[f"chunked_pass2_config_{args.label}"] = {
        "vendor": args.vendor,
        "model": args.model,
        "n_chunks": args.n_chunks,
        "sub_summary_words": args.sub_summary_words,
        "source_transcript": args.transcript_file,
    }
    main_summary_path.write_text(json.dumps(main_summary, indent=2))

    print(f"\n=== {args.label} Summary ===", flush=True)
    for s in [score_c1c] + ([score_concat] if score_concat else []):
        print(
            f"  {s.condition}  halluc_score={s.halluc_score} (unsupported={s.n_unsupported})  "
            f"probe_cov={s.probe_coverage:.3f} ({s.n_covered}/{s.n_probes})  "
            f"final={s.final_score:.3f}",
            flush=True,
        )

    # Print comparison context if existing C0/C1 in summary
    for k in ("C0", "C1", "C0_claude", "C1_claude"):
        s = main_summary.get("scores", {}).get(k)
        if s:
            print(
                f"  (ref) {k}  unsupported={s['n_unsupported']}  "
                f"probe_cov={s['probe_coverage']:.3f} ({s['n_covered']}/{s['n_probes']})",
                flush=True,
            )


if __name__ == "__main__":
    main()
