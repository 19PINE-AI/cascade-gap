# Plan corrections — ready to apply

Precise edits to `cascade_gap_paper_plan.md` based on Phase 0 findings. Keep this doc as the audit trail; apply in-place when ready.

## Edit 1 — §2 Silo 1, Step-Audio-R1 paragraph

**Current text (line 27):** "their finding is consistent with ours under one reading — that an audio-only alphabet (their MGRD-trained CoT) outperforms a text-only alphabet on tasks needing acoustic features."

**Issue:** the preceding sentence attributes to Step-Audio-R1 the claim that "textual surrogate reasoning is the failure mode." That phrasing is NOT in the paper.

**Proposed rewrite:**
> The principal opposing voice is **Step-Audio-R1** (arXiv 2511.15848, Nov 2025), which reports that default audio language models "consistently perform better with minimal or no reasoning" and proposes Modality-Grounded Reasoning Distillation (MGRD) as a training-time fix that yields genuinely audio-grounded chains of thought. We read this result as consistent with ours under the alphabet-fit lens: on tasks requiring acoustic features, an audio-grounded reasoning alphabet outperforms a text-grounded one, and the cascade gap's sign flips accordingly. Importantly, Step-Audio-R1 does not include a same-weights self-cascade baseline, so our C1 condition measures a comparison their paper leaves open.

## Edit 2 — §2 Silo 1, add Cascade Equivalence Hypothesis

After the existing X-Talk sentence, insert:

> **The Cascade Equivalence Hypothesis** (arXiv 2602.17598, Feb 2026) argues the complementary point: speech LLMs *behave* like ASR→LLM pipelines internally, with transcripts emerging in hidden states and text representations causally necessary for downstream accuracy. Under noise, external cascades outperform end-to-end speech LLMs by up to 7.6 points at 0 dB. We read this mechanistically: if the internal cascade is already load-bearing, externalizing it — and enriching the externalized bottleneck with non-lexical tags, as our C2 condition does — is the natural next step.

## Edit 3 — §2 Silo 1, soften X-Talk claim

**Current:** "X-Talk (arXiv 2512.18706, Dec 2025) shows optimized cascaded speech-to-speech pipelines beat omni models on latency without accuracy loss"

**Proposed:** "X-Talk (arXiv 2512.18706, Dec 2025) argues optimized cascaded speech-to-speech pipelines achieve sub-second latency while retaining modular flexibility, challenging the assumption that end-to-end omni models are strictly dominant"

## Edit 4 — §2 add Beyond Transcription caveat

**Current (line 25):** "'Beyond Transcription' (arXiv 2604.12506) is the closest existing analogue to our augmented-cascade condition — it decomposes audio into transcription + paralinguistics + non-linguistic events and shows the structured intermediate alphabet matters; we extend this with same-model cascades and cross-modality comparison."

**Proposed addition (append to sentence):** "We note that *Beyond Transcription* realizes this schema via training-time supervision on 13,500 hours of UAS-labeled data, while we achieve it as a same-weights inference-time prompting condition on unmodified models — the two results are complementary evidence that the structured alphabet is load-bearing regardless of how it is produced."

## Edit 5 — §4.1 Model coverage — version pins

Replace the Tier-1 table with:

| Model | Version pin | Audio | Document/Vision | GUI |
|---|---|---|---|---|
| Gemini 3.1 Pro Preview | `gemini-3.1-pro-preview` (rel. 2026-02-19) | ✓ | ✓ | ✓ |
| Gemini 3.1 Flash (or Flash-Lite) | `gemini-3.1-flash-preview` / `gemini-3.1-flash-lite-preview` | ✓ | ✓ | ✓ |
| GPT-5.x + GPT-4o-audio-preview | latest stable at snapshot date | ✓ (audio-preview) | ✓ | ✓ |
| Claude Opus 4.7 / Sonnet 4.6 | `claude-opus-4-7`, `claude-sonnet-4-6` | — | ✓ | ✓ |
| Qwen3-Omni-30B-A3B-Instruct | HF `Qwen/Qwen3-Omni-30B-A3B-Instruct` | ✓ | ✓ | partial |
| Qwen3.5-Omni | HF; rel. 2026-03-30 | ✓ | ✓ | partial |
| Step-Audio-R1.1 | HF `stepfun-ai/Step-Audio-R1.1` (rel. 2026-01-14) | ✓ | — | — |
| UI-TARS-2 (72B-DPO) | HF `ByteDance-Seed/UI-TARS-72B-DPO` | — | partial | ✓ |

Drop Qwen2.5-Omni-72B (does not exist). Keep Qwen2.5-Omni-7B as a secondary-tier reference.

Record the snapshot date ("all experiments between 2026-04-X and 2026-05-X") so reproduction is anchored. §4.4 control #2 ("Prompt fairness") should also note API version pinning.

## Edit 6 — §4.2 Audio task list

Replace with:

1. LibriSQA factual QA (symbolic anchor)
2. MMAR Signal + Semantic layers (mostly symbolic)
3. AMI meeting minutes (mostly symbolic)
4. MMAR Perception layer (mixed)
5. MELD / IEMOCAP emotion classification (paralinguistic)
6. MUStARD sarcasm detection (paralinguistic)
7. MMAU music + environmental sound reasoning (perceptual)
8. DIHARD speaker diarization (perceptual) — **or substitute VoxConverse** if LDC license is a barrier

Footnote: using MMAR/MMAU lets us re-use an existing four-layer reasoning stratification (Signal / Perception / Semantic / Cultural) as the symbolic→perceptual axis, rather than imposing one from outside.

## Edit 7 — §4.4 Controls, add item 6

**Add:** "**Contamination check.** MMAR/MMAU were released before Gemini 3.1 Pro's knowledge cutoff. Report whether each closed-source model achieves above-baseline zero-shot on the public test set (suggesting pretraining exposure), and re-run headline experiments on any available held-out split."

## Edit 8 — §5 Risks, add row

| Risk | Likelihood | Mitigation |
|---|---|---|
| Audio-token API costs blow the budget | Medium | Per-model call ceiling; use Gemini 3.1 Flash-Lite for Pass-2 reasoning wherever Pass-1 is the expensive audio pass; front-load smaller open-weight runs |
| Benchmark pretraining contamination (MMAR, DocVQA, OSWorld in frontier training data) | High | Add §4.4 contamination check; prefer recent benchmark extensions; spot-check with controlled perturbations |
