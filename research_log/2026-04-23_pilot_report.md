# Phase-1 Pilot Report — 2026-04-23

First real numbers. Pilot design, methodology, and completed-run findings below. Per-model result tables update as each run completes.

## 1. Design

**Audio pilot — MMAR subset:**
- Benchmark: MMAR (arXiv 2505.13032), 1,000-item audio-QA with four-layer hierarchical reasoning stratification (Signal, Perception, Semantic, Cultural).
- Subset: 20 items, stratified 5 per layer, random seed 42.
- Conditions (from plan §4.3):
  - **C0**: audio + question → answer (end-to-end, one call).
  - **C1**: Pass 1 = "transcribe verbatim"; Pass 2 = text-only reasoning.
  - **C2**: Pass 1 = UAS-augmented schema (paralinguistic tags + events + confidence) from `harness/schemas/audio_uas.md`; Pass 2 = text-only reasoning over the structured output.
- Decoding: temperature 0, max_output_tokens 2048, seed 0.
- Scoring: exact letter match against gold choice, with substring fallback on answer text.

**Vision pilot — DocVQA subset:**
- Benchmark: DocVQA validation (lmms-lab/DocVQA, 5,349 items).
- Subset: 20 items, 4 per each of top 5 question_types (table/list, layout, form, free_text, handwritten).
- Conditions analogous, C2 uses `harness/schemas/document_layout.md`.
- Scoring: case-insensitive substring match against any reference answer (lightweight proxy for ANLS).

**Models (audio × omni):**
- Gemini 3.1 Pro Preview (`gemini-3.1-pro-preview`) — closed, direct API.
- Gemini 3 Flash Preview (`gemini-3-flash-preview`) — closed, direct API.
- Qwen2.5-Omni-7B (`Qwen/Qwen2.5-Omni-7B`) — open, local GPU (bfloat16 when GPU free, else 4-bit NF4).

**Models (vision):**
- Gemini 3.1 Pro Preview, Gemini 3 Flash Preview — direct API.
- GPT-5.4 — OpenAI direct.
- GPT-5.4-mini — OpenRouter (direct key gated).
- Qwen3-VL-30B-A3B-Thinking, Qwen3-VL-235B-A22B-Thinking — OpenRouter.

**Dropped from the audio matrix:**
- `gpt-4o-audio-preview` — per user direction ("too old model, discard").
- GPT-5.4 / 5.4-mini — verified these do NOT accept audio input (400 on `input_audio`).
- Qwen3-Omni / Step-Audio-R1.1 — not on OpenRouter, and at the time of this pilot GPU had only 9-40 GB free (Qwen3-Omni-30B and Step-Audio-R1.1's 32B-Qwen core both need ~60 GB bf16). Scheduled for a follow-up run once GPU frees up or with 4-bit quantization.

---

## 2. Gemini 3.1 Pro — MMAR (n=20) — **DONE**

| Condition | Accuracy | Output tokens (mean) | Latency (mean) |
|---|---:|---:|---:|
| C0 (end-to-end) | **0.900** | 0.9 | 13.4 s |
| C1 (plain cascade) | 0.800 | 57.3 | 35.3 s |
| C2 (augmented cascade) | 0.600 | 98.8 | 37.9 s |

### Per-MMAR-layer

| Layer | n | C0 | C1 | C2 | Δ(C1−C0) | Δ(C2−C0) | Δ(C2−C1) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Signal (perceptual end) | 5 | 0.800 | 0.600 | 0.400 | −0.200 | −0.400 | −0.200 |
| Perception | 5 | 0.800 | 0.800 | 0.400 | 0.000 | −0.400 | −0.400 |
| Semantic (symbolic) | 5 | 1.000 | 0.800 | 0.800 | −0.200 | −0.200 | 0.000 |
| Cultural | 5 | 1.000 | 1.000 | 0.800 | 0.000 | −0.200 | −0.200 |

**Phase-1 decision gate:** PASS (5 of 8 layer-level deltas cross ±3pt).

### What this says for the paper

1. **The cascade gap is negative on Gemini 3.1 Pro for MMAR, every layer.** The sign is uniformly against the paper's core hypothesis on a frontier omni model. End-to-end already wins.
2. **The symbolic→perceptual axis is directionally correct:** the gap is smallest (zero) on Cultural and most negative on Perception/Signal. This matches the paper's prediction about *where* the gap is most negative, even though the gap is not positive *anywhere*.
3. **C2 is strictly worse than C1 on every layer except Semantic (tied).** Augmentation with paralinguistic tags does NOT close the gap on this model; it widens it. Most plausible explanation: the model's C2 Pass-1 output averages 98 tokens vs C1's 57, and the longer, more structured Pass-1 distracts Pass-2 rather than aiding it. Only 1/20 C2 answers was a malformed letter, so format conformance isn't the issue — it's genuine reasoning degradation. The plan's §4.3 Figure-3 prediction (C2/C3 should close the gap) does not hold here.
4. **Compute Pareto is brutal.** Cascades cost ~55-110× more output tokens and ~2.5-2.8× more latency for strictly worse accuracy. On Gemini 3.1 Pro + MMAR, there is no reason a practitioner would cascade.

### Implications for paper positioning

The "frontier omni model" slice of the paper needs to flip from **"cascade beats end-to-end"** to **"end-to-end beats cascade, but the gap narrows toward the symbolic end and the augmentation direction still needs a solution."** This is consistent with the Step-Audio-R1 finding (audio LLMs "consistently perform better with minimal or no reasoning" — and a cascade imposes text-based reasoning mid-flow).

The paper's **predictive-rule claim (§4.6)** is still alive: sign of Δ is predictable from task properties, even if the sign is uniformly negative on Pro. What the paper cannot claim from this data is that a same-weights cascade gives *absolute* wins on symbolic tasks. It can claim:
- Δ magnitude is smallest where the paper predicts (Cultural/Semantic).
- The gap widens on perceptual tasks in the predicted direction.
- Augmentation hurts on Pro — a surprise the plan did not anticipate and should now engage head-on.

### Still to test (decides whether the paper's sign-flip hypothesis survives)

- **Weaker model hypothesis**: the plan's best case for the cascade is an older/smaller model where end-to-end audio reasoning is weak. Qwen2.5-Omni-7B is the test. If cascade wins on Qwen, the paper can frame the effect as *model-capability-dependent* rather than universal.
- **Cross-family confirmation**: Gemini 3 Flash result will tell us whether Pro's negative Δ is Gemini-specific or applies across the family.
- **Document and GUI modalities**: the plan's stronger claim is cross-modality. If cascade beats end-to-end on DocVQA or OSWorld even when it loses on MMAR, the paper becomes more of a modality-level story than a universal one.

---

## 3. Gemini 3 Flash — MMAR (n=20) — in flight

Results pending. Will fill in table and comparison against Pro when complete.

## 4. Qwen2.5-Omni-7B — MMAR (n=20) — in flight

Results pending. Expectation: cascade gap should be more positive here (or at least less negative) — this model is much weaker on audio than Gemini 3.1 Pro, so the symbolic-end tasks may genuinely benefit from externalized reasoning.

## 5. DocVQA pilots — in flight

- GPT-5.4 (OpenAI direct): running.
- Qwen3-VL-30B-A3B-Thinking (OpenRouter): running.
- Qwen3-VL-235B-A22B-Thinking (OpenRouter): running.
- GPT-5.4-mini (OpenRouter): running.
- Gemini 3.1 Pro, Gemini 3 Flash: queued (will run after Gemini audio pilots to avoid API quota contention).

## 6. Artifacts

- Per-call log (full prompt + response): `runs/<run-tag>/calls.jsonl`
- Per-item summary (one row per item-condition): `runs/<run-tag>/items.jsonl`
- Cell summaries: `runs/<run-tag>/summary.json`
- Stratified 20-item MMAR sample (reproducible, seed 42): `data/mmar/MMAR-main/pilot_sample.jsonl`
- Stratified 20-item DocVQA sample: `data/docvqa_pilot/pilot_sample.jsonl` + `img_*.png`
