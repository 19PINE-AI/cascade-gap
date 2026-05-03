# Cross-vendor n=2: Claude on Heat Pipes 104pp — counter-cell, training-prior leak

**Date:** 2026-04-30
**Run:** `runs/paper-review-19700025120-1777462513/`
**Source:** NASA Tech Memo AST-275 (1968), 104 pages, "Application of Heat Pipes to Spacecraft Thermal Control Problems"

This is the second cross-vendor paper cell after Thermal Analysis 66pp (which fully replicated the cascade pattern). The result on Heat Pipes is **opposite** — Claude's cascade goes the wrong way on hallucinations, doesn't help on coverage.

## Numbers across all conditions

| Vendor | Condition | Output words | Halluc | Coverage |
|---|---|---:|---:|---:|
| Gemini 3.1 Pro | C0 | 1,837 | 14 | 0.720 |
| Gemini 3.1 Pro | C1 | 1,815 | 11 | 0.780 |
| Gemini 3.1 Pro | C1c (chunked + merge) | 955 | **4** | 0.580 |
| Gemini 3.1 Pro | C1c_concat (chunked, no merge) | 2,747 | 16 | **0.940** |
| Claude Opus 4.7 | C0 | 3,308 | **4** | **0.900** |
| Claude Opus 4.7 | C1 | 2,077 | **20** | 0.900 |

Two big cross-vendor observations:

1. **Claude C0 dominates Gemini C0** (4 halluc vs 14, 0.90 cov vs 0.72) — Claude's image-grounded extraction on this 104pp paper is much stronger.
2. **Claude C1 reverses the cascade** (4 → 20 halluc, no coverage gain) — Pass-2 from the cascade transcript actually makes Claude *worse*.

## Why Claude C1 hallucinates 5× more than C0

Inspecting the 20 unsupported claims (`judge_halluc_C1_claude.json`), the dominant pattern is **training-prior leak**: Claude expands abbreviated citations in the transcript with bibliographic details that are correct in the published literature but absent from this specific document.

Examples (paraphrased from the judge's findings):

| Transcript says | Claude C1 says (unsupported) |
|---|---|
| "Reference 2 (Cotter)" | "Cotter's 1965 analysis (LA-3246-MS)" — year and report number not in transcript |
| "Reference 5" | "Reference 5 (TRW)" — TRW affiliation not in transcript |
| "Reference 11" | "Reference 11 (Katzoff)" — author name not in transcript |
| "Reference 12" | "correlation from Allingham and McEntire (1961)" — author names + year not in transcript |
| "Reference 13" | "McAdams' laminar horizontal-tube formula" — author name not in transcript |
| "proposed by Haller, et al of NASA" | "Vapor chamber-fin radiator (Haller, Lieblein, and Lindow at NASA Lewis)" — Lieblein, Lindow, NASA Lewis not in transcript |

These details are real — Cotter LA-3246-MS (1965) is a real foundational heat-pipe paper, McAdams is the real author of the cited correlation, Haller / Lieblein / Lindow at NASA Lewis really proposed this radiator. Claude has seen this 1960s heat-pipe literature in training and "fills in" the abbreviated references with what it knows.

In addition, one claim is a **sign-error on a physics inequality**: the transcript states the no-boiling condition as `p_v − p_ℓ ≤ 2σcosθ/r_c`; Claude's review writes `≥`. That's not training prior, that's a literal misreading by Pass-2.

## Why C0 doesn't have the same problem

Claude C0 (multimodal, reading page images directly) had only 4 hallucinations. The page images include the actual references list with full bibliographic details. C0 sees the literal citations as printed and reproduces them faithfully. C1 Pass-2 reads only the cascade transcript, which abbreviated everything to "Reference N" — leaving room for the model's prior to fill in details.

This is a clean **mechanism finding**: the cascade Pass-2 has *less* visual grounding than the multimodal Pass-1 on documents where references are printed. When the document body refers to "[2]" or "Reference 2", a multimodal pass can flip back to the bibliography. A text-only Pass-2 working from a transcript that abbreviated those references cannot.

## Cascade failure modes are now formally two

Phase-3 has surfaced two distinct failure modes for the cascade:

### Mode A — Compression bottleneck

Cascade Pass-2 has too much transcript to compress into a fixed output budget, drops content the same way C0 drops content. Coverage gain shrinks toward zero on long papers.

- Gemini Heat Pipes C1 vs C0: +6 pp coverage gain (vs +33 pp on Karpathy)
- Confirmed mechanism by chunked Pass-2 (C1c_concat: +22 pp by relieving the bottleneck)

### Mode B — Training-prior leak

Cascade Pass-2 from text fills in details (citations, names, dates) from training data when the transcript abbreviates them. C0's image-grounded extraction is more faithful because details are visually verifiable.

- Claude Heat Pipes C1 vs C0: 4 → 20 hallucinations
- Gemini Natural Vibration 42pp C1 vs C0: 4 → 5 hallucinations + −17 pp coverage (was unexplained, now consistent — historical references like Beckley 1946, Lewis & Wrisley 1950 in this paper are exactly the kind of content that triggers training-prior leak)

The two failure modes can compound. Heat Pipes had Mode A on Gemini (modest coverage gain) but largely escaped Mode B (Gemini's training prior on heat-pipe literature isn't as detailed as Claude's, apparently). Heat Pipes has Mode B on Claude (catastrophic hallucination increase). Natural Vibration on Gemini has Mode B (the only counter-cell in the original 9 cells).

## Refined cross-vendor claim

After Thermal Analysis 66pp + Heat Pipes 104pp at n=2 cross-vendor papers:

> The cross-vendor cascade pattern replicates on **moderate-length** papers (Thermal Analysis 66pp: both vendors show −60% halluc, +8-16 pp coverage). On the longest paper tested (Heat Pipes 104pp), the cascade pattern is vendor-dependent: Gemini retains a small cascade win, Claude reverses to a counter-result driven by training-prior leak on famous historical references.

The two failure modes (compression bottleneck, training-prior leak) are now both motivated by direct evidence from cross-vendor experiments, not just a single counter-cell.

## What this means for the paper

The cross-vendor story is now two-sided:

**Strengths:**
- 2 vendors confirm cascade on the moderate-length paper (Thermal Analysis 66pp)
- Mechanism story (compression-relief + chunked Pass-2 fix) holds at n=2
- Inter-judge replication confirms the direction-agreement findings on every cell

**Honest caveats:**
- Long papers can break the cascade in vendor-specific ways
- Claude's training-prior leak on 1960s heat-pipe literature is a real, observable failure mode
- Practitioners should expect cascade to underperform on long, heavily-cited domain papers when the model has detailed training data on that domain

This makes the paper much more publishable than a uniformly positive story. Reviewers will trust nuanced claims with documented failure modes more than universal claims with no caveats.

## Next experiments (if time allows)

1. **Cross-vendor Heat Pipes with chunked Pass-2 on Claude (C1c_claude)** — does chunked Pass-2 also help Claude as it helped Gemini? If yes, the chunked Pass-2 fix is vendor-independent. If no, Claude's failure mode is fundamentally different from Gemini's.
2. **Thermal Analysis 66pp cascade behavior on Mimo paper** — adds a third vendor on the moderate-paper case.
3. **Same-paper rerun with citations stripped from the transcript** — would isolate Mode B by removing the surface form (reference numbers) that triggers the training-prior leak.
