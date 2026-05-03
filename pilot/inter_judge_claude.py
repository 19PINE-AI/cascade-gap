"""Inter-judge replication: re-score existing Phase-3 cells with Claude Opus 4.7
as a second judge, using the same hallucination + probe-coverage prompts as
GPT-5.4.

Output:
  - judge_halluc_{label}_claude.json
  - judge_probes_{label}_claude.json
  - inter_judge_agreement.json (in run-dir)

For each cell, we report:
  - GPT-5.4 vs Claude hallucination counts per condition.
  - Direction agreement: does each judge agree that C1 < C0 on hallucinations
    and C1 > C0 on coverage?
  - Per-probe agreement: % of probes where both judges agree COVERED/MISSING.

Usage:
  python3 pilot/inter_judge_claude.py --run-dir <run_dir> [<run_dir> ...]
  python3 pilot/inter_judge_claude.py --all  # discover from runs/*/judge_halluc_*.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from anthropic import Anthropic

from pilot_audio_review import (
    HALLUCINATION_PROMPT,
    PROBE_CHECK_PROMPT,
    parse_json,
)

REPO = pathlib.Path(__file__).resolve().parent.parent
CLAUDE_MODEL = "claude-opus-4-7"


def call_claude_judge(prompt: str, max_tokens: int = 16_384) -> tuple[str, int]:
    client = Anthropic()
    t0 = time.time()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    )
    ms = int((time.time() - t0) * 1000)
    text_parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return ("\n".join(text_parts)).strip(), ms


def judge_halluc(review: str, reference: str, out_path: pathlib.Path, label: str) -> dict:
    if out_path.exists():
        return json.loads(out_path.read_text())
    prompt = (
        HALLUCINATION_PROMPT
        .replace("{transcript}", reference[:120_000])
        .replace("{review}", review)
    )
    text, ms = call_claude_judge(prompt)
    data = parse_json(text)
    unsupported = data.get("unsupported_claims", [])
    out = {
        "label": label,
        "judge": "claude-opus-4-7",
        "n_unsupported": len(unsupported),
        "unsupported_claims": unsupported,
        "elapsed_ms": ms,
    }
    out_path.write_text(json.dumps(out, indent=2))
    return out


def judge_probes(review: str, probes: list[dict], out_path: pathlib.Path, label: str) -> dict:
    if out_path.exists():
        return json.loads(out_path.read_text())
    prompt = (
        PROBE_CHECK_PROMPT
        .replace("{probes_json}", json.dumps(probes, indent=2))
        .replace("{review}", review)
    )
    text, ms = call_claude_judge(prompt)
    data = parse_json(text)
    results = data.get("results", [])
    n_covered = sum(1 for r in results if r.get("status") == "COVERED")
    out = {
        "label": label,
        "judge": "claude-opus-4-7",
        "n_probes": len(results),
        "n_covered": n_covered,
        "coverage": n_covered / max(1, len(results)),
        "results": results,
        "elapsed_ms": ms,
    }
    out_path.write_text(json.dumps(out, indent=2))
    return out


def discover_conditions(run_dir: pathlib.Path) -> list[str]:
    """Find every condition that has both a review_*.txt and an existing
    judge_halluc_*.json (GPT-5.4 baseline). Includes vendor variants like
    C0_claude, C1_claude as separate conditions."""
    conds: list[str] = []
    for hp in sorted(run_dir.glob("judge_halluc_*.json")):
        label = hp.stem.replace("judge_halluc_", "")
        review_file = run_dir / f"review_{label}.txt"
        if not review_file.exists():
            continue
        conds.append(label)
    return conds


def reread_gpt5(run_dir: pathlib.Path, label: str) -> tuple[int, int, list[dict]]:
    halluc = json.loads((run_dir / f"judge_halluc_{label}.json").read_text())
    probes_judged = json.loads((run_dir / f"judge_probes_{label}.json").read_text())
    return (
        halluc.get("n_unsupported", -1),
        probes_judged.get("n_covered", -1),
        probes_judged.get("results", []),
    )


def re_judge_run(run_dir: pathlib.Path) -> dict:
    print(f"\n=== {run_dir.name} ===", flush=True)
    ref_path = run_dir / "reference_transcript.txt"
    probes_path = run_dir / "probes.json"
    if not ref_path.exists() or not probes_path.exists():
        print(f"  skipping: missing reference or probes", flush=True)
        return {}
    reference = ref_path.read_text()
    probes = json.loads(probes_path.read_text()).get("probes", [])
    if not probes:
        print(f"  skipping: empty probes", flush=True)
        return {}

    conditions = discover_conditions(run_dir)
    print(f"  conditions: {conditions}", flush=True)
    cell: dict = {"run_dir": str(run_dir), "n_probes": len(probes), "conditions": {}}

    for label in conditions:
        review = (run_dir / f"review_{label}.txt").read_text()
        print(f"  [{label}] hallucination check via Claude...", flush=True)
        h_out = judge_halluc(review, reference, run_dir / f"claude_halluc_{label}.json", label)
        print(f"    Claude unsupported = {h_out['n_unsupported']}", flush=True)

        print(f"  [{label}] probe coverage via Claude ({len(probes)} probes)...", flush=True)
        p_out = judge_probes(review, probes, run_dir / f"claude_probes_{label}.json", label)
        print(f"    Claude covered = {p_out['n_covered']}/{p_out['n_probes']} = {p_out['coverage']:.3f}", flush=True)

        gpt_unsupp, gpt_covered, gpt_probe_results = reread_gpt5(run_dir, label)
        # Per-probe binary agreement
        cl_results = {r["id"]: r["status"] for r in p_out["results"] if "id" in r}
        gp_results = {r["id"]: r["status"] for r in gpt_probe_results if "id" in r}
        common_ids = set(cl_results) & set(gp_results)
        if common_ids:
            agree = sum(1 for pid in common_ids if cl_results[pid] == gp_results[pid])
            agree_pct = agree / len(common_ids)
        else:
            agree_pct = float("nan")

        cell["conditions"][label] = {
            "gpt5_unsupported": gpt_unsupp,
            "claude_unsupported": h_out["n_unsupported"],
            "gpt5_covered": gpt_covered,
            "claude_covered": p_out["n_covered"],
            "n_probes_compared": len(common_ids),
            "per_probe_agreement_pct": agree_pct,
        }
        print(
            f"    GPT-5.4 vs Claude:  halluc {gpt_unsupp} vs {h_out['n_unsupported']}  "
            f"  cov {gpt_covered} vs {p_out['n_covered']}  "
            f"  per-probe agree={agree_pct:.3f}",
            flush=True,
        )

    # Direction agreement: for each (C0, C1) vendor pair, do both judges agree on cascade direction?
    pairs: list[tuple[str, str, str]] = [("C0", "C1", "gemini")]
    if "C0_claude" in cell["conditions"] and "C1_claude" in cell["conditions"]:
        pairs.append(("C0_claude", "C1_claude", "claude"))

    cell["direction_agreement"] = []
    for c0_label, c1_label, vendor in pairs:
        if c0_label not in cell["conditions"] or c1_label not in cell["conditions"]:
            continue
        c0 = cell["conditions"][c0_label]
        c1 = cell["conditions"][c1_label]
        def hall_dir(c0_n, c1_n):
            return "C1<C0" if c1_n < c0_n else ("tie" if c1_n == c0_n else "C1>C0")
        def cov_dir(c0_n, c1_n):
            return "C1>C0" if c1_n > c0_n else ("tie" if c1_n == c0_n else "C1<C0")

        gpt_hall = hall_dir(c0["gpt5_unsupported"], c1["gpt5_unsupported"])
        cl_hall = hall_dir(c0["claude_unsupported"], c1["claude_unsupported"])
        gpt_cov = cov_dir(c0["gpt5_covered"], c1["gpt5_covered"])
        cl_cov = cov_dir(c0["claude_covered"], c1["claude_covered"])
        rec = {
            "vendor": vendor,
            "pair": f"{c0_label}_vs_{c1_label}",
            "halluc_gpt5": gpt_hall,
            "halluc_claude": cl_hall,
            "halluc_agree": gpt_hall == cl_hall,
            "cov_gpt5": gpt_cov,
            "cov_claude": cl_cov,
            "cov_agree": gpt_cov == cl_cov,
        }
        cell["direction_agreement"].append(rec)
        print(
            f"  direction[{vendor}]:  halluc {gpt_hall} vs {cl_hall} "
            f"({'AGREE' if rec['halluc_agree'] else 'DISAGREE'});  "
            f"cov {gpt_cov} vs {cl_cov} "
            f"({'AGREE' if rec['cov_agree'] else 'DISAGREE'})",
            flush=True,
        )

    (run_dir / "inter_judge_agreement.json").write_text(json.dumps(cell, indent=2))
    return cell


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, action="append", default=[])
    ap.add_argument("--all", action="store_true",
                    help="Discover all runs/* dirs that have judge_halluc_C0.json")
    ap.add_argument("--out", type=pathlib.Path, default=REPO / "research_log" / "inter_judge_summary.json")
    args = ap.parse_args()

    run_dirs: list[pathlib.Path] = list(args.run_dir)
    if args.all:
        for rd in sorted((REPO / "runs").iterdir()):
            if rd.is_dir() and (rd / "judge_halluc_C0.json").exists():
                run_dirs.append(rd)

    if not run_dirs:
        raise SystemExit("no run-dirs given (use --run-dir or --all)")

    print(f"[inter-judge] {len(run_dirs)} run-dir(s)", flush=True)
    summary = {"runs": []}
    for rd in run_dirs:
        try:
            cell = re_judge_run(rd)
            if cell:
                summary["runs"].append(cell)
        except Exception as e:
            print(f"  ERROR on {rd}: {type(e).__name__}: {e}", flush=True)

    args.out.write_text(json.dumps(summary, indent=2))
    print(f"\n[saved] {args.out}", flush=True)


if __name__ == "__main__":
    main()
