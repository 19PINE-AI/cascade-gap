"""Aggregate runs/<tag>/summary.json into a cross-model/cross-task table.

Usage:
  python3 pilot/aggregate.py                # all runs
  python3 pilot/aggregate.py --benchmark mmar
  python3 pilot/aggregate.py --emit markdown > cross.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parent.parent


def load_summaries():
    for path in sorted((REPO / "runs").glob("*/summary.json")):
        try:
            s = json.loads(path.read_text())
        except Exception:
            continue
        tag = path.parent.name
        if "by_category" in s:
            bench = "mmar"
            stratify = s["by_category"]
        elif "by_question_type" in s:
            # DocVQA or ChartQA
            bench = "chartqa" if tag.startswith("chartqa") else "docvqa"
            stratify = s["by_question_type"]
        else:
            # Non-standard runs (e.g. music-schema ablation with its own format)
            continue
        yield {
            "tag": tag,
            "bench": bench,
            "model": s.get("model", "?"),
            "provider": s.get("provider", "?"),
            "n": s.get("n", 0),
            "by_condition": s.get("by_condition", {}),
            "stratify": stratify,
        }


def aggregate_table(rows: list[dict], benchmark: str | None) -> str:
    out = []
    out.append("# Cross-model cascade-gap summary\n")
    by_bench: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if benchmark and r["bench"] != benchmark:
            continue
        by_bench[r["bench"]].append(r)

    for bench, rs in sorted(by_bench.items()):
        out.append(f"\n## Benchmark: {bench.upper()}\n")
        out.append("| Model | N | C0 | C1 | C2 | Δ(C1−C0) | Δ(C2−C0) | C0 tok | C2 tok | C0 lat | C2 lat |")
        out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in rs:
            bc = r["by_condition"]
            c0 = bc.get("C0", {})
            c1 = bc.get("C1", {})
            c2 = bc.get("C2", {})
            d1 = c1.get("acc", 0) - c0.get("acc", 0)
            d2 = c2.get("acc", 0) - c0.get("acc", 0)
            out.append(
                f"| {r['model'][:40]} | {r['n']} | {c0.get('acc', 0):.2f} | {c1.get('acc', 0):.2f} | "
                f"{c2.get('acc', 0):.2f} | {d1:+.2f} | {d2:+.2f} | "
                f"{c0.get('out_tok_mean', 0):.0f} | {c2.get('out_tok_mean', 0):.0f} | "
                f"{c0.get('lat_ms_mean', 0)/1000:.1f}s | {c2.get('lat_ms_mean', 0)/1000:.1f}s |"
            )

        # Per-stratum detail
        out.append(f"\n### Per-stratum deltas ({bench})\n")
        # Collect all strata seen
        all_strata = set()
        for r in rs:
            all_strata.update(r["stratify"].keys())
        strata = sorted(all_strata)
        header = "| Model | " + " | ".join(f"{s}\\nΔ(C1)\\nΔ(C2)" for s in strata) + " |"
        out.append(header)
        out.append("|---" + "|---" * len(strata) + "|")
        for r in rs:
            cells = []
            for s in strata:
                x = r["stratify"].get(s)
                if not x:
                    cells.append("—")
                    continue
                c0 = x.get("C0_acc", 0)
                c1 = x.get("C1_acc", 0)
                c2 = x.get("C2_acc", 0)
                cells.append(f"{c1-c0:+.2f} / {c2-c0:+.2f}")
            out.append(f"| {r['model'][:30]} | " + " | ".join(cells) + " |")

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", choices=["mmar", "docvqa", "chartqa"], default=None)
    ap.add_argument("--emit", choices=["markdown", "json"], default="markdown")
    args = ap.parse_args()

    rows = list(load_summaries())
    # drop the tiny smoke-test run (name "pilot-" with n<=5)
    rows = [r for r in rows if r["n"] >= 10]

    if args.emit == "json":
        print(json.dumps(rows, indent=2))
    else:
        print(aggregate_table(rows, args.benchmark))


if __name__ == "__main__":
    main()
