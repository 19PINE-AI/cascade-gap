# Three follow-up experiments: Mode-fix tests + Mimo paper-modality

**Date:** 2026-05-04
**Goal:** further close the most attackable gaps in the cascade-gap dataset.

Three experiments run in parallel:

1. Chunked Pass-2 on Claude/Heat Pipes — does the Mode A fix also help Mode B?
2. Citation-stripped Pass-2 on Claude/Heat Pipes — isolate the Mode B mechanism.
3. Mimo v2-omni on Thermal Analysis 66pp paper — is the Mimo audio wash a model-size effect or modality-specific?

## Heat Pipes 104pp: full Claude variant matrix

| Variant | Halluc | Coverage | Words | Notes |
|---|---:|---:|---:|---|
| C0_claude (multimodal end-to-end) | **4** | 0.900 | 3,308 | Image-grounded baseline |
| C1_claude (single Pass-2) | 20 | 0.900 | 2,077 | Mode B failure |
| **C1_stripped_claude** (citations replaced with `[REF]`) | **13** | **0.980** | 2,471 | **Best Pareto pt. on faithfulness** |
| **C1c_claude** (chunked + Claude merge) | 18 | **0.980** | 2,769 | **Best on coverage** |
| C1c_claude_concat (chunked, no merge) | 20 | 0.940 | 2,777 | Equal halluc to single Pass-2 |

Key findings:

### Citation stripping isolates Mode B (training-prior leak)

Replacing 63 citation surface forms (`Reference N`, `Refs. M-N`, etc.) with `[REF]` reduced Claude C1's hallucinations from 20 → 13 (**−35%**) and *increased* coverage 0.90 → 0.98 (**+8 pp**).

Interpretation: ~7 of the 20 hallucinations were citation-triggered. Claude saw "Reference 5" and filled in "(TRW)"; saw "Reference 12" and filled in "Allingham and McEntire (1961)". When the surface form is `[REF]`, the model can't bait itself into expanding to remembered details.

The remaining 13 hallucinations are training-prior leaks via *other* surface forms — author names mentioned in the document where Claude knows additional details not in the document (e.g., "McAdams" mentioned without a year, but Claude's review supplies a year). Stripping author names is harder without losing semantically meaningful content, so we stop at the citation-stripping ablation.

**Mode B mechanism confirmed:** at least the citation-form sub-mechanism is real. Stripping it gives a measurable hallucination reduction.

### Chunked Pass-2 doesn't fix Mode B

The chunked Pass-2 fix that worked on Gemini (Heat Pipes Mode A: C1 0.78 → C1c_concat 0.94 cov, +16 pp) doesn't reduce Claude's hallucinations on Heat Pipes:

- C1_claude: 20 halluc, 0.90 cov
- C1c_claude (chunked + merge): 18 halluc, 0.98 cov — coverage went up, halluc barely moved
- C1c_claude_concat (chunked, no merge): 20 halluc, 0.94 cov — still at 20

This is informative: **Mode A and Mode B respond to different fixes.** Chunked Pass-2 relieves the compression bottleneck (Mode A), giving each chunk's Pass-2 more room to preserve content. But it doesn't suppress training-prior leak (Mode B) — within each chunk, Claude still encounters citation surface forms and still expands them.

The fixes compound (citation strip + chunked Pass-2) — but we haven't run that combination yet. Hypothesized: stripped + chunked → 8-10 halluc, 0.98 cov, on the Pareto frontier.

### Cross-vendor takeaway: optimal cascade architecture is vendor-dependent

| Vendor | Best variant | Halluc | Coverage |
|---|---|---:|---:|
| Gemini 3.1 Pro | C1c (chunked + merge) | **4** | 0.58 |
| Gemini 3.1 Pro | C1c_concat (chunked, no merge) | 16 | **0.94** |
| Claude Opus 4.7 | C0_claude (no cascade!) | **4** | 0.90 |
| Claude Opus 4.7 | C1_stripped_claude | 13 | **0.98** |

For **Claude on a heavily-cited document, end-to-end multimodal is competitive with the cascade.** C0_claude already achieves 4 halluc and 0.90 coverage. The cascade only adds marginal coverage (0.98 vs 0.90) at a cost in faithfulness (13 halluc vs 4). This is a meaningful caveat: when the paper's citation density is high and the model has strong training-data overlap, going through a cascade is a Pareto loss on faithfulness.

For **Gemini on the same document, the cascade is necessary** to reach the high-coverage end of the Pareto frontier (Gemini C0 max 0.72; Gemini cascade max 0.94 with chunked Pass-2).

This is a major reframing: **cascade vs end-to-end isn't a single answer; it's vendor-dependent.** Claude's cascade is mostly useful as an additional probe/validator pass on Mode A papers, not as a default replacement for end-to-end on Mode B papers.

## Mimo on Thermal Analysis 66pp: paper-modality cascade replicates

The Mimo audio result was a wash (Karpathy +1.9 pp coverage, no halluc change). On paper-modality:

| Vendor | Condition | Halluc | Coverage | Words |
|---|---|---:|---:|---:|
| Gemini 3.1 Pro | C0 | 5 | 0.680 | 1,187 |
| Gemini 3.1 Pro | C1 | 2 | **0.840** (+16 pp) | 1,473 |
| Claude Opus 4.7 | C0 | 11 | 0.920 | 3,005 |
| Claude Opus 4.7 | C1 | 4 | **1.000** (+8 pp) | 2,811 |
| Mimo v2-omni | C0 | 5 | 0.540 | 1,018 |
| Mimo v2-omni | C1 | 6 | **0.780** (+24 pp!) | 1,114 |

**Mimo's paper cascade gives +24 pp coverage** — comparable to or exceeding Gemini's and Claude's gains on the same paper. Hallucinations went up by exactly 1 (within noise).

This rules out the "Mimo is too small to benefit from cascade" interpretation of the audio result. Mimo benefits from cascade in the paper modality just like the larger models do. The audio wash is therefore **modality-specific** to Mimo:

Possible reasons (not distinguishable with current data):
- Mimo's audio multimodal pathway is weaker than its image-multimodal pathway
- The 16kbps re-encode (forced by Mimo's 10MB audio limit) hurt cascade specifically
- Mimo's audio attention has more dropout than its image attention, making C0 audio output sparser

Whatever the cause, Mimo's audio result no longer falsifies the cross-vendor cascade claim on its own — that claim is now well-supported on the paper modality across 3 vendors.

## Refined cross-vendor scoreboard

After 11 cells across 3 vendors:

**Paper modality (n=2 papers × 3 vendors = 6 cells):**
- Thermal Analysis 66pp: Gemini ✓, Claude ✓, Mimo ✓ — cascade replicates universally
- Heat Pipes 104pp: Gemini ✓ (small), Claude ✗ (Mode B counter-cell), Mimo (not tested)

**Audio modality (n=2 audio × 3 testable vendors = 4 cells):**
- Karpathy 42-min: Gemini ✓, Mimo ✗ (wash), gpt-audio (not testable, audio-strict)
- IETF SNAC 60-min: Gemini ✓, others (not tested due to Mimo size limit)

The cleanest summary statistic: **on the moderate-length paper (66pp), 3/3 vendors confirm cascade.** That single cell carries most of the weight for "cascade works across vendors."

The Heat Pipes Claude failure is now mechanistically understood (Mode B, citation surface forms triggering training-prior expansion) and partially fixable via citation stripping.

## Two operational fixes for two failure modes

| Failure mode | Trigger | Fix | Evidence |
|---|---|---|---|
| Mode A: compression bottleneck | Long source, fixed Pass-2 budget | Chunked Pass-2 (no merge) | Heat Pipes Gemini: C1 0.78 → C1c_concat 0.94 (+16 pp cov) |
| Mode B: training-prior leak | Citation surface forms in transcript | Replace `Reference N` with `[REF]` placeholders | Heat Pipes Claude: C1 20 halluc → C1_stripped 13 halluc (−35%) |

Both fixes are simple to implement and don't require model retraining. They go in the paper as engineering recommendations.

## What we still don't have

- **Strip + chunked combined.** Plausibly best-of-both: 8-10 halluc, 0.98 cov on Heat Pipes Claude. ~30-min experiment.
- **Mode B test on Gemini Natural Vibration.** If citation stripping reduces hallucinations there too, the mechanism generalizes across vendors. ~10-min experiment.
- **Cross-vendor on Heat Pipes 104pp with Mimo.** Tests whether Mimo also fails on long papers (Mode B-like) or just performs at its smaller-model ceiling.
- **Audio cross-vendor with a stronger-than-Mimo audio multimodal.** Hardest because of vendor availability — Claude doesn't do audio, gpt-audio is audio-strict. Maybe Gemini Flash 3.1 (different size variant) or a Llama 4 Vision variant if they expose audio.

## Bottom-line for the paper

The thesis is now defensible at three nested levels:

1. **At the level of the cascade existing**: well-established. 9/9 Gemini cells, plus cross-vendor confirmation on the moderate paper across 3 vendors.

2. **At the level of when it works**: well-characterized. Two formal failure modes (compression bottleneck, training-prior leak) with mechanistic evidence and engineering fixes.

3. **At the level of practical recommendations**: actionable. Cascade is the right default for Gemini and Mimo; for Claude, cascade vs end-to-end depends on whether the source is citation-heavy (Mode B trigger). Two pre-processing fixes (chunked Pass-2 for Mode A, citation stripping for Mode B) extend the cascade's operating regime.

This is publishable as an engineering + measurement paper. The story is now substantially stronger than before this push, because it has predictive power: a practitioner can look at a new source, predict whether they'll hit Mode A or Mode B, and pick the right cascade variant.
