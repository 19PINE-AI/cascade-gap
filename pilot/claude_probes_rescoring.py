"""Probe-circularity check (paper item #2): re-extract atomic probes with
Claude Opus 4.7 (instead of GPT-5.4) and re-score the existing C0/C1 reviews
against the new probes with BOTH judges (GPT-5.4 and Claude).

For each target run-dir:
  1. Read reference_transcript.txt.
  2. Extract 30-50 atomic probes via Claude using the same prompt template
     as GPT-5.4 used originally.
  3. Re-score review_C0.txt and review_C1.txt against the new probes with
     (a) GPT-5.4 high-reasoning and (b) Claude.
  4. Compare per-cell coverage and Δ_cov to the original (Gemini-extracted)
     probe-set numbers.

Outputs:
  - probes_claude.json
  - judge_probes_C0_claudeprobes_gptjudge.json
  - judge_probes_C1_claudeprobes_gptjudge.json
  - claude_probes_C0_claudeprobes.json    (Claude judge)
  - claude_probes_C1_claudeprobes.json
  - probe_circularity_summary.json

Usage:
  python3 pilot/claude_probes_rescoring.py \
      --run-dir runs/audio-review-mit_6034_winston-1778857365 \
      --run-dir runs/paper-review-2605.09852-1778859219 \
      --run-dir runs/paper-review-2605.13991-1778859221
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from anthropic import Anthropic

from pilot_audio_review import (
    PROBE_CHECK_PROMPT,
    PROBE_EXTRACTION_PROMPT,
    call_gpt5_judge,
    parse_json,
)
from inter_judge_claude import call_claude_judge

CLAUDE_MODEL = "claude-opus-4-7"


def extract_probes_claude(reference: str, out_path: pathlib.Path) -> list[dict]:
    if out_path.exists():
        d = json.loads(out_path.read_text())
        probes = d.get("probes", [])
        print(f"  [probes_claude] reusing {len(probes)} probes from {out_path.name}", flush=True)
        return probes
    prompt = PROBE_EXTRACTION_PROMPT.replace("{transcript}", reference[:120_000])
    # Need larger max_tokens for Claude — probe extraction can be long
    print(f"  [probes_claude] extracting probes via Claude...", flush=True)
    text, ms = call_claude_judge(prompt, max_tokens=16_384)
    data = parse_json(text)
    probes = data.get("probes", [])
    out_path.write_text(json.dumps({
        "probes": probes,
        "extractor": "claude-opus-4-7",
        "elapsed_ms": ms,
    }, indent=2))
    print(f"  [probes_claude] {len(probes)} probes extracted ({ms/1000:.1f}s)", flush=True)
    return probes


def score_with_judge(
    review: str,
    probes: list[dict],
    judge_name: str,  # "gpt5" or "claude"
    out_path: pathlib.Path,
    label: str,
) -> tuple[int, int, float]:
    if out_path.exists():
        d = json.loads(out_path.read_text())
        n_cov = d.get("n_covered", 0)
        n_pr = d.get("n_probes", len(probes))
        cov = n_cov / max(1, n_pr)
        print(f"  [{label}/{judge_name}] reusing cov={cov:.3f}", flush=True)
        return n_cov, n_pr, cov

    prompt = PROBE_CHECK_PROMPT.replace("{probes_json}", json.dumps(probes, indent=2)).replace("{review}", review)
    if judge_name == "gpt5":
        text, ms = call_gpt5_judge(prompt)
    elif judge_name == "claude":
        text, ms = call_claude_judge(prompt, max_tokens=16_384)
    else:
        raise ValueError(f"unknown judge: {judge_name}")

    data = parse_json(text)
    results = data.get("results", [])
    n_cov = sum(1 for r in results if r.get("status") == "COVERED")
    n_pr = len(results)
    cov = n_cov / max(1, n_pr)
    out_path.write_text(json.dumps({
        "label": label,
        "judge": judge_name,
        "n_probes": n_pr,
        "n_covered": n_cov,
        "coverage": cov,
        "results": results,
        "elapsed_ms": ms,
    }, indent=2))
    print(f"  [{label}/{judge_name}] covered={n_cov}/{n_pr} cov={cov:.3f} ({ms/1000:.1f}s)", flush=True)
    return n_cov, n_pr, cov


def run_one(run_dir: pathlib.Path) -> dict:
    print(f"\n=== {run_dir.name} ===", flush=True)
    ref = (run_dir / "reference_transcript.txt").read_text()
    review_c0 = (run_dir / "review_C0.txt").read_text()
    review_c1 = (run_dir / "review_C1.txt").read_text()

    # Original probes (GPT-5.4-extracted)
    orig = json.loads((run_dir / "probes.json").read_text()).get("probes", [])
    print(f"  [original probes] {len(orig)} (GPT-5.4 extracted)", flush=True)

    # New: Claude-extracted probes
    claude_probes = extract_probes_claude(ref, run_dir / "probes_claude.json")
    if not claude_probes:
        print(f"  WARNING: Claude probe extraction returned empty", flush=True)
        return {"run_dir": str(run_dir), "error": "no claude probes"}

    # Re-score C0 and C1 with Claude probes, both judges
    c0_gpt = score_with_judge(review_c0, claude_probes, "gpt5",
                              run_dir / "judge_probes_C0_claudeprobes_gpt5.json", "C0")
    c1_gpt = score_with_judge(review_c1, claude_probes, "gpt5",
                              run_dir / "judge_probes_C1_claudeprobes_gpt5.json", "C1")
    c0_cl = score_with_judge(review_c0, claude_probes, "claude",
                             run_dir / "claude_probes_C0_claudeprobes.json", "C0")
    c1_cl = score_with_judge(review_c1, claude_probes, "claude",
                             run_dir / "claude_probes_C1_claudeprobes.json", "C1")

    # Original Gemini-probes coverage (from existing summary.json)
    orig_summary = json.loads((run_dir / "summary.json").read_text())
    orig_c0_cov = orig_summary["scores"]["C0"]["probe_coverage"]
    orig_c1_cov = orig_summary["scores"]["C1"]["probe_coverage"]
    orig_delta = orig_c1_cov - orig_c0_cov

    result = {
        "run_dir": str(run_dir),
        "n_probes_gemini_extracted": len(orig),
        "n_probes_claude_extracted": len(claude_probes),
        "original_gpt_C0_cov": orig_c0_cov,
        "original_gpt_C1_cov": orig_c1_cov,
        "original_gpt_delta_cov": orig_delta,
        "claudeprobes_gpt_C0_cov": c0_gpt[2],
        "claudeprobes_gpt_C1_cov": c1_gpt[2],
        "claudeprobes_gpt_delta_cov": c1_gpt[2] - c0_gpt[2],
        "claudeprobes_claude_C0_cov": c0_cl[2],
        "claudeprobes_claude_C1_cov": c1_cl[2],
        "claudeprobes_claude_delta_cov": c1_cl[2] - c0_cl[2],
    }

    sp = run_dir / "probe_circularity_summary.json"
    sp.write_text(json.dumps(result, indent=2))

    print(f"\n  === Probe-circularity result on {run_dir.name} ===")
    print(f"  Δcov (orig probes, GPT)         : {orig_delta:+.3f}")
    print(f"  Δcov (Claude probes, GPT judge) : {result['claudeprobes_gpt_delta_cov']:+.3f}")
    print(f"  Δcov (Claude probes, Claude jud): {result['claudeprobes_claude_delta_cov']:+.3f}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, action="append", required=True)
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("research_log/probe_circularity_summary.json"))
    args = ap.parse_args()

    all_results = []
    for rd in args.run_dir:
        try:
            r = run_one(rd)
            all_results.append(r)
        except Exception as e:
            print(f"  ERROR on {rd}: {type(e).__name__}: {e}", flush=True)
            all_results.append({"run_dir": str(rd), "error": f"{type(e).__name__}: {e}"})

    args.out.write_text(json.dumps({"runs": all_results}, indent=2))
    print(f"\n[saved] {args.out}", flush=True)


if __name__ == "__main__":
    main()
