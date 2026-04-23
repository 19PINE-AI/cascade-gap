# Cascade Gap Evaluation Harness

Minimal scaffolding for Phase 1 pilot experiments. The design follows the three-condition protocol in §4.3 of the plan.

## Layout

```
harness/
├── models/           Model adapters (one per vendor)
│   ├── base.py       Abstract ModelAdapter (prompt → response, supports text + audio + image inputs)
│   ├── anthropic.py  Claude Opus 4.7 / Sonnet 4.6
│   ├── openai.py     GPT-4o-audio-preview, GPT-5.x
│   ├── gemini.py     Gemini 3.1 Pro / Flash
│   └── hf.py         HuggingFace open-weight (Qwen3-Omni, Step-Audio-R1.1, UI-TARS-2)
├── tasks/            Task loaders
│   ├── base.py       Abstract Task
│   └── mmar.py       Example: MMAR audio reasoning
├── schemas/          C2 augmented-cascade tag schemas (Pass-1 prompts)
│   ├── audio_uas.md
│   ├── document_layout.md
│   └── gui_affordance.md
├── conditions.py     C0 / C1 / C2 / C3 runners
├── metrics.py        Per-task scorers
├── cache.py          On-disk cache for API responses (mandatory for audio re-runs)
├── run.py            CLI entry
└── requirements.txt
```

## Usage (intended; not yet runnable — adapters are stubs)

```bash
# Phase 1 decision-gate pilot: 2 audio tasks × 3 models × 3 conditions × 3 seeds
python run.py \
  --tasks mmar_signal,mmar_perception \
  --models qwen3_omni,gemini_3_1_pro,gpt_4o_audio \
  --conditions C0,C1,C2 \
  --seeds 0,1,2 \
  --n-items 50 \
  --output runs/2026-04-24-pilot/
```

## Phase 1 decision gate (from plan §6)

"Do C0 and C1 differ by ≥3 points on at least 2 of 6 pilot tasks per modality?"

`run.py` prints a pass/fail verdict on the gate after the pilot completes.

## Caching

Every API call is cached by `(provider, model_version, prompt_hash, modality_input_hash, decoding_params_hash)`. This is **mandatory**: audio-preview APIs are rate-limited and expensive; a dropped run should not cost anything.

## Status (2026-04-23)

- [x] Directory structure
- [x] Tag schemas (C2)
- [x] Interface contracts (ModelAdapter, Task, Condition)
- [ ] Concrete adapter implementations
- [ ] Concrete task loaders
- [ ] Metrics
- [ ] End-to-end test on 1 task, 1 model, 1 condition
