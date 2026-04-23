"""Re-run LLM-judge on already-generated summaries.

Reads runs/<tag>/summary_<item>_<cond>.txt files, fetches the reference
from pilot_sample.jsonl, scores each, writes judge_<item>.json and
summary.json in place.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
from dataclasses import asdict

from llm_judge import score_coverage, score_faithfulness


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--sample", type=pathlib.Path, required=True,
                    help="Path to pilot_sample.jsonl with reference_path per item")
    args = ap.parse_args()

    items_by_id = {}
    for line in args.sample.open():
        d = json.loads(line)
        items_by_id[d["item_id"]] = d

    # Find summary files
    summaries = sorted(args.run_dir.glob("summary_*_C*.txt"))
    # Group by item_id: summary_<item_id>_<COND>.txt
    by_item: dict[str, dict[str, pathlib.Path]] = {}
    for p in summaries:
        # "summary_" + <item_id> + "_" + cond + ".txt"
        stem = p.stem[len("summary_"):]
        item_id, cond = stem.rsplit("_", 1)
        by_item.setdefault(item_id, {})[cond] = p

    print(f"Re-judging {len(by_item)} items in {args.run_dir}")

    per_item: list[dict] = []
    for item_id, cond_paths in by_item.items():
        if item_id not in items_by_id:
            print(f"  SKIP {item_id}: not in sample")
            continue
        item = items_by_id[item_id]
        ref = pathlib.Path(item["reference_path"]).read_text()

        scores_by_cond = {}
        for cond in ["C0", "C1", "C2"]:
            if cond not in cond_paths:
                print(f"  {item_id}/{cond}: missing summary")
                continue
            summary_text = cond_paths[cond].read_text()
            print(f"  {item_id}/{cond}: judging... (summary {len(summary_text)} chars, ref {len(ref)} chars)", flush=True)
            try:
                faith = score_faithfulness(summary_text, ref)
                cov = score_coverage(summary_text, ref)
                print(f"    {cond}: {faith.n_supported}/{faith.n_claims} supported, "
                      f"{cov['n_covered']}/{cov['n_key_claims']} covered", flush=True)
                scores_by_cond[cond] = {
                    "faith": asdict(faith),
                    "cov": cov,
                }
            except Exception as e:
                import traceback
                print(f"    {cond}: FAILED {type(e).__name__}: {str(e)[:200]}", flush=True)
                traceback.print_exc()
                scores_by_cond[cond] = {"error": str(e)}

        # Save judge detail
        detail_path = args.run_dir / f"judge_{item_id}.json"
        detail_path.write_text(json.dumps(scores_by_cond, indent=2))

        row = {"item_id": item_id, "title": item.get("title", "?")}
        for cond in ["C0", "C1", "C2"]:
            if cond not in scores_by_cond or "error" in scores_by_cond[cond]:
                continue
            faith = scores_by_cond[cond]["faith"]
            cov = scores_by_cond[cond]["cov"]
            row[f"{cond}_n_claims"] = faith["n_claims"]
            row[f"{cond}_supported"] = faith["n_supported"]
            row[f"{cond}_unsupported"] = faith["n_unsupported"]
            row[f"{cond}_contradicted"] = faith["n_contradicted"]
            row[f"{cond}_precision"] = faith["supported_rate"]
            row[f"{cond}_coverage"] = cov["coverage_rate"]
            row[f"{cond}_n_key_claims"] = cov["n_key_claims"]
            row[f"{cond}_n_covered"] = cov["n_covered"]
        per_item.append(row)

    # Aggregate
    print("\n=== Aggregate ===")
    for cond in ["C0", "C1", "C2"]:
        precs = [r.get(f"{cond}_precision") for r in per_item if f"{cond}_precision" in r]
        covs = [r.get(f"{cond}_coverage") for r in per_item if f"{cond}_coverage" in r]
        hall = sum(r.get(f"{cond}_unsupported", 0) for r in per_item)
        contra = sum(r.get(f"{cond}_contradicted", 0) for r in per_item)
        if precs:
            print(f"  {cond}  precision={sum(precs)/len(precs):.3f}  "
                  f"coverage={sum(covs)/len(covs):.3f}  "
                  f"total_hallucinated={hall}  total_contradicted={contra}")

    summary_path = args.run_dir / "summary.json"
    if per_item:
        summary = {
            "run_dir": str(args.run_dir),
            "n": len(per_item),
            "by_condition": {
                cond: {
                    "precision": sum(r.get(f"{cond}_precision", 0) for r in per_item if f"{cond}_precision" in r) / max(1, sum(1 for r in per_item if f"{cond}_precision" in r)),
                    "coverage": sum(r.get(f"{cond}_coverage", 0) for r in per_item if f"{cond}_coverage" in r) / max(1, sum(1 for r in per_item if f"{cond}_coverage" in r)),
                    "total_hallucinated": sum(r.get(f"{cond}_unsupported", 0) for r in per_item),
                    "total_contradicted": sum(r.get(f"{cond}_contradicted", 0) for r in per_item),
                    "total_supported": sum(r.get(f"{cond}_supported", 0) for r in per_item),
                    "total_n_claims": sum(r.get(f"{cond}_n_claims", 0) for r in per_item),
                } for cond in ["C0", "C1", "C2"]
            },
            "per_item": per_item,
        }
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"\n[wrote] {summary_path}")


if __name__ == "__main__":
    main()
