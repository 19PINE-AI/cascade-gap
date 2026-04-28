"""Re-score existing long-form summaries with multiple judges and report
inter-judge agreement.

Phase-2 M1 deliverable: cross-judge validation. Reads runs/<tag>/summary_*_C*.txt
files, looks up the reference, and runs each summary through 2+ judges.
Saves results to runs/<tag>/judge_multi_<item>.json and updates summary.json.

Usage:
    python3 pilot/rejudge_multi.py \
        --run-dir runs/longform-pdf-... \
        --sample data/longform_pdf/pilot_sample.jsonl \
        --judges gemini:gemini-3.1-pro-preview openai:gpt-5.4
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from dataclasses import asdict

# Ensure we can import sibling modules when run from repo root.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from llm_judge_multi import score_one_judge, score_with_judges, cohens_kappa_binary


def parse_judge_arg(s: str) -> tuple[str, str]:
    """Parse 'provider:model' into (provider, model)."""
    if ":" not in s:
        raise ValueError(f"Judge spec must be provider:model, got {s!r}")
    p, m = s.split(":", 1)
    return p, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--sample", type=pathlib.Path, required=True)
    ap.add_argument(
        "--judges",
        nargs="+",
        default=["gemini:gemini-3.1-pro-preview", "openai:gpt-5.4"],
        help="One or more judge specs, e.g. 'gemini:gemini-3.1-pro-preview' 'openai:gpt-5.4'",
    )
    ap.add_argument("--limit-items", type=int, default=0, help="Limit to N items (0=all)")
    args = ap.parse_args()

    judges = [parse_judge_arg(j) for j in args.judges]
    print(f"[judges] {judges}", flush=True)

    items_by_id = {}
    for line in args.sample.open():
        d = json.loads(line)
        items_by_id[d["item_id"]] = d

    # Discover summary files: summary_<item_id>_<COND>.txt
    by_item: dict[str, dict[str, pathlib.Path]] = {}
    for p in sorted(args.run_dir.glob("summary_*_C*.txt")):
        stem = p.stem[len("summary_"):]
        item_id, cond = stem.rsplit("_", 1)
        by_item.setdefault(item_id, {})[cond] = p

    item_ids = sorted(by_item.keys())
    if args.limit_items > 0:
        item_ids = item_ids[: args.limit_items]
    print(f"[items] {len(item_ids)} in {args.run_dir}", flush=True)

    all_results = []
    for item_id in item_ids:
        if item_id not in items_by_id:
            print(f"  SKIP {item_id}: not in sample", flush=True)
            continue
        item = items_by_id[item_id]
        ref = pathlib.Path(item["reference_path"]).read_text()
        for cond in ["C0", "C1", "C2"]:
            if cond not in by_item[item_id]:
                continue
            summary_text = by_item[item_id][cond].read_text()
            # Skip empty / refusal-only summaries
            if len(summary_text) < 100:
                print(f"  SKIP {item_id}/{cond}: summary too short ({len(summary_text)} chars)", flush=True)
                continue
            print(f"  [{item_id}/{cond}] judging with {len(judges)} judges...", flush=True)
            t0 = time.time()
            try:
                r = score_with_judges(summary_text, ref, judges)
            except Exception as e:
                print(f"    FAILED {type(e).__name__}: {str(e)[:200]}", flush=True)
                r = {"error": str(e), "per_judge": []}
            r["item_id"] = item_id
            r["condition"] = cond
            all_results.append(r)
            ms = int((time.time() - t0) * 1000)
            for j in r.get("per_judge", []):
                if "error" in j:
                    print(f"    judge {j['judge_provider']}/{j['judge_model']}: ERROR {j['error'][:120]}", flush=True)
                else:
                    print(
                        f"    judge {j['judge_provider']}/{j['judge_model']}: "
                        f"prec={j['precision']:.3f} cov={j['coverage']:.3f} "
                        f"({j['n_supported']}/{j['n_claims']} supp, {j['coverage_n_covered']}/{j['coverage_n_total']} cov)",
                        flush=True,
                    )
            if "precision_mean" in r:
                print(f"    inter-judge: prec_range={r['precision_range']:.3f} cov_range={r['coverage_range']:.3f}", flush=True)
            print(f"    ({ms/1000:.1f}s)", flush=True)

    # Save full per-cell results
    out = args.run_dir / "judge_multi.jsonl"
    with out.open("w") as f:
        for r in all_results:
            f.write(json.dumps(r) + "\n")
    print(f"\n[wrote] {out}", flush=True)

    # Compute Cohen's κ on the binary "is faithful" verdict (precision >= 0.95)
    if len(judges) >= 2:
        provider_a, model_a = judges[0]
        provider_b, model_b = judges[1]
        a_verdicts, b_verdicts = [], []
        for r in all_results:
            if "error" in r:
                continue
            judge_data = {(j["judge_provider"], j["judge_model"]): j for j in r["per_judge"] if "error" not in j}
            ja = judge_data.get((provider_a, model_a))
            jb = judge_data.get((provider_b, model_b))
            if ja is None or jb is None:
                continue
            a_verdicts.append(ja["precision"] >= 0.95)
            b_verdicts.append(jb["precision"] >= 0.95)
        if a_verdicts:
            kappa = cohens_kappa_binary(a_verdicts, b_verdicts)
            print(f"\n=== Inter-judge Cohen's κ (faithful @ prec>=0.95) ===", flush=True)
            print(f"  judge A: {provider_a}/{model_a}", flush=True)
            print(f"  judge B: {provider_b}/{model_b}", flush=True)
            print(f"  n cells: {len(a_verdicts)}", flush=True)
            print(f"  κ = {kappa:.3f}", flush=True)
            agree_summary_path = args.run_dir / "kappa.json"
            agree_summary_path.write_text(json.dumps({
                "judge_a": f"{provider_a}/{model_a}",
                "judge_b": f"{provider_b}/{model_b}",
                "n": len(a_verdicts),
                "kappa": kappa,
                "threshold": 0.95,
            }, indent=2))
            print(f"[wrote] {agree_summary_path}", flush=True)


if __name__ == "__main__":
    main()
