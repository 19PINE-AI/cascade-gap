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
    pro_model: str,
    n_chunks: int,
    sub_summary_words: int,
) -> tuple[str, list[str], int]:
    """Map: per-chunk sub-summary. Reduce: merge into single review."""
    chunks = split_transcript(transcript, n_chunks)
    print(f"  [C1c] split transcript ({len(transcript.split())} words) into {len(chunks)} chunk(s)", flush=True)

    sub_summaries: list[str] = []
    total_ms = 0
    for i, chunk in enumerate(chunks, 1):
        prompt = SUB_SUMMARY_PROMPT_TMPL.format(
            i=i, N=len(chunks), target_words=sub_summary_words, chunk=chunk,
        )
        print(f"    [chunk {i}/{len(chunks)}] {len(chunk.split())} words -> sub-summary...", flush=True)
        sub, ms = call_gemini_text_only(prompt, pro_model, max_output_tokens=8_192)
        total_ms += ms
        if not sub:
            sub = "(empty)"
        sub_summaries.append(f"=== Section {i}/{len(chunks)} ===\n{sub}")
        print(f"      sub-summary: {len(sub.split())} words ({ms/1000:.1f}s)", flush=True)

    print(f"  [C1c] merging {len(sub_summaries)} sub-summaries...", flush=True)
    merge_input = "\n\n".join(sub_summaries)
    print(f"    merge-input: {len(merge_input.split())} words", flush=True)
    merge_prompt = MERGE_PROMPT_TMPL.format(sub_summaries=merge_input)
    review, ms = call_gemini_text_only(merge_prompt, pro_model, max_output_tokens=8_192)
    total_ms += ms
    print(f"    C1c review: {len(review.split())} words ({ms/1000:.1f}s)", flush=True)
    return review, sub_summaries, total_ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--pro-model", default="gemini-3.1-pro-preview")
    ap.add_argument("--n-chunks", type=int, default=5)
    ap.add_argument("--sub-summary-words", type=int, default=500)
    args = ap.parse_args()

    rd = args.run_dir
    if not rd.exists():
        raise SystemExit(f"run-dir not found: {rd}")

    ref = (rd / "reference_transcript.txt").read_text()
    transcript = (rd / "transcript_C1_pass1.txt").read_text()
    probes = json.loads((rd / "probes.json").read_text()).get("probes", [])
    if not probes:
        raise SystemExit("probes.json missing or empty")

    # Run chunked Pass-2 (skip if cached)
    c1c_path = rd / "review_C1c.txt"
    sub_path = rd / "review_C1c_subsummaries.txt"
    if c1c_path.exists():
        print(f"  [C1c] reusing existing {c1c_path.name}", flush=True)
        review_c1c = c1c_path.read_text()
    else:
        review_c1c, sub_summaries, _ms = chunked_pass2(
            transcript, args.pro_model, args.n_chunks, args.sub_summary_words,
        )
        c1c_path.write_text(review_c1c)
        sub_path.write_text("\n\n".join(sub_summaries))

    # Score
    score_c1c = score_review(review_c1c, ref, probes, "C1c", rd)

    # Update / write summary_chunked.json
    main_summary_path = rd / "summary.json"
    main_summary = json.loads(main_summary_path.read_text()) if main_summary_path.exists() else {}
    main_summary.setdefault("scores", {})["C1c"] = asdict(score_c1c)
    main_summary["review_C1c_word_count"] = len(review_c1c.split())
    main_summary["chunked_pass2_config"] = {
        "n_chunks": args.n_chunks,
        "sub_summary_words": args.sub_summary_words,
    }
    main_summary_path.write_text(json.dumps(main_summary, indent=2))

    print(f"\n=== C1c Summary ===", flush=True)
    print(
        f"  C1c  halluc_score={score_c1c.halluc_score} (unsupported={score_c1c.n_unsupported})  "
        f"probe_cov={score_c1c.probe_coverage:.3f} ({score_c1c.n_covered}/{score_c1c.n_probes})  "
        f"final={score_c1c.final_score:.3f}",
        flush=True,
    )

    # Print comparison context if existing C0/C1 in summary
    for k in ("C0", "C1"):
        s = main_summary.get("scores", {}).get(k)
        if s:
            print(
                f"  (ref) {k}  unsupported={s['n_unsupported']}  "
                f"probe_cov={s['probe_coverage']:.3f} ({s['n_covered']}/{s['n_probes']})",
                flush=True,
            )


if __name__ == "__main__":
    main()
