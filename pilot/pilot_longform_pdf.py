"""Long-form PDF summarization pilot — probes the scenario where end-to-end
vision models hallucinate on dense multi-page documents.

Each item is a full academic paper (16-24 pages). Conditions:

  C0 — end-to-end: all page images + "summarize" prompt → summary.
  C1 — plain cascade: Pass-1 = "transcribe every page verbatim"; Pass-2 =
       "summarize the transcript".
  C2 — structured cascade: Pass-1 = "extract structured description" using
       the pre-registered document_layout schema; Pass-2 = "summarize the
       structured description."

Scoring via llm_judge.py:
  - Faithfulness (precision): claims in summary marked SUPPORTED / UNSUPPORTED
    / CONTRADICTED against the paper's ground-truth extracted text.
  - Coverage (recall): of 15-25 key claims the judge extracts from the
    reference, how many does the summary cover?

Targeted paper's thesis: on long dense documents, C0 should hallucinate
claims (low precision) and/or omit key points (low recall) — C1 and C2
should beat C0 on both. This is where the cascade wins by design.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import time
from dataclasses import asdict, dataclass
from typing import Sequence

from google import genai
from google.genai import types

from llm_judge import score_coverage, score_faithfulness

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = REPO / "data" / "longform_pdf" / "pilot_sample.jsonl"
LAYOUT_SCHEMA_PATH = REPO / "harness" / "schemas" / "document_layout.md"


SUMMARY_PROMPT = """\
Write a comprehensive summary of this paper. Cover:
- The paper's main thesis / central claim.
- Methodology / experimental protocol.
- Key quantitative results (with specific numbers where reported).
- Stated limitations or scope boundaries.

Length: 500-800 words. Use plain prose, no bullet lists. Be faithful to the
source — do not embellish, do not speculate beyond what is stated."""


C1_PASS1_PROMPT = """\
Produce a detailed text record of every substantive point this PDF makes,
page by page, in reading order. Preserve every named entity, number, date,
claim, formula, and figure/table reference. You may rephrase wording, but
every fact, statistic, equation, and cited work must appear in your record.
Include headings and section structure. Emit page markers like '=== page N ==='.
Do NOT summarize, analyze, or answer any downstream question — only produce
the complete content record."""


def c2_pass1_prompt() -> str:
    schema = LAYOUT_SCHEMA_PATH.read_text()
    match = re.search(r"## Pass-1 prompt\s*```\n(.*?)\n```", schema, re.S)
    if not match:
        raise RuntimeError("Could not extract Pass-1 prompt from document_layout.md")
    # Adapt for multi-page: ask to process all pages
    adapted = match.group(1) + "\n\nThis document has multiple pages. Emit blocks for ALL pages in reading order."
    return adapted


def pass2_summary_prompt(perception_text: str, rich: bool) -> str:
    header = (
        "Below is a structured description of a paper, produced by an earlier perception pass."
        if rich
        else "Below is a plain-text transcription of a paper."
    )
    return (
        f"{header} Use ONLY the information below to write a comprehensive summary.\n\n"
        f"<perception>\n{perception_text}\n</perception>\n\n"
        f"Task:\n{SUMMARY_PROMPT}"
    )


@dataclass
class CallLog:
    item_id: str
    model: str
    condition: str
    stage: str
    prompt_tokens: int
    output_tokens: int
    latency_ms: int
    output_text: str


def call_gemini(client, model, prompt, image_paths: Sequence[str] | None):
    parts = [prompt]
    if image_paths:
        for p in image_paths:
            parts.append(types.Part.from_bytes(
                data=pathlib.Path(p).read_bytes(),
                mime_type="image/png",
            ))
    t0 = time.time()
    resp = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.0, top_p=1.0, max_output_tokens=65_536,
        ),
    )
    ms = int((time.time() - t0) * 1000)
    u = resp.usage_metadata
    text = (resp.text or "").strip()
    if not text:
        # Diagnose: log finish_reason, candidates, safety
        cand = resp.candidates[0] if resp.candidates else None
        fr = getattr(cand, "finish_reason", "?") if cand else "?"
        print(f"      [warn] empty response; finish_reason={fr}; usage={u}", flush=True)
    return (
        text,
        getattr(u, "prompt_token_count", 0) or 0,
        getattr(u, "candidates_token_count", 0) or 0,
        ms,
    )


def run_one(client, model: str, item: dict, run_dir: pathlib.Path) -> dict:
    image_paths = item["image_paths"]
    ref_text = pathlib.Path(item["reference_path"]).read_text()

    logs: list[CallLog] = []

    # ---- C0: end-to-end summary ----
    print(f"    [C0] sending {len(image_paths)} page images...", flush=True)
    c0_text, c0_in, c0_out, c0_ms = call_gemini(
        client, model, SUMMARY_PROMPT + "\n\n(All attached pages are from a single paper.)", image_paths
    )
    logs.append(CallLog(item["item_id"], model, "C0", "e2e", c0_in, c0_out, c0_ms, c0_text))

    # ---- C1: transcribe → summarize ----
    print(f"    [C1.p1] transcribing...", flush=True)
    p1_text, p1_in, p1_out, p1_ms = call_gemini(client, model, C1_PASS1_PROMPT, image_paths)
    logs.append(CallLog(item["item_id"], model, "C1", "pass1", p1_in, p1_out, p1_ms, p1_text))
    print(f"    [C1.p2] summarizing transcript ({p1_out} tokens)...", flush=True)
    c1_text, c1_in, c1_out, c1_ms = call_gemini(
        client, model, pass2_summary_prompt(p1_text, rich=False), None
    )
    logs.append(CallLog(item["item_id"], model, "C1", "pass2", c1_in, c1_out, c1_ms, c1_text))

    # ---- C2: structured → summarize ----
    print(f"    [C2.p1] structured extraction...", flush=True)
    p2_text, p2_in, p2_out, p2_ms = call_gemini(client, model, c2_pass1_prompt(), image_paths)
    logs.append(CallLog(item["item_id"], model, "C2", "pass1", p2_in, p2_out, p2_ms, p2_text))
    print(f"    [C2.p2] summarizing structured ({p2_out} tokens)...", flush=True)
    c2_text, c2_in, c2_out, c2_ms = call_gemini(
        client, model, pass2_summary_prompt(p2_text, rich=True), None
    )
    logs.append(CallLog(item["item_id"], model, "C2", "pass2", c2_in, c2_out, c2_ms, c2_text))

    # Persist calls
    with (run_dir / "calls.jsonl").open("a") as f:
        for log in logs:
            f.write(json.dumps(asdict(log)) + "\n")

    # Save summaries separately for manual inspection
    for cond, text in [("C0", c0_text), ("C1", c1_text), ("C2", c2_text)]:
        (run_dir / f"summary_{item['item_id']}_{cond}.txt").write_text(text)

    # ---- LLM-judge scoring ----
    print(f"    [judge] scoring C0...", flush=True)
    c0_faith = score_faithfulness(c0_text, ref_text)
    c0_cov = score_coverage(c0_text, ref_text)
    print(f"      C0: {c0_faith.n_supported}/{c0_faith.n_claims} supported, "
          f"{c0_cov['n_covered']}/{c0_cov['n_key_claims']} covered")
    print(f"    [judge] scoring C1...", flush=True)
    c1_faith = score_faithfulness(c1_text, ref_text)
    c1_cov = score_coverage(c1_text, ref_text)
    print(f"      C1: {c1_faith.n_supported}/{c1_faith.n_claims} supported, "
          f"{c1_cov['n_covered']}/{c1_cov['n_key_claims']} covered")
    print(f"    [judge] scoring C2...", flush=True)
    c2_faith = score_faithfulness(c2_text, ref_text)
    c2_cov = score_coverage(c2_text, ref_text)
    print(f"      C2: {c2_faith.n_supported}/{c2_faith.n_claims} supported, "
          f"{c2_cov['n_covered']}/{c2_cov['n_key_claims']} covered")

    # Persist per-item detail
    detail_path = run_dir / f"judge_{item['item_id']}.json"
    detail_path.write_text(json.dumps({
        "C0_faith": asdict(c0_faith), "C0_cov": c0_cov,
        "C1_faith": asdict(c1_faith), "C1_cov": c1_cov,
        "C2_faith": asdict(c2_faith), "C2_cov": c2_cov,
    }, indent=2))

    return {
        "item_id": item["item_id"],
        "title": item["title"],
        "page_count": item["page_count"],
        **{f"{c}_n_claims": faith.n_claims for c, faith in [("C0", c0_faith), ("C1", c1_faith), ("C2", c2_faith)]},
        **{f"{c}_supported_rate": faith.supported_rate for c, faith in [("C0", c0_faith), ("C1", c1_faith), ("C2", c2_faith)]},
        **{f"{c}_unsupported": faith.n_unsupported for c, faith in [("C0", c0_faith), ("C1", c1_faith), ("C2", c2_faith)]},
        **{f"{c}_contradicted": faith.n_contradicted for c, faith in [("C0", c0_faith), ("C1", c1_faith), ("C2", c2_faith)]},
        **{f"{c}_coverage_rate": cov["coverage_rate"] for c, cov in [("C0", c0_cov), ("C1", c1_cov), ("C2", c2_cov)]},
        "C0_out_tokens": c0_out,
        "C1_pass1_tokens": p1_out, "C1_pass2_tokens": c1_out,
        "C2_pass1_tokens": p2_out, "C2_pass2_tokens": c2_out,
        "C0_ms": c0_ms,
        "C1_ms": p1_ms + c1_ms,
        "C2_ms": p2_ms + c2_ms,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.1-pro-preview")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--run-dir", type=pathlib.Path, default=None)
    args = ap.parse_args()

    run_dir = args.run_dir or REPO / "runs" / f"longform-pdf-{args.model}-{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run_dir] {run_dir}", flush=True)

    items = [json.loads(l) for l in SAMPLE.open()]
    if args.limit > 0:
        items = items[: args.limit]
    print(f"[items] {len(items)}", flush=True)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    results = []
    for i, item in enumerate(items):
        print(f"\n  [{i+1}/{len(items)}] {item['item_id']} ({item['page_count']} pages, {item['title']})", flush=True)
        t0 = time.time()
        try:
            r = run_one(client, args.model, item, run_dir)
        except Exception as e:
            print(f"    FAILED: {type(e).__name__}: {str(e)[:200]}", flush=True)
            r = {"item_id": item["item_id"], "error": str(e)}
        results.append(r)
        print(f"    ({int(time.time()-t0)}s total)", flush=True)
        with (run_dir / "items.jsonl").open("a") as f:
            f.write(json.dumps(r) + "\n")

    # Aggregate
    valid = [r for r in results if "error" not in r]
    print(f"\n=== Aggregate === N={len(valid)} errors={len(results)-len(valid)}", flush=True)
    for cond in ["C0", "C1", "C2"]:
        if not valid:
            continue
        supp = sum(r[f"{cond}_supported_rate"] for r in valid) / len(valid)
        unsup = sum(r[f"{cond}_unsupported"] for r in valid)
        cont = sum(r[f"{cond}_contradicted"] for r in valid)
        cov = sum(r[f"{cond}_coverage_rate"] for r in valid) / len(valid)
        lat = sum(r[f"{cond}_ms"] for r in valid) / len(valid) / 1000
        print(f"  {cond}  precision={supp:.3f}  hallucinated={unsup}  contradicted={cont}  coverage={cov:.3f}  lat={lat:.1f}s", flush=True)

    summary = {
        "model": args.model, "n": len(valid),
        "by_condition": {
            cond: {
                "precision": sum(r[f"{cond}_supported_rate"] for r in valid) / len(valid) if valid else 0,
                "total_hallucinated": sum(r[f"{cond}_unsupported"] for r in valid),
                "total_contradicted": sum(r[f"{cond}_contradicted"] for r in valid),
                "coverage": sum(r[f"{cond}_coverage_rate"] for r in valid) / len(valid) if valid else 0,
                "lat_s": sum(r[f"{cond}_ms"] for r in valid) / len(valid) / 1000 if valid else 0,
            } for cond in ["C0", "C1", "C2"]
        }
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[wrote] {run_dir}/summary.json", flush=True)


if __name__ == "__main__":
    main()
