# Synthesis — 2026-04-23 end-of-day

After running 11 pilots (3 audio × 3 conditions + 6 DocVQA × 3 + 2 ChartQA × 3), the paper's core thesis needs sharpening. Document this so the final paper draft has a clean framing rather than the plan's current "symbolic → perceptual" axis, which the data does not support.

## The three findings that matter

### 1. There is no cascade gap on current-gen frontier omni models for standard benchmarks

Gemini 3.1 Pro on MMAR: C0=0.90, C1=0.80, C2=0.60. GPT-5.4 on DocVQA: C0=0.85, C1=0.85, C2=0.80. Frontier omni models have native-modality perception and reasoning at near-ceiling on standard benchmarks. There's nothing left for a cascade to add; often the cascade strictly hurts.

**Paper consequence:** the "cascade-beats-end-to-end" headline framing is false for the headline models. The paper needs to be about **when and why** the cascade helps (weaker models, mismatched task structure), not a universal claim.

### 2. The cascade gap's sign depends on alphabet-match, not symbolic-vs-perceptual

Two concrete data points show the plan's axis is wrong — or at least, a worse predictor than "alphabet-match":

- **Gemini 3 Flash on MMAR Signal Layer** (sounds-perceptual, e.g., "is this studio-recorded?"): C0=0.20, C1=0.40, C2=0.40. **Cascade wins** — because Signal-layer answers are actually tag-representable (presence/absence of distortion, studio-vs-field). The "perceptual" label is misleading; these are *structured-tag-representable* questions.
- **Gemini 3 Flash on MMAR Semantic Layer** (sounds-symbolic, e.g., "what game are they playing?"): C0=1.00, C2=0.40. **Cascade bombs** — because the semantic meaning depends on *prosody and tone* that transcription drops. The "symbolic" label is misleading; these are *prosody-dependent* questions.
- **GPT-5.4-mini on ChartQA augmented_test**: C0=0.70, C2=0.90. **Augmented cascade wins** — because automated chart QA asks about specific numeric cells that the layout-schema captures cleanly.
- **GPT-5.4-mini on ChartQA human_test**: C0=0.90, C2=0.60. **Augmented cascade loses** — human-written questions are open-ended and resist reduction to the layout schema.

**Reframed thesis (v2):**

> Cascade gap Δ is positive when the task's load-bearing features can be losslessly represented in the Pass-1 text schema, and negative when the answer depends on features the schema drops. The symbolic-vs-perceptual axis proxies for this imperfectly; the predictor's features should measure *alphabet-match directly*.

### 3. Token cost is a Pareto killer even when accuracy ties

Even in the best case (ChartQA augmented_test, +0.20 gap), C2 costs **53×** more output tokens and **4×** latency than C0. On DocVQA GPT-5.4, C2 costs **372×** more output tokens with no accuracy benefit. The paper cannot recommend C2 as a practitioner's default — it has to be conditional on task-class.

## The paper's repositioning

From the plan's original thesis:
> "prompting the same frontier model in a two-pass self-cascade ... yields meaningfully better task accuracy than the model's native end-to-end mode"

To the reframed thesis:
> "The cascade gap's sign — and therefore whether a self-cascade is worth the token cost — is governed primarily by alphabet-match between task-class and pre-registered Pass-1 schema, and secondarily by the model's native-modality capability. We provide the first systematic measurement of both effects across audio, document, and chart modalities."

This is a **less bold but more defensible** thesis. It:
- Acknowledges upfront that the cascade is usually worse.
- Pivots the contribution from "cascade wins" to "when cascade wins and why," which is more practically useful.
- Keeps §4.6's predictive rule as the paper's central artifact (now predicting alphabet-match rather than gap sign directly).
- Makes the per-task-class schema design in §4.3 a first-class contribution, not an ablation.

## What Phase 2 needs to do differently

1. **Per-task-class schemas.** Our pre-registered UAS schema is speech-centric and broke on music items. Phase 2 needs: speech UAS, music UAS (`tempo, key, chord_progression, mode, instruments, timbre`), environmental-sound UAS (`sources, direction, motion, background`), document layout, chart structure, GUI affordance. Schema design is itself a paper contribution.

2. **Weaker-model emphasis.** The cascade gap only shows up positively on models that can't handle the task natively. Phase 2 should front-load smaller open-weight models (Qwen2.5-Omni-7B, Qwen3-VL-8B) and treat frontier models as a ceiling reference, not the headline.

3. **Perturbation-based contamination check.** On ChartQA augmented_test, the +0.20 cascade gap could reflect template pattern-matching. Rerun with re-rendered charts where the numeric values are replaced with arbitrary integers, keeping the template. If the gap persists, the reasoning is real; if it collapses, the gap is contamination.

4. **Compute-Pareto-first plotting.** Accuracy-at-token-budget on the same plot as cascade-gap heatmap. Figure 4 in the plan becomes Figure 1: practitioners care about the Pareto, not the gap.

## Still-open questions after today's pilots

- **Does Qwen2.5-Omni-7B (local audio) show a larger positive gap than Gemini?** Partial answer after 13/20 items: NO. Qwen2.5-Omni-7B shows the same directional pattern as Pro (C0 > C1 > C2), contradicting the "weaker model benefits from cascade" hypothesis. The Flash result (cascade helps on Signal Layer) seems to be a sweet spot: weak enough at acoustic reasoning that cascade helps, strong enough at text reasoning that Pass-2 can exploit it. Below that threshold (Qwen-7B at 4-bit), Pass-2 is also too weak.
- **Does Gemini 3.1 Pro on DocVQA show a non-zero gap?** Pilot running.
- **Do Qwen3-VL-30B / 235B thinking models show the gap?** Partial (11-15/20): **NO meaningful gap — C0=C1=C2=1.00 on the items so far.** Both models solve DocVQA near-perfectly, regardless of condition. C2 costs 8,900+ output tokens for the same answer (thinking-mode verbosity). Strict Pareto loss.

## DIRECT alphabet-match validation (music schema on MMAR) — **COMPLETE (n=12)**

Critical experiment: re-run MMAR music-modality items with a pre-registered `audio_music.md` schema (tonal / instrumentation / structure / cultural) instead of the speech-centric UAS. Same model, same Pass-2 prompt.

Full results on 12 music-modality items from the pilot sample (9 originally music-modality + 3 additional flagged by question keywords: chord, instrument, singing):

### Aggregate

| Condition | Accuracy |
|---|---:|
| C0 (end-to-end) | 0.833 |
| C1 (plain cascade, transcription) | **0.917** |
| C2 (speech UAS, pre-registered) | 0.583 |
| **C2 (music schema)** | **0.750** |

**Δ(music − speech) = +0.167** (same model, same audio, same Pass-2; only Pass-1 schema changed).

### Per-layer

| MMAR layer | n | C0 | C2-speech | C2-music | Δ(music − speech) |
|---|---:|---:|---:|---:|---:|
| Signal | 3 | 0.667 | 0.333 | 0.667 | **+0.333** |
| Perception | 4 | 0.750 | 0.500 | 0.500 | 0.000 |
| Cultural | 5 | 1.000 | 0.800 | 1.000 | +0.200 |

### Per-item (6 of 12 shown; all 12 in runs/mmar-music-schema-*/items.jsonl)

| Question (truncated) | C0 | C1 | C2-speech | C2-music | Δ |
|---|:--:|:--:|:--:|:--:|:--:|
| "Which chord shows distortion?" | 1 | 0 | **0** | **1** | +1.0 |
| "What is the mode of the instrument?" | 1 | 1 | **0** | **1** | +1.0 |
| "What is the issue with the actor's singing?" | 1 | 1 | **0** | **1** | +1.0 |
| "Emotion of music, happy or sad?" | 1 | 1 | 1 | 1 | 0 |
| "Style of music?" | 1 | 1 | 1 | 1 | 0 |
| "How might the instrument be played?" | 1 | 1 | **1** | **0** | **−1.0** |

3 items rescued, 1 item broken by over-commitment, rest tied. Net +2 items out of 12.

### What the numbers mean

1. **Primary claim survives: alphabet-match drives the cascade gap within augmented cascades.** Music schema beats speech schema by 17 points on music content. The effect is carried by a small number of items where the speech schema produced degenerate `[inaudible] events:[music]` Pass-1 output.

2. **A new nuance surfaces: plain cascade (C1) beats both augmented schemas at 0.917.** C1 is unopinionated — it transcribes whatever it can and hands the audio context implicitly to Pass-2. Augmented schemas commit Pass-1 to a specific structured interpretation that can be wrong. One concrete failure: on a Jaw Harp item, music schema correctly identified the instrument (Khomus) but Pass-2 then answered the "how is it played" question wrong; speech schema's vague "mechanical sounds" tag left Pass-2 enough ambiguity to guess correctly.

3. **The paper's C3 "richer alphabet always helps" expectation from §4.3 is wrong.** On music content, the ordering is:
   speech-UAS < music-schema < plain transcription (C1)
   That is, *less* schema can be better when the schema risks over-committing. The paper should report this as a finding, not hide it.

### Two concrete paper claims that follow

- **Existence of alphabet-match:** there exist task classes where choice of Pass-1 schema changes Pass-2 accuracy by 30-100 points on specific items, with the sign determined by schema-content match. Validated on MMAR music items.
- **Non-monotonicity in alphabet richness:** there exists a task class (music QA on Gemini 3.1 Pro) where plain transcription beats a well-matched structured schema, because the schema over-commits Pass-1. This constrains §4.3's Figure-3 expectation.

This experiment was n=12, one model, pilot-scale. Phase-2 needs the same comparison on ~300 MMAR music items, a third "router" experiment that selects speech-UAS vs music-schema from a Pass-0 classifier, and environmental-sound equivalents.
