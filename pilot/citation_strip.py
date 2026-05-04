"""Citation-stripped Pass-2: replace bibliographic surface forms in the
cascade transcript with neutral placeholders, then re-run Pass-2.

Hypothesis: Mode B (training-prior leak) is triggered by surface forms
like 'Reference 5', '[12]', 'Ref. 2 (Cotter)' that prompt the model to
expand abbreviated citations from prior knowledge. If we strip these
surface forms, Pass-2 from the stripped transcript should hallucinate less.

Usage:
  python3 pilot/citation_strip.py \
      --run-dir runs/paper-review-19700025120-1777462513 \
      --transcript-file transcript_C1_pass1_claude.txt \
      --vendor claude \
      --label C1_stripped_claude
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from pilot_audio_review import score_review
from pilot_paper_review import pass2_review_prompt as pass2_paper_prompt
from pilot_paper_review_claude import call_claude_text_only
from pilot_paper_review import call_gemini_text_only


# Common citation surface forms in scientific papers:
# Numeric brackets: [1], [2-5], [1, 5, 9]
# Word forms: Reference 12, Ref. 2, Refs. 11 and 12
# Author-year is harder to strip without a bibliography lookup, so we leave it.
CITATION_PATTERNS = [
    # Numeric brackets like [12], [2-5], [3, 7]
    (re.compile(r"\[\s*\d+(?:\s*[-–,]\s*\d+)*\s*\]"), "[REF]"),
    # "Reference N", "References N and N", "Refs. N-N", "Ref. N"
    (re.compile(
        r"\b(?:references?|refs?\.?)\s+\d+(?:\s*(?:[-–,]|\band\b)\s*\d+)*",
        re.IGNORECASE,
    ), "[REF]"),
]


def strip_citations(text: str) -> tuple[str, dict[str, int]]:
    """Replace citation surface forms with [REF]. Return (stripped_text, stats)."""
    stats: dict[str, int] = {}
    out = text
    for pattern, repl in CITATION_PATTERNS:
        before = out
        out = pattern.sub(repl, out)
        n = len(pattern.findall(before))
        stats[pattern.pattern[:40]] = n
    stats["total"] = sum(stats.values())
    return out, stats


def _text_only(prompt: str, vendor: str, model: str, max_tokens: int = 8_192) -> tuple[str, int]:
    if vendor == "gemini":
        return call_gemini_text_only(prompt, model, max_output_tokens=max_tokens)
    if vendor == "claude":
        return call_claude_text_only(prompt, model, max_tokens=max_tokens)
    raise ValueError(f"unknown vendor: {vendor}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--transcript-file", required=True)
    ap.add_argument("--vendor", choices=["gemini", "claude"], required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--label", required=True,
                    help="Label for outputs, e.g. C1_stripped_claude")
    args = ap.parse_args()

    rd = args.run_dir
    if not rd.exists():
        raise SystemExit(f"run-dir not found: {rd}")

    if args.model is None:
        args.model = {"gemini": "gemini-3.1-pro-preview", "claude": "claude-opus-4-7"}[args.vendor]

    src_path = rd / args.transcript_file
    if not src_path.exists():
        raise SystemExit(f"transcript file not found: {src_path}")
    transcript = src_path.read_text()
    print(f"[input] {src_path.name} ({len(transcript.split())} words)", flush=True)

    stripped, stats = strip_citations(transcript)
    stripped_path = rd / f"{args.transcript_file.replace('.txt', '_stripped.txt')}"
    stripped_path.write_text(stripped)
    print(f"[strip] {stats['total']} citation surface forms replaced", flush=True)
    for k, v in stats.items():
        if k != "total":
            print(f"        pattern '{k}...': {v}", flush=True)
    print(f"[output] {stripped_path.name} ({len(stripped.split())} words)", flush=True)

    review_path = rd / f"review_{args.label}.txt"
    if review_path.exists():
        print(f"  [{args.label}] reusing existing review", flush=True)
        review = review_path.read_text()
    else:
        prompt = pass2_paper_prompt(stripped)
        print(f"  [{args.label}] running Pass-2 with {args.vendor} ({args.model})...", flush=True)
        review, ms = _text_only(prompt, args.vendor, args.model)
        review_path.write_text(review)
        print(f"    {args.label}: {len(review.split())} words ({ms/1000:.1f}s)", flush=True)

    # Score
    ref = (rd / "reference_transcript.txt").read_text()
    probes = json.loads((rd / "probes.json").read_text()).get("probes", [])
    score = score_review(review, ref, probes, args.label, rd)

    # Update summary
    sp = rd / "summary.json"
    s = json.loads(sp.read_text()) if sp.exists() else {}
    s.setdefault("scores", {})[args.label] = asdict(score)
    s[f"review_{args.label}_word_count"] = len(review.split())
    s[f"citation_strip_stats_{args.label}"] = stats
    sp.write_text(json.dumps(s, indent=2))

    print(f"\n=== {args.label} ===", flush=True)
    print(
        f"  {args.label}  halluc={score.n_unsupported}  "
        f"cov={score.probe_coverage:.3f} ({score.n_covered}/{score.n_probes})",
        flush=True,
    )
    for k in ("C0_claude", "C1_claude", "C0", "C1"):
        v = s["scores"].get(k)
        if v:
            print(f"  (ref) {k}  halluc={v['n_unsupported']}  cov={v['probe_coverage']:.3f}", flush=True)


if __name__ == "__main__":
    main()
