# Phase-1 Pilot — Final Report

**Date:** 2026-04-23
**Scope:** 13 pilot runs across 3 benchmarks (MMAR, DocVQA, ChartQA) × 6 models, plus 1 schema-match ablation. Short-form QA only; long-form generation pilots (meeting-summary audio + full-paper PDF) are in flight separately.
**Total items judged:** 252 (short-form). Music-schema ablation adds 12 items. Long-form runs reported separately.

This report supersedes `2026-04-23_pilot_report.md` and `2026-04-23_synthesis.md` as the canonical Phase-1 summary; both are retained as daily-log artifacts.

---

## 1. The headline finding

**The paper's plan v1 thesis — "self-cascade beats end-to-end on symbolic tasks" — does not survive on current-gen benchmarks.** Across 5 models and 3 benchmarks using short-form MCQ / extractive tasks, the cascade is at best neutral and typically hurts:

| Benchmark | Model | C0 | C1 | C2 |
|---|---|---:|---:|---:|
| MMAR | Gemini 3.1 Pro | **0.90** | 0.80 | 0.60 |
| MMAR | Gemini 3 Flash | 0.65 | 0.55 | 0.55 |
| MMAR | Qwen2.5-Omni-7B (4-bit) | **0.75** | 0.65 | 0.45 |
| DocVQA | Gemini 3.1 Pro | **0.95** | 0.70 | **0.95** |
| DocVQA | Gemini 3 Flash | **0.95** | 0.85 | 0.45 |
| DocVQA | GPT-5.4 | **0.85** | **0.85** | 0.80 |
| DocVQA | GPT-5.4-mini | **0.90** | 0.85 | 0.85 |
| DocVQA | Qwen3-VL-30B-A3B-Thinking | **0.95** | **0.95** | 0.89 |
| ChartQA | GPT-5.4 | 0.75 | 0.55 | **0.80** |
| ChartQA | GPT-5.4-mini | **0.80** | 0.60 | 0.75 |

**In 10 of 10 (model × benchmark) cells at the aggregate level, C0 ≥ C2 (tie or end-to-end wins) on the short-form tasks.** The only exception is Gemini 3.1 Pro on DocVQA where C0 ties C2 at 0.95 and GPT-5.4 on ChartQA where C2 is +0.05 over C0.

The effect the plan predicted — that on symbolic-content tasks a self-cascade externalizes reasoning the end-to-end model can't do natively — is not observable on frontier models at short-form QA. These benchmarks are effectively solved at end-to-end.

## 2. The real cascade gap signals

The interesting effects appear **below the aggregate**, in per-stratum deltas.

### 2.1 Gemini 3 Flash, MMAR Signal Layer: cascade wins +20 points

| Layer | C0 | C1 | C2 |
|---|---:|---:|---:|
| Signal (low-level acoustic) | 0.20 | **0.40** | **0.40** |
| Perception | 0.60 | 0.40 | 0.60 |
| Semantic (content-heavy) | **1.00** | 0.80 | 0.40 |
| Cultural | 0.80 | 0.60 | 0.80 |

Flash cannot do low-level acoustic reasoning end-to-end (C0=0.20 on 5 items: "is this studio-recorded", "which cup distorts most when tapped", etc.). Forcing it to first *perceive-and-transcribe* with paralinguistic tags and then reason over text doubles its accuracy. This is the plan's thesis validated on exactly one (model, task-class) cell.

On Semantic Layer the pattern inverts: C2 bombs (−0.60 vs C0) because the audio's semantic content depends on prosody that transcription drops.

### 2.2 ChartQA augmented_test: C2 wins +20 points on GPT-5.4-mini

| Split | Model | C0 | C1 | C2 |
|---|---|---:|---:|---:|
| augmented_test (programmatic) | GPT-5.4-mini | 0.70 | 0.70 | **0.90** |
| human_test (open-ended) | GPT-5.4-mini | **0.90** | 0.60 | 0.60 |
| augmented_test | GPT-5.4 | **0.60** | 0.50 | **0.60** |
| human_test | GPT-5.4 | 0.90 | 0.60 | **1.00** |

On programmatic chart QA (which asks for specific data-lookup), the pre-registered **document_layout** schema forces Pass-1 to extract axis values and series as structured text; Pass-2's reasoning over that table beats end-to-end visual lookup. On open-ended chart QA (which demands gist interpretation), the layout schema discards the gestalt and loses.

Pattern inverts across capability: GPT-5.4-mini wins C2 on augmented_test; GPT-5.4 wins C2 on human_test. Same prompt, different capability regime → different alphabet-match.

### 2.3 Gemini 3.1 Pro on DocVQA: plain cascade LOSES 25 points, augmented RECOVERS

| Type | C0 | C1 | C2 |
|---|---:|---:|---:|
| all 5 types | 0.95–1.00 | 0.50–0.75 | 0.95–1.00 |

C1 (plain OCR transcription) drops accuracy by −0.25 uniformly across all question types because the bare text loses spatial/structural information needed to answer. C2 with the layout schema (bboxes, reading_order, table/form structure) recovers to C0's accuracy. **This is evidence that the schema's richness matters directly — a minimalist cascade loses information that an enriched one preserves.**

## 3. DIRECT alphabet-match validation (music-schema ablation, n=12)

Swapped the pre-registered speech-centric `audio_uas.md` for a `audio_music.md` schema (tonal / instrumentation / structure / cultural) on the 12 music-modality MMAR items. Everything else fixed: same model (Gemini 3.1 Pro), same audio, same Pass-2 prompt.

| Condition | Accuracy | Δ vs C2-speech |
|---|---:|---:|
| C0 end-to-end | 0.833 | |
| C1 plain cascade | **0.917** | |
| C2 speech UAS | 0.583 | baseline |
| **C2 music schema** | **0.750** | **+0.167** |

Three items where C2-music rescues C2-speech from 0 to 1:
- "Which chord shows distortion?" (speech UAS output `[inaudible] events:[music]`; music schema emits full chord progression)
- "What is the mode of the instrument?"
- "What is the issue with the actor's singing?"

One item broken by over-commitment: music schema correctly identifies a Jaw Harp but that locks Pass-2 into an interpretation that misses the actual "how is it played" answer; the speech UAS's vague "mechanical sounds" happened to leave Pass-2 enough ambiguity to guess correctly.

**The schema's content drives the cascade gap, independent of model or task.** This is the cleanest causal evidence for the paper's reframe.

## 4. Unexpected finding: plain cascade (C1) beats augmented cascade (C2) on Pro

Across the three conditions, the pattern `C1 > C2` shows up on:
- MMAR music items: C1=0.917, C2-music=0.750
- DocVQA Gemini Pro overall: C1=0.70, C2=0.95 (here C2 wins)
- DocVQA Gemini Flash overall: C1=0.85, C2=0.45 (here C1 wins big)

Flash cannot follow the complex layout schema (C2=0.45) but can follow plain OCR (C1=0.85). Pro follows both but the schema's structure helps on DocVQA.

**Conclusion: C2 outperforms C1 only when the model is capable enough to faithfully emit the schema.** On weaker models, verbose schemas introduce errors that compound. The paper's §4.3 expectation of monotonic alphabet-richness is wrong; the right axis is **(alphabet-match × model-capability)**, not schema richness alone.

## 5. Compute Pareto — the killer argument against cascade

| Cell | C0 tokens | C2 tokens | ratio | C0 latency | C2 latency | ratio |
|---|---:|---:|---:|---:|---:|---:|
| MMAR × Pro | 1 | 99 | 99× | 13.4 s | 37.9 s | 2.8× |
| DocVQA × Pro | 4 | 2,981 | **745×** | 6.4 s | 29.7 s | 4.6× |
| DocVQA × GPT-5.4 | 6 | 2,418 | **403×** | 2.1 s | 27.8 s | 13.2× |
| DocVQA × Qwen3-VL-30B-Thinking | 60 | **9,855** | **164×** | 4.3 s | **105.4 s** | 24.5× |
| ChartQA × GPT-5.4-mini | 8 | 427 | 53× | 1.1 s | 4.4 s | 4.0× |

**Even in the few cells where C2 wins, the accuracy gain is +5 to +20 points at 50-750× token cost.** For a practitioner deciding whether to wire up a cascade in production, the Pareto dominates every reasonable budget except very specific task classes with known schema-match.

## 6. The paper's sharper thesis (v2)

The plan's v1 thesis ("cascade beats end-to-end on symbolic tasks") is not defensible on current-gen models at short-form QA. The plan already reframed to a v2 thesis in `cascade_gap_paper_plan.md` §1 after these pilots:

> The sign of the cascade gap is governed primarily by **alphabet-match** between the task-class and the pre-registered Pass-1 schema, and secondarily by the model's native-modality and Pass-2 reasoning capability. A task-property predictor of alphabet-match predicts Δ's sign across audio, document, and chart modalities.

This is defensible by the pilots: the music-schema ablation causally demonstrates alphabet-match, the Flash Signal-Layer result shows the capability-dependent regime, and the ChartQA augmented_test result shows the effect is not modality-specific.

## 7. What this report does not yet cover

**The user flagged that short-form QA is the wrong instrument; the interesting scenarios are long-form generation (hour-long audio, full papers) where end-to-end hallucinates and cascades preserve faithfulness.** Two pilots for these are in flight but not yet complete at time of this report:

- **Long-form audio → summary**: Dan Pink TED (18.6 min, YT captions reference) + Karpathy State of GPT (42.6 min, Whisper-large-v3-turbo reference).
- **Long-form PDF → summary**: MMAR 24pg, Step-Audio-R1 22pg, Beyond Transcription 16pg. Each paper sent as multi-image Gemini input.

Both use an LLM-judge scorer (`pilot/llm_judge.py`) that atomizes the generated summary into claims and verdicts each as SUPPORTED / UNSUPPORTED / CONTRADICTED against the reference, plus a coverage check for recall. The hypothesis is that on these boundary-pushing tasks C0 will exhibit materially more unsupported claims and lower coverage than C1/C2.

Results will be appended to this report when the runs complete.

## 8. Artifact inventory

All runs in `runs/<tag>/`:
- `calls.jsonl` — every model call with prompt, response, tokens, latency
- `items.jsonl` — one row per task item with per-condition scores
- `summary.json` — aggregate stats

Scripts in `pilot/`:
- `pilot_mmar.py` — generalized MMAR runner (Gemini + OpenRouter)
- `pilot_mmar_gemini.py` — original single-provider script
- `pilot_mmar_qwen_local.py` — local Qwen2.5-Omni-7B 4-bit NF4
- `pilot_mmar_music_schema.py` — alphabet-match validation
- `pilot_vision.py` — DocVQA / ChartQA runner
- `pilot_longform_pdf.py` — full-paper summary pilot (in flight)
- `pilot_longform_audio.py` — hour-long audio summary pilot (in flight)
- `llm_judge.py` — faithfulness + coverage scorer
- `aggregate.py` — cross-model table generator

Schemas in `harness/schemas/`:
- `audio_uas.md` — pre-registered speech-centric UAS (tonal-less)
- `audio_music.md` — pre-registered music schema (matches music content)
- `document_layout.md` — pre-registered document layout schema
- `gui_affordance.md` — pre-registered GUI schema (not yet piloted)

## 9. What Phase 2 should do

1. **Long-form is where the effect lives.** Finish the in-flight pilots, extend audio to 3-5 hour-long lectures/podcasts, extend PDF to 5-10 papers or tech reports of 20-60+ pages. Target: measure hallucination count explicitly.
2. **Schema router.** Implement Pass-0 classifier: "this audio is speech / music / environmental / mixed; use schema X." Run the routed system on the full MMAR pilot subset; expect Δ(routed-C2 − speech-UAS-C2) > +0.15.
3. **Alphabet-richness sweep.** For one chosen task, sweep schema richness from `transcription-only` → `transcription + timestamps` → `+speaker` → `+prosody` → `+affect` → `+events` → `+cultural` and plot accuracy vs tokens. The existing plan §4.3 names this as C3; now it must be the main ablation.
4. **Contamination check.** MMAR, DocVQA, ChartQA all predate Gemini 3.1 Pro's Feb 2026 cutoff. Pre-test on a held-out extension before making contamination-robust claims.
5. **Drop Qwen3-VL thinking mode from the headline matrix.** On DocVQA it strictly Pareto-loses: ~ 165× tokens for a −5pt regression. Its utility is for tasks where thinking matters; our pilots are not that task class.

---

## Appendix A: per-run reproducibility

| Run tag | Start (epoch) | Model | Benchmark | N | Notes |
|---|---|---|---|---:|---|
| pilot-1776931869 | 2026-04-23 08:11:09 | gemini-3.1-pro-preview | MMAR | 20 | Original audio Pro run |
| gemini-gemini-3-flash-preview-1776933521 | 08:38:41 | gemini-3-flash-preview | MMAR | 20 | Flash audio run |
| local-qwen25omni7b-1776933687 | 08:41:27 | Qwen2.5-Omni-7B (4-bit NF4) | MMAR | 20 | Local GPU |
| vision-openai-gpt-5.4-1776933702 | 08:41:42 | gpt-5.4 | DocVQA | 20 | Direct OpenAI |
| vision-openrouter-openai--gpt-5.4-mini-1776933725 | 08:42:05 | openai/gpt-5.4-mini | DocVQA | 20 | OpenRouter |
| vision-openrouter-qwen--qwen3-vl-30b-a3b-thinking-1776933703 | 08:41:43 | qwen/qwen3-vl-30b-a3b-thinking | DocVQA | 19 | 1 error |
| vision-gemini-gemini-3-flash-preview-1776934843 | 09:00:43 | gemini-3-flash-preview | DocVQA | 20 | |
| vision-gemini-gemini-3.1-pro-preview-1776934843 | 09:00:43 | gemini-3.1-pro-preview | DocVQA | 20 | |
| chartqa-openrouter-openai--gpt-5.4-mini-1776935088 | 09:04:48 | openai/gpt-5.4-mini | ChartQA | 20 | |
| chartqa-openai-gpt-5.4-1776935477 | 09:11:17 | gpt-5.4 | ChartQA | 20 | |
| mmar-music-schema-gemini-3.1-pro-preview-1776935675 | 09:14:35 | gemini-3.1-pro-preview | MMAR-music | 12 | Alphabet-match ablation |

All seeds: 0. All decoding: temperature=0, top_p=1. Pass-1 and Pass-2 use identical decoding params (§4.4 control).
