"""LLM-as-judge scorer for long-form generation tasks.

Given a generated summary and a reference text (the source paper / transcript),
the judge:
  1. Atomizes the summary into discrete claims.
  2. For each claim, marks it as SUPPORTED, UNSUPPORTED (hallucinated), or CONTRADICTED
     by the reference.
  3. Returns counts + examples.

Also scores recall: given a held-out set of "key reference claims" (extracted
separately by a second judge call on the reference alone), how many are covered
by the summary?
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

JUDGE_MODEL = "gemini-3.1-pro-preview"


@dataclass
class JudgeScore:
    n_claims: int
    n_supported: int
    n_unsupported: int
    n_contradicted: int
    supported_rate: float  # precision
    claims_detail: list[dict]  # each entry: {"claim": ..., "verdict": ..., "note": ...}


def _client():
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _parse_json_output(text: str) -> Any:
    # Models often wrap JSON in ```json``` fences; strip them.
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return json.loads(t)


FAITHFULNESS_PROMPT = """\
You are a faithfulness judge. Given a generated SUMMARY and the REFERENCE DOCUMENT
it was supposedly based on, decompose the summary into atomic factual claims and
verify each claim against the reference.

For each claim, label it:
  - SUPPORTED: the claim is directly stated or clearly implied by the reference.
  - UNSUPPORTED: the reference does not say this (neither supports nor contradicts).
  - CONTRADICTED: the reference states something incompatible.

Rules:
- A claim is "atomic" if it makes exactly one factual assertion.
- Common knowledge or framing statements ("this paper discusses X") don't count
  unless they make a specific factual assertion about the paper's content.
- Numerical claims must match the reference's numbers to count as SUPPORTED.
- Quotes must match the reference verbatim to count as SUPPORTED; paraphrases
  are SUPPORTED only if semantically equivalent.

Output strict JSON:

{
  "claims": [
    {"claim": "<atomic claim>", "verdict": "SUPPORTED|UNSUPPORTED|CONTRADICTED", "note": "<1 sentence reason>"}
  ]
}

REFERENCE DOCUMENT (may be truncated for length):
<<<
{reference}
>>>

GENERATED SUMMARY:
<<<
{summary}
>>>

JSON output:"""


def score_faithfulness(summary: str, reference: str, reference_char_limit: int = 80_000) -> JudgeScore:
    """Return hallucination-style audit of `summary` vs `reference`."""
    ref_trunc = reference[:reference_char_limit]
    prompt = FAITHFULNESS_PROMPT.format(reference=ref_trunc, summary=summary)

    client = _client()
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=JUDGE_MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0, top_p=1.0, max_output_tokens=8192
                ),
            )
            parsed = _parse_json_output(resp.text or "")
            break
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(5)

    claims = parsed.get("claims", [])
    n_supported = sum(1 for c in claims if c.get("verdict") == "SUPPORTED")
    n_unsupported = sum(1 for c in claims if c.get("verdict") == "UNSUPPORTED")
    n_contradicted = sum(1 for c in claims if c.get("verdict") == "CONTRADICTED")
    n_claims = max(1, len(claims))
    return JudgeScore(
        n_claims=len(claims),
        n_supported=n_supported,
        n_unsupported=n_unsupported,
        n_contradicted=n_contradicted,
        supported_rate=n_supported / n_claims,
        claims_detail=claims,
    )


COVERAGE_PROMPT = """\
You are extracting the most important factual claims from a REFERENCE DOCUMENT
so a downstream step can check whether a summary covered them.

Return the 15-25 most important, distinct, atomic factual claims. Prefer claims
that are:
- Specific (concrete numbers, names, dates) over generic ("the paper talks about X").
- Core to the document's argument (thesis, key results, methodology steps,
  stated limitations) over decorative.

Output strict JSON:
{"key_claims": ["<claim 1>", "<claim 2>", ...]}

REFERENCE DOCUMENT (may be truncated):
<<<
{reference}
>>>

JSON output:"""


COVERAGE_CHECK_PROMPT = """\
You are checking whether a GENERATED SUMMARY covers a list of KEY CLAIMS from
a reference document.

For each key claim, say COVERED if the summary contains it (verbatim or clear
paraphrase) or MISSING if it does not.

Output strict JSON:
{"coverage": [{"claim": "<claim>", "status": "COVERED|MISSING"}, ...]}

KEY CLAIMS:
<<<
{claims}
>>>

GENERATED SUMMARY:
<<<
{summary}
>>>

JSON output:"""


def score_coverage(summary: str, reference: str, reference_char_limit: int = 80_000) -> dict:
    """Return coverage of reference's key claims in the summary."""
    client = _client()
    ref_trunc = reference[:reference_char_limit]

    # Step 1: extract key claims from reference
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=JUDGE_MODEL,
                contents=[COVERAGE_PROMPT.format(reference=ref_trunc)],
                config=types.GenerateContentConfig(
                    temperature=0.0, top_p=1.0, max_output_tokens=4096
                ),
            )
            key_claims = _parse_json_output(resp.text or "").get("key_claims", [])
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)

    # Step 2: check coverage in the summary
    claims_json = json.dumps(key_claims, indent=2)
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=JUDGE_MODEL,
                contents=[COVERAGE_CHECK_PROMPT.format(claims=claims_json, summary=summary)],
                config=types.GenerateContentConfig(
                    temperature=0.0, top_p=1.0, max_output_tokens=4096
                ),
            )
            coverage = _parse_json_output(resp.text or "").get("coverage", [])
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)

    n_covered = sum(1 for c in coverage if c.get("status") == "COVERED")
    n_total = max(1, len(coverage))
    return {
        "n_key_claims": len(coverage),
        "n_covered": n_covered,
        "coverage_rate": n_covered / n_total,
        "key_claims": key_claims,
        "per_claim": coverage,
    }
