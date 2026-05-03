# Audio cross-vendor: cascade does NOT replicate cleanly outside Gemini

**Date:** 2026-04-30
**Tested vendors:** Mimo v2-omni (Xiaomi, via OpenRouter), gpt-audio (OpenAI, via OpenRouter), reference Gemini 3.1 Pro.
**Source:** Karpathy "State of GPT" 42-min talk (we re-encoded to 16kbps mono mp3 to fit Mimo's 10MB base64 audio limit).

This is the audio equivalent of the cross-vendor experiment that succeeded with Claude Opus 4.7 on the paper modality. The audio result is more nuanced.

## Numbers

| Vendor | Condition | Output words | Halluc | Coverage |
|---|---|---:|---:|---:|
| Gemini 3.1 Pro | C0 | 1,638 | 13 | 0.627 |
| Gemini 3.1 Pro | C1 | 1,935 | 3 | **0.961** |
| Mimo v2-omni | C0 | 1,509 | 4 | 0.569 |
| Mimo v2-omni | C1 | 1,268 | 4 | 0.588 |
| OpenAI gpt-audio | C0 | 3,010 | 10 | 0.765 |
| OpenAI gpt-audio | C1 | — | — | — |

(gpt-audio C1 not testable, see below.)

Notable: gpt-audio C0 alone (no cascade) achieves 0.765 coverage — between Gemini C0 (0.627) and Mimo C0 (0.569). It's a strong end-to-end audio model, just not a candidate for same-weights cascade because of the audio-strict constraint.

## Two distinct cross-vendor failure modes

### Mimo v2-omni: cascade is essentially a wash (-0 halluc, +1.9 pp cov)

Mimo runs both passes of the cascade, but produces near-identical hallucination counts and barely-different coverage:
- C0: 4 halluc, 0.569 coverage
- C1: 4 halluc, 0.588 coverage

Compared to Gemini's spectacular +33 pp cov / -77% halluc on the same audio, the Mimo cascade barely moves either axis. Two non-exclusive interpretations:

1. **Mimo's text reasoning ≈ its multimodal-on-audio capability.** The cascade's coverage gain on Gemini comes from Pass-2 (text reasoning over a transcript) being *stronger* than Pass-1 / C0 (multimodal reasoning over audio). On Mimo, Pass-2 from text is similar in strength to C0 from audio. There's no headroom for the cascade to fill.

2. **Mimo is smaller (~30B params, MoE) than Gemini 3.1 Pro.** Smaller models have less attention budget to spare in the first place. C0's coverage of 0.57 is already the model's ceiling on this output length, and Pass-2 can't do better.

These interpretations aren't mutually exclusive. The first is a mechanistic claim about cascade dynamics; the second is an empirical observation about model size. Distinguishing them would require a same-size cross-vendor test (e.g., Llama 4 Vision audio of similar params — not available on OpenRouter).

### gpt-audio: cascade not testable — model refuses text-only Pass-2

OpenAI's gpt-audio is an audio-strict model. When called with text-only input (as needed for Pass-2: `<transcript> + write a review`), it returns `400: This model requires that either input content or output modality contain audio`.

The same-weights cascade requires the SAME model on both passes. gpt-audio cannot do the text-only second pass, so the same-weights cascade is not realizable on this model.

This is itself a finding: **same-weights cascade requires a general multimodal model that handles both audio and text inputs**. It excludes audio-specialist models like gpt-audio. We can still measure C0 on gpt-audio for context, but the C0 vs C1 comparison the paper makes is undefined for audio-strict vendors.

## Refined cross-vendor claim

The original claim was "cascade replicates across vendors." After the Claude paper-modality success and the Mimo / gpt-audio audio-modality results, the more accurate claim is:

> The cascade pattern (cascade reduces hallucinations and improves coverage relative to end-to-end) replicates on **general-purpose multimodal models with strong text-reasoning capability**. It is testable on Gemini 3.1 Pro and Claude Opus 4.7 (both confirmed). It is not testable on audio-strict models like gpt-audio. On Mimo v2-omni — a smaller general multimodal — the cascade pattern attenuates to a wash, suggesting either model-size or text-vs-multimodal-strength-balance dependencies.

This is a more honest and more useful claim than "cascade always works." It tells future practitioners:
- If your model has strong text reasoning relative to its multimodal capability, expect cascade gains.
- If your model is small or text-reasoning-weak, expect cascade to be a wash.
- If your model is audio-strict, cascade isn't realizable.

## What we tested vs. didn't

| Vendor | Modality | Cascade testable? | Result |
|---|---|:---:|---|
| Gemini 3.1 Pro | audio + paper | yes | replicates |
| Claude Opus 4.7 | paper | yes | replicates |
| Claude Opus 4.7 | audio | no (Claude can't do audio) | not testable |
| Mimo v2-omni | audio | yes | wash (no gain, no loss) |
| Mimo v2-omni | paper | not run | unknown |
| OpenAI gpt-audio | audio | no (audio-strict) | not testable |

The "Claude on audio" cell is the cleanest open question. Claude doesn't natively do audio multimodal yet. If/when it does, we'd expect (based on the paper-modality result) the cascade to work.

## Methodological gotcha discovered

Mimo's 10MB base64 audio limit forced us to re-encode the source audio from 32kbps mp3 to 16kbps. This affects all four conditions equally (both the Gemini and Mimo runs use the same 16kbps source for the cross-vendor comparison... wait — actually, the existing Gemini run used 32kbps. So the Mimo numbers are at 16kbps, the Gemini numbers are at 32kbps).

This is a confound. Some of Mimo's poor coverage might be due to lower audio quality, not Mimo itself. The fix would be re-running Gemini at 16kbps to confirm Gemini still wins on the cascade at the same audio quality. That cell is cheap (~15 min) and worth running before publication.

## What goes in the paper

**Replicated:**
- Cross-vendor on the paper modality (Claude on Thermal Analysis 66pp, Heat Pipes 104pp).
- Cross-vendor cascade pattern with the **same direction** on both vendors at n=1 paper.

**Honest negative finding:**
- Cross-vendor on audio modality with a smaller / different-architecture vendor (Mimo) does NOT replicate the cascade gain. Possible mechanisms: model size, text-vs-multimodal strength balance.

**Methodological exclusion:**
- Audio-strict models (gpt-audio) cannot run the same-weights cascade. The paper should add this caveat to the protocol description: cascade requires a general multimodal model.

The honest scientific story is stronger than a uniformly positive one would have been: cascade has a defined operating regime (general multimodal models, strong text reasoning), not a universal one.
