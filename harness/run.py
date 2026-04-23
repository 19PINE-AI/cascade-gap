"""Phase-1 pilot runner.

Runs the matrix (tasks × models × conditions × seeds), saves per-item
results, aggregates per cell, reports the §6 decision gate.

Stub: CLI skeleton only. The pilot runner is wired to adapters but each
adapter is currently NotImplementedError — Phase-1 implementer fills in.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from .conditions import run_condition
from .metrics import cascade_gap, phase1_gate, summarize
from .models.anthropic import AnthropicAdapter
from .models.gemini import GeminiAdapter
from .models.hf import HFAdapter
from .models.openai import OpenAIAdapter

MODEL_FACTORY = {
    "claude_opus_4_7": lambda: AnthropicAdapter("claude-opus-4-7"),
    "gemini_3_1_pro": lambda: GeminiAdapter("gemini-3.1-pro-preview"),
    "gemini_3_1_flash_lite": lambda: GeminiAdapter("gemini-3.1-flash-lite-preview"),
    "gpt_4o_audio": lambda: OpenAIAdapter("gpt-4o-audio-preview"),
    "qwen3_omni_30b": lambda: HFAdapter("qwen3_omni_30b"),
    "step_audio_r1_1": lambda: HFAdapter("step_audio_r1_1"),
    "ui_tars_2_72b": lambda: HFAdapter("ui_tars_2_72b_dpo"),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", required=True, help="Comma-separated task names")
    p.add_argument("--models", required=True, help="Comma-separated model short names")
    p.add_argument("--conditions", default="C0,C1,C2")
    p.add_argument("--seeds", default="0,1,2")
    p.add_argument("--n-items", type=int, default=50)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    args = p.parse_args()

    tasks = args.tasks.split(",")
    models = args.models.split(",")
    conditions = args.conditions.split(",")
    seeds = [int(s) for s in args.seeds.split(",")]

    args.output.mkdir(parents=True, exist_ok=True)
    per_cell: dict[tuple[str, str, str], list] = defaultdict(list)

    for task_name in tasks:
        task = _load_task(task_name, args.data_dir)
        for model_name in models:
            if model_name not in MODEL_FACTORY:
                raise SystemExit(f"Unknown model: {model_name}")
            adapter = MODEL_FACTORY[model_name]()
            if not adapter.supports_modality(_modality_for_task(task)):
                print(f"[skip] {model_name} does not support {task.modality} for {task_name}")
                continue
            for seed in seeds:
                items = task.load(n_items=args.n_items, seed=seed)
                for item in items:
                    for cond in conditions:
                        r = run_condition(task, item, cond, perceive_model=adapter)
                        per_cell[(task_name, model_name, cond)].append(r)
                        _write_item_row(args.output, task_name, model_name, cond, seed, item.item_id, r)

    # Aggregate and report gate
    summaries = {
        k: summarize(k[0], k[1], k[2], v) for k, v in per_cell.items()
    }
    gaps: list[float] = []
    for task_name in tasks:
        for model_name in models:
            c0 = summaries.get((task_name, model_name, "C0"))
            c1 = summaries.get((task_name, model_name, "C1"))
            if c0 and c1:
                g = cascade_gap(c0, c1)
                gaps.append(g)
                print(f"[gap] {task_name}/{model_name}: Δ = {g:+.3f}  (C0={c0.score_mean:.3f}, C1={c1.score_mean:.3f})")

    passed = phase1_gate(gaps, threshold=0.03, min_tasks=2)
    print(f"\n[PHASE 1 GATE] {'PASS' if passed else 'FAIL'} — {sum(1 for g in gaps if abs(g) >= 0.03)} / {len(gaps)} cells cross ±3pt threshold")


def _modality_for_task(task):
    return {"audio": "audio", "document": "image", "gui": "image"}[task.modality]


def _load_task(name: str, data_dir: Path):
    if name.startswith("mmar_"):
        from .tasks.mmar import MMARTask
        layer = name.split("_", 1)[1]
        return MMARTask(data_dir=data_dir / "mmar", layer=layer)
    raise SystemExit(f"Unknown task: {name}")


def _write_item_row(out: Path, task, model, cond, seed, item_id, result):
    row = {
        "task": task,
        "model": model,
        "condition": cond,
        "seed": seed,
        "item_id": item_id,
        "score": result.score,
        "pass_1_tokens": result.pass_1_tokens,
        "pass_2_tokens": result.pass_2_tokens,
        "pass_1_latency_ms": result.pass_1_latency_ms,
        "pass_2_latency_ms": result.pass_2_latency_ms,
    }
    with (out / "items.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
