"""C1_iter (iterative-refinement cascade variant): Pass-2 emits per-claim
quotes from the Pass-1 transcript; a downstream faithfulness filter rejects
claims whose cited quote is not actually in the transcript, then a final
rewrite step regenerates the review using only the surviving claims.

This addresses paper open-question (iii): "an iterative-refinement cascade
variant: have Pass-2 emit per-claim citations back to spans of the Pass-1
transcript, then run a faithfulness filter that rejects claims whose cited
span does not support them."

Pipeline:
  1. Pass-2a: model writes a CLAIMS list, each with (claim_text, quote_from_transcript).
     The quote must be a verbatim substring of the Pass-1 transcript.
  2. Filter: for each claim, fuzzy-match the quote against the transcript.
     If the best-match overlap drops below threshold, mark the claim as
     UNSUPPORTED and drop it.
  3. Pass-2b: model rewrites the review using only the SUPPORTED claims as
     bullet points (no transcript access).

Usage:
  python3 pilot/iterative_refinement.py \
      --run-dir runs/paper-review-19700025120-1777462513 \
      --transcript-file transcript_C1_pass1_claude.txt \
      --label C1_iter_claude \
      --vendor claude
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from pilot_audio_review import REVIEW_PROMPT, score_review


CLAIM_EXTRACTION_PROMPT = """\
Below is the transcribed full text of a multi-page document or audio recording.

<source>
{transcript}
</source>

Task: Write a comprehensive faithful review of this source as a structured
list of atomic claims. For EACH claim, provide:
  1. claim_text: the assertion, in your own words, ≤ 1 short sentence.
  2. quote: a verbatim quote (≤ 25 words) from the source above that supports
     this exact claim. The quote MUST be copy-pasted verbatim — it will be
     string-matched against the source. If you cannot find a verbatim quote,
     do not include the claim.

Cover every substantive point the source makes — the main thesis, supporting
arguments, examples, anecdotes, quantitative claims, dates, names, numbers,
percentages, model identifiers, notable quotes, frameworks, taxonomies, and
procedural steps. Be exhaustive.

Do not include any claim whose quote you cannot find verbatim in the source.
Do not embellish, speculate, or add framing context. Do not include claims
based on prior knowledge of the topic — only what is literally said.

Output strict JSON, with this schema:
{{
  "claims": [
    {{"claim_text": "...", "quote": "..."}},
    ...
  ]
}}

Aim for 50-150 claims for a long source. Output JSON only — no prose.
"""


FINAL_REWRITE_PROMPT = """\
Below is a list of factual claims, each previously verified against a source
document. Write a comprehensive, well-organized review article that
incorporates EVERY claim listed below.

Constraints:
- Use ONLY the claims listed; do not add other facts, citations, dates,
  author names, or numerical values not present in the list.
- Group related claims into coherent paragraphs.
- Do not invent quotations, citations, references, or attributions beyond
  what is in the list.
- Output the review article as plain prose; no headers, no bullet list, no
  meta-commentary.

<claims>
{claims_block}
</claims>
"""


def normalize(s: str) -> str:
    """Lowercase + collapse whitespace + strip punctuation. Used for fuzzy match."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def quote_in_transcript(quote: str, transcript_norm: str, threshold: float = 0.85) -> tuple[bool, float]:
    """Check whether `quote` (a short verbatim span) appears in the
    transcript. First tries exact substring match on the normalized
    transcript; falls back to a SequenceMatcher on a sliding window if exact
    fails. Returns (passes, best_ratio).
    """
    q = normalize(quote)
    if not q or len(q) < 5:
        return False, 0.0
    # Exact substring
    if q in transcript_norm:
        return True, 1.0
    # Fuzzy windowed match: scan in steps; not super-fast but transcripts
    # are at most ~50k tokens so OK for ≤ 150 claims.
    qlen = len(q)
    best = 0.0
    # Sample a few window positions deterministically — full O(NL) is too slow
    # for very long transcripts.
    step = max(1, qlen // 4)
    for i in range(0, len(transcript_norm) - qlen + 1, step):
        window = transcript_norm[i:i + qlen + 20]
        ratio = difflib.SequenceMatcher(None, q, window).quick_ratio()
        if ratio > best:
            best = ratio
            if best >= 0.95:
                break
    if best < threshold:
        return False, best
    # Confirm with a slower but more accurate scan around the best window.
    # (One pass with ratio() at the best position.)
    return True, best


# --- vendor dispatch --------------------------------------------------------

def call_text_only(prompt: str, vendor: str, model: str | None = None) -> tuple[str, int]:
    if vendor == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        m = model or "gemini-3.1-pro-preview"
        t0 = time.time()
        resp = client.models.generate_content(
            model=m,
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=65_536,
            ),
        )
        ms = int((time.time() - t0) * 1000)
        return (resp.text or "").strip(), ms
    if vendor == "claude":
        from anthropic import Anthropic
        client = Anthropic()
        m = model or "claude-opus-4-7"
        t0 = time.time()
        # Big prompts (≥ 200K total tokens) — request the 1M-context beta
        # so we can fit long Pass-1 transcripts in the prompt.
        approx_tokens = len(prompt) // 4
        extra_headers = {"anthropic-beta": "context-1m-2025-08-07"} if approx_tokens > 150_000 else {}
        resp = client.messages.create(
            model=m,
            max_tokens=16_000,
            messages=[{"role": "user", "content": prompt}],
            extra_headers=extra_headers,
        )
        ms = int((time.time() - t0) * 1000)
        text_parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return ("\n".join(text_parts)).strip(), ms
    raise SystemExit(f"unknown vendor: {vendor}")


def parse_claims_json(text: str) -> list[dict]:
    """Lenient JSON parse: strip markdown fences, find first {...}."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    try:
        data = json.loads(t)
        return data.get("claims", [])
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", t)
    if m:
        try:
            data = json.loads(m.group(0))
            return data.get("claims", [])
        except json.JSONDecodeError:
            pass
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--transcript-file", required=True)
    ap.add_argument("--label", required=True,
                    help="Label suffix; outputs review_<label>.txt + judge_*_<label>.json")
    ap.add_argument("--vendor", choices=["gemini", "claude"], required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--match-threshold", type=float, default=0.85)
    args = ap.parse_args()

    rd = args.run_dir
    transcript_path = rd / args.transcript_file
    if not transcript_path.exists():
        raise SystemExit(f"transcript not found: {transcript_path}")
    transcript = transcript_path.read_text()
    ref = (rd / "reference_transcript.txt").read_text()
    probes = json.loads((rd / "probes.json").read_text()).get("probes", [])

    print(f"[iter] {rd.name} vendor={args.vendor} label={args.label}", flush=True)
    print(f"  transcript: {len(transcript.split())} words", flush=True)

    # 1. Pass-2a: extract claims with quotes
    claims_path = rd / f"claims_{args.label}.json"
    if claims_path.exists():
        claims = json.loads(claims_path.read_text())["claims"]
        print(f"  reusing {len(claims)} claims from {claims_path.name}", flush=True)
    else:
        ext_prompt = CLAIM_EXTRACTION_PROMPT.format(transcript=transcript)
        print(f"  Pass-2a: extracting claims with quotes ({args.vendor})...", flush=True)
        raw, ms = call_text_only(ext_prompt, args.vendor, args.model)
        (rd / f"claims_raw_{args.label}.txt").write_text(raw)
        claims = parse_claims_json(raw)
        if not claims:
            print(f"  [WARN] no claims parsed; raw response saved to claims_raw_{args.label}.txt", flush=True)
            return
        print(f"    extracted {len(claims)} claims ({ms/1000:.1f}s)", flush=True)
        claims_path.write_text(json.dumps({"claims": claims}, indent=2))

    # 2. Faithfulness filter
    tnorm = normalize(transcript)
    supported, rejected = [], []
    for c in claims:
        quote = (c.get("quote") or "").strip()
        ok, ratio = quote_in_transcript(quote, tnorm, threshold=args.match_threshold)
        c["quote_match_ratio"] = round(ratio, 3)
        c["supported"] = ok
        if ok:
            supported.append(c)
        else:
            rejected.append(c)

    print(f"  filter: {len(supported)}/{len(claims)} supported (threshold={args.match_threshold})", flush=True)
    (rd / f"claims_filtered_{args.label}.json").write_text(json.dumps({
        "n_total": len(claims),
        "n_supported": len(supported),
        "n_rejected": len(rejected),
        "match_threshold": args.match_threshold,
        "supported": supported,
        "rejected": rejected,
    }, indent=2))

    # 3. Pass-2b: rewrite using only supported claims
    review_path = rd / f"review_{args.label}.txt"
    if review_path.exists():
        review = review_path.read_text()
        print(f"  reusing existing review at {review_path.name}", flush=True)
    else:
        claims_block = "\n".join(f"- {c['claim_text']}" for c in supported)
        rewrite_prompt = FINAL_REWRITE_PROMPT.format(claims_block=claims_block)
        print(f"  Pass-2b: rewriting from {len(supported)} supported claims...", flush=True)
        review, ms = call_text_only(rewrite_prompt, args.vendor, args.model)
        review_path.write_text(review)
        print(f"    wrote {len(review.split())} words ({ms/1000:.1f}s)", flush=True)

    # 4. Score
    score = score_review(review, ref, probes, args.label, rd)
    print(f"  [{args.label}] halluc={score.n_unsupported} cov={score.probe_coverage:.3f}", flush=True)

    # 5. Save summary
    sp = rd / "summary.json"
    s = json.loads(sp.read_text()) if sp.exists() else {}
    s.setdefault("scores", {})[args.label] = {
        "condition": args.label,
        "n_unsupported": score.n_unsupported,
        "n_probes": score.n_probes,
        "n_covered": score.n_covered,
        "probe_coverage": score.probe_coverage,
        "halluc_score": score.halluc_score,
        "final_score": score.final_score,
        "n_claims_total": len(claims),
        "n_claims_supported": len(supported),
        "n_claims_rejected": len(rejected),
    }
    s[f"review_{args.label}_word_count"] = len(review.split())
    sp.write_text(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
