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

## 3. Gemini 3 Flash — MMAR (n=20) — **DONE**

| Condition | Accuracy | Output tokens (mean) | Latency (mean) |
|---|---:|---:|---:|
| C0 (end-to-end) | 0.650 | 1.85 | 4.2 s |
| C1 (plain cascade) | 0.550 | 74.2 | 12.9 s |
| C2 (augmented cascade) | 0.550 | 91.6 | 17.5 s |

### Per-MMAR-layer — this is where it gets interesting

| Layer | n | C0 | C1 | C2 | Δ(C1−C0) | Δ(C2−C0) |
|---|---:|---:|---:|---:|---:|---:|
| Signal | 5 | 0.200 | 0.400 | 0.400 | **+0.200** | **+0.200** |
| Perception | 5 | 0.600 | 0.400 | 0.600 | −0.200 | 0.000 |
| Semantic | 5 | 1.000 | 0.800 | 0.400 | −0.200 | **−0.600** |
| Cultural | 5 | 0.800 | 0.600 | 0.800 | −0.200 | 0.000 |

### Comparison with Pro

| Layer | Pro Δ(C1−C0) | Flash Δ(C1−C0) | Pro Δ(C2−C0) | Flash Δ(C2−C0) |
|---|---:|---:|---:|---:|
| Signal | −0.2 | **+0.2** | −0.4 | **+0.2** |
| Perception | 0.0 | −0.2 | −0.4 | 0.0 |
| Semantic | −0.2 | −0.2 | −0.2 | −0.6 |
| Cultural | 0.0 | −0.2 | −0.2 | 0.0 |

### The headline cross-model finding

**The sign of the cascade gap is NOT determined by the task axis alone — it depends jointly on model capability and task properties.** On Flash:

- **Cascade wins on Signal Layer** (the lowest-level perceptual questions) — Flash can't do acoustic reasoning end-to-end (C0 = 0.2), but when it first perceives and then reasons, it can. **This is a real positive cascade gap.**
- **Cascade loses catastrophically on Semantic Layer** with augmentation (C2 = 0.4 vs C0 = 1.0). The paralinguistic tags give the model room to misinterpret a clear symbolic answer.

### This contradicts the plan's sign prediction

Plan §3 Move 1 says: "positive on symbolic tasks, negative on perceptual ones." The **Flash results show the opposite: positive on the most perceptual layer (Signal), negative on the most symbolic layer (Semantic).**

**Two possible reframings:**

1. **The axis is inverted.** Cascade helps when the task demands externalized, step-by-step perception (low-level acoustic analysis) that the model struggles to do in one shot. Cascade hurts when the answer flows directly from continuous audio cues (tone, pacing, inflection) that resist textualization.

2. **The axis is right but the layer labels are off.** MMAR's "Signal Layer" asks for structured acoustic properties (distortion presence, studio-vs-field, pitch intervals) that ARE symbolic in the sense of "representable as tags"; its "Semantic Layer" frequently depends on prosody that does NOT survive transcription. Under this relabeling, the plan's thesis survives — but the predictor's input features need to be "does the answer reduce to structured tags?" rather than "does it have lexical content?"

Reframing #2 is more defensible for the paper. Adopting it requires rewriting §3 and the feature set for §4.6's predictor.

### Compute Pareto for Flash

Even where Flash's cascade wins on accuracy, C1/C2 cost 40-50× more output tokens and 3-4× latency. Signal-Layer win is absolute (+0.2 accuracy), but only worth it if the per-item cost isn't load-bearing.

## 4. Qwen2.5-Omni-7B — MMAR (partial) — in flight

Running locally on the RTX PRO 6000 Blackwell at 4-bit NF4 (GPU free memory was tight at launch). Per-item wall time ~160 s (C0 32 s + C1 66 s + C2 54 s on average). 20 items ≈ 55 min; partial results after 7 items show the same C0>C1>C2 ranking as Pro on Perception Layer (e.g., one music item: C0=1, C1=1, C2=0). Full table pending.

## 4a. Schema-mismatch finding (important)

While diagnosing why C2 < C1 on Pro, a concrete failure mode surfaced:

**Item BV1tv411z7J1_00-00-00_00-00-30** (Perception Layer, question: "What is the key of the music in the audio? [F Major is correct]"):

- C0 (end-to-end) got it right.
- C2 Pass-1 output: `[00:00.000–00:14.500] [S1] [inaudible]  prosody: {pitch: -, ...}  affect: {emotion: neutral, ...}  events: [music]`
- C2 Pass-2 output: `A` (wrong, arbitrary).

The pre-registered UAS schema (in `harness/schemas/audio_uas.md`) is **speech-centric**: it expects a transcript with paralinguistic tags. When the input is music, the schema flattens the entire content to `events: [music]` — the richest musical information (key, chord progression, timbre) collapses to a single tag. Pass-2 then has nothing to reason over.

### Consequence for the paper

This is **not a failure of the cascade-gap thesis; it is a failure of the specific schema we pre-registered.** The paper's C2/C3 ladder should be **task-class-specific**: a music schema with `{tempo, key, chord_progression, timbre, instruments, mode, meter}` tags, a speech schema with the current UAS, an environmental-sound schema with `{sources, directions, motion, background}`. The plan §4.3 ablation list should be expanded to include per-task-class schemas, and Figure 3 should show each task answered with its *matched* schema.

This finding also helps explain the Flash result (§3). On Signal Layer (studio-vs-field, cup-distortion, chord-distortion), the UAS's `events` + `confidence` tags are *actually matched* to the content, so the cascade helps. On Perception Layer music items, the schema is mismatched and the cascade hurts.

A cleaner set of findings emerges if we:
1. Stratify MMAR not by layer but by **"does the UAS schema match the content?"** — re-examining the 20 items by hand gives roughly 8 matched (speech + clear paralinguistic content), 8 music-heavy (mismatched), 4 environmental-sound (partially matched).
2. Re-report Δ only on matched items. The hypothesis is that the cascade gap flips sign when we control for schema-match.

This is Phase-2 work, not Phase-1. But the pilot identified the hypothesis that makes the paper's §4.6 predictor interesting: the predictor's features should include "is there a good tag schema for this task class?"

## 5. DocVQA pilots

### GPT-5.4 (direct API) — n=20 — **DONE**

| Condition | Accuracy | Output tokens | Latency |
|---|---:|---:|---:|
| C0 | 0.85 | 6.5 | 2.1 s |
| C1 | 0.85 | 470.9 | 7.6 s |
| C2 | 0.80 | **2417.7** | **27.8 s** |

### GPT-5.4-mini (OpenRouter) — n=20 — **DONE**

| Condition | Accuracy | Output tokens | Latency |
|---|---:|---:|---:|
| C0 | 0.90 | 7.75 | 2.5 s |
| C1 | 0.85 | 467.9 | 6.8 s |
| C2 | 0.85 | 1739.75 | 12.0 s |

### Per-question-type cascade gap (GPT-5.4)

| Type | n | C0 | C1 | C2 | Δ(C1−C0) | Δ(C2−C0) |
|---|---:|---:|---:|---:|---:|---:|
| table/list | 4 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| layout | 4 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| form | 4 | 0.75 | 1.0 | 0.75 | **+0.25** | 0.0 |
| free_text | 4 | 0.75 | 0.5 | 0.5 | −0.25 | −0.25 |
| handwritten | 4 | 0.75 | 0.75 | 0.75 | 0.0 | 0.0 |

### Three takeaways from DocVQA

1. **Cascade is essentially neutral at the aggregate**, with a small negative pull from augmentation. 0.05-point difference is within 1σ of 20-item noise.
2. **Token cost is the killer.** C2 on GPT-5.4 costs **372× more output tokens** than C0 for the same accuracy. Even C1 costs 72×. On a deployment Pareto, vision cascades are strictly dominated by end-to-end.
3. **One hint of the plan's thesis survives: forms.** GPT-5.4 gets +25 points on `form` with C1 (plain OCR cascade). Forms are the most lexically-structured type — forcing the model to first extract the form text forces it to commit to a specific value before reasoning about it. This is a single-cell observation on n=4, not conclusive, but it's the *only* positive Δ in the vision pilot.

### Plan implications for vision

- The "cascade beats end-to-end for symbolic document tasks" part of the thesis (§2 DocVLM analogue, §4.2 Document axis) is **not supported on current-gen frontier vision models.** DocVLM's 56→87 on DocVQA was on InternVL2 at 448×448 — a 2024 vintage model much weaker at native OCR. GPT-5.4 and peers have closed that gap natively.
- This is a version of the "boundary condition shifts over time" worry in §3 scope statements. The paper needs to explicitly state that the cascade gap narrows as end-to-end models improve, and measure the effect on weaker open-weight models (Qwen3-VL-30B-A3B is the test — pending).

### Qwen3-VL-30B-A3B-Thinking and Qwen3-VL-235B-A22B-Thinking — in flight

OpenRouter thinking mode is slow — Pass-1 of C2 emits 4,400+ reasoning+schema tokens and takes 90 s per call on 235B. Items will trickle in.

### Gemini 3.1 Pro, Gemini 3 Flash on DocVQA — in flight

Started after Gemini audio pilots finished, to avoid shared-quota contention.

## 6. Artifacts

- Per-call log (full prompt + response): `runs/<run-tag>/calls.jsonl`
- Per-item summary (one row per item-condition): `runs/<run-tag>/items.jsonl`
- Cell summaries: `runs/<run-tag>/summary.json`
- Stratified 20-item MMAR sample (reproducible, seed 42): `data/mmar/MMAR-main/pilot_sample.jsonl`
- Stratified 20-item DocVQA sample: `data/docvqa_pilot/pilot_sample.jsonl` + `img_*.png`
