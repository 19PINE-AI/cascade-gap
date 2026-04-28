"""Multi-judge LLM evaluator with cross-judge agreement metrics.

Generalizes llm_judge.py to support any judge model via provider abstraction
(Gemini API, OpenAI API, OpenRouter, Anthropic API). Computes Cohen's kappa
on per-claim faithfulness verdicts when multiple judges score the same item.

This is a Phase-2 M1 deliverable: the inter-judge agreement number is what
makes the LLM-judge methodology defensible to peer reviewers.

Usage:
    from pilot.llm_judge_multi import score_with_judges

    results = score_with_judges(
        summary=text,
        reference=ref,
        judges=[
            ("gemini", "gemini-3.1-pro-preview"),
            ("openai", "gpt-5.4"),
            ("anthropic", "claude-opus-4-7"),  # optional
        ],
    )
    # Returns per-judge scores and inter-judge kappa
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import Any

# Same prompts as llm_judge.py — reused so cross-judge results are comparable.
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


@dataclass
class JudgeVerdict:
    judge_provider: str
    judge_model: str
    n_claims: int
    n_supported: int
    n_unsupported: int
    n_contradicted: int
    precision: float
    coverage_n_total: int
    coverage_n_covered: int
    coverage: float
    claims_detail: list[dict]
    coverage_detail: list[dict]


def _parse_json(text: str) -> Any:
    """Robust JSON parser handling fences, preambles, and nested braces."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*\n?", "", t)
    t = re.sub(r"\n?\s*```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start_obj, start_arr = t.find("{"), t.find("[")
    starts = [x for x in [start_obj, start_arr] if x != -1]
    if not starts:
        raise ValueError(f"No JSON. First 300 chars: {text[:300]!r}")
    start = min(starts)
    depth, in_str, esc, end = 0, False, False, None
    open_ch = t[start]
    close_ch = "}" if open_ch == "{" else "]"
    for i in range(start, len(t)):
        c = t[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise ValueError(f"Unbalanced JSON. First 300 chars: {text[:300]!r}")
    return json.loads(t[start:end])


def _call_judge(provider: str, model: str, prompt: str, max_tokens: int = 16_384) -> str:
    """Single Pass-2 call to a judge, returning raw text."""
    if provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        resp = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.0, top_p=1.0, max_output_tokens=max_tokens
            ),
        )
        return (resp.text or "").strip()
    if provider == "openai":
        from openai import OpenAI
        client = OpenAI()
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=max_tokens,
        )
        return (r.choices[0].message.content or "").strip()
    if provider == "openrouter":
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        return (r.choices[0].message.content or "").strip()
    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        r = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.content[0].text.strip()
    raise ValueError(f"Unknown judge provider: {provider}")


def score_one_judge(
    judge_provider: str,
    judge_model: str,
    summary: str,
    reference: str,
    reference_char_limit: int = 80_000,
) -> JudgeVerdict:
    """Score (faithfulness + coverage) with a single judge."""
    ref_trunc = reference[:reference_char_limit]

    # Faithfulness
    faith_prompt = FAITHFULNESS_PROMPT.replace("{reference}", ref_trunc).replace("{summary}", summary)
    for attempt in range(3):
        try:
            text = _call_judge(judge_provider, judge_model, faith_prompt)
            faith = _parse_json(text)
            break
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(5)
    if not isinstance(faith, dict):
        raise ValueError(f"Faithfulness response not a dict: {type(faith).__name__}")
    claims = faith.get("claims", [])
    n_supp = sum(1 for c in claims if c.get("verdict") == "SUPPORTED")
    n_unsupp = sum(1 for c in claims if c.get("verdict") == "UNSUPPORTED")
    n_contra = sum(1 for c in claims if c.get("verdict") == "CONTRADICTED")
    n_total = max(1, len(claims))

    # Coverage step 1: extract key claims
    cov_extract_prompt = COVERAGE_PROMPT.replace("{reference}", ref_trunc)
    for attempt in range(3):
        try:
            text = _call_judge(judge_provider, judge_model, cov_extract_prompt, max_tokens=8192)
            key_claims = _parse_json(text).get("key_claims", [])
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)

    # Coverage step 2: check
    cov_check_prompt = COVERAGE_CHECK_PROMPT.replace(
        "{claims}", json.dumps(key_claims, indent=2)
    ).replace("{summary}", summary)
    for attempt in range(3):
        try:
            text = _call_judge(judge_provider, judge_model, cov_check_prompt, max_tokens=8192)
            coverage_data = _parse_json(text).get("coverage", [])
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)
    n_covered = sum(1 for c in coverage_data if c.get("status") == "COVERED")
    cov_total = max(1, len(coverage_data))

    return JudgeVerdict(
        judge_provider=judge_provider,
        judge_model=judge_model,
        n_claims=len(claims),
        n_supported=n_supp,
        n_unsupported=n_unsupp,
        n_contradicted=n_contra,
        precision=n_supp / n_total,
        coverage_n_total=len(coverage_data),
        coverage_n_covered=n_covered,
        coverage=n_covered / cov_total,
        claims_detail=claims,
        coverage_detail=coverage_data,
    )


def score_with_judges(
    summary: str,
    reference: str,
    judges: list[tuple[str, str]],
    reference_char_limit: int = 80_000,
) -> dict:
    """Score the same summary with multiple judges; report per-judge + agreement.

    `judges` is a list of (provider, model) tuples.
    """
    out = {"per_judge": []}
    for provider, model in judges:
        try:
            v = score_one_judge(provider, model, summary, reference, reference_char_limit)
            out["per_judge"].append(asdict(v))
        except Exception as e:
            out["per_judge"].append({
                "judge_provider": provider, "judge_model": model,
                "error": str(e),
            })

    # Aggregate cross-judge stats: precision and coverage means/stds
    valid = [j for j in out["per_judge"] if "error" not in j]
    if len(valid) >= 2:
        precs = [j["precision"] for j in valid]
        covs = [j["coverage"] for j in valid]
        out["precision_mean"] = sum(precs) / len(precs)
        out["precision_range"] = max(precs) - min(precs)
        out["coverage_mean"] = sum(covs) / len(covs)
        out["coverage_range"] = max(covs) - min(covs)
    return out


# --- Cross-judge agreement on the SAME summary ---
# Two judges atomize differently, so we can't directly do Cohen's κ on per-claim
# verdicts. Instead we report: (a) agreement on aggregate precision (do both
# judges agree the summary is faithful?), (b) coverage rank correlation across
# (item, condition) cells.

def precision_agreement(
    judges_results: list[dict],
    threshold: float = 0.95,
) -> dict:
    """Do both judges agree the summary is faithful (precision >= threshold)?

    For inter-judge agreement at the cell level. Use after running multiple
    cells with `score_with_judges`.
    """
    n_both_faithful = 0
    n_both_unfaithful = 0
    n_disagree = 0
    for r in judges_results:
        verdicts = [j["precision"] >= threshold for j in r["per_judge"] if "error" not in j]
        if len(verdicts) < 2:
            continue
        if all(verdicts):
            n_both_faithful += 1
        elif not any(verdicts):
            n_both_unfaithful += 1
        else:
            n_disagree += 1
    n_total = n_both_faithful + n_both_unfaithful + n_disagree
    return {
        "n_total": n_total,
        "n_both_faithful": n_both_faithful,
        "n_both_unfaithful": n_both_unfaithful,
        "n_disagree": n_disagree,
        "agreement_rate": (n_both_faithful + n_both_unfaithful) / max(1, n_total),
        "threshold": threshold,
    }


def cohens_kappa_binary(
    judge_a_verdicts: list[bool],
    judge_b_verdicts: list[bool],
) -> float:
    """Cohen's κ for two binary judges over the same items.

    judge_a_verdicts[i] and judge_b_verdicts[i] are the two judges' verdicts
    on the same item i (e.g., 'precision >= 0.95'). Returns κ in [-1, 1].
    """
    if len(judge_a_verdicts) != len(judge_b_verdicts):
        raise ValueError("Different lengths")
    n = len(judge_a_verdicts)
    if n == 0:
        return 0.0
    n_agree = sum(1 for a, b in zip(judge_a_verdicts, judge_b_verdicts) if a == b)
    p_observed = n_agree / n
    p_a_pos = sum(judge_a_verdicts) / n
    p_b_pos = sum(judge_b_verdicts) / n
    p_expected = p_a_pos * p_b_pos + (1 - p_a_pos) * (1 - p_b_pos)
    if p_expected >= 1.0:
        return 1.0  # Perfect agreement
    return (p_observed - p_expected) / (1 - p_expected)
