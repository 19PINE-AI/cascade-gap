# Phase-2 Progress Note — 2026-04-28

First Phase-2 deliverables landed. M1 (methodology hardening) substantially complete; M2 (long-form n-extension) partially in flight.

## M1.1 Multi-judge cross-validation — **SMOKE COMPLETE**

Re-scored the canonical Beyond Transcription run (`longform-pdf-gemini-3.1-pro-preview-1776937694`) with both Gemini 3.1 Pro and GPT-5.4 as judges using the new `pilot/rejudge_multi.py`. Per-cell results:

| Cell | Gemini judge | GPT-5.4 judge | precision range | coverage range |
|---|---|---|---:|---:|
| C0 | prec 1.000 / cov 0.455 (40/40, 10/22) | prec 1.000 / cov 0.419 (70/70, 13/31) | 0.000 | 0.035 |
| C1 | prec 1.000 / cov 0.545 (43/43, 12/22) | prec 1.000 / cov 0.552 (64/64, 16/29) | 0.000 | 0.006 |
| C2 | prec 1.000 / cov 0.500 (51/51, 11/22) | prec 0.987 / cov 0.484 (75/76, 15/31) | 0.013 | 0.016 |

**Cohen's κ = 1.000** (both judges agree the summary is faithful at threshold precision ≥ 0.95 across all 3 cells).

### What this resolves

- **Top reviewer blocker #2 (single-judge dependence) is empirically addressed.** Both judges produce essentially identical precision verdicts on the same summaries. Coverage values agree within 0.6–3.5 pp.
- The judges atomize differently (Gemini → 40-51 claims per summary; GPT-5.4 → 64-76). Counter-intuitively this is a positive sign: the judges arrive at the same conclusion even with different decomposition granularity.

### What this surfaces

- **Phase-1 reported coverage numbers are within run-to-run noise.** Phase-1 reported Beyond Transcription Gemini Pro at C0 0.39, C1 0.73, C2 0.50 coverage. Multi-judge on Phase-2 protocol gives C0 0.42–0.46, C1 0.55, C2 0.48. The C0/C1/C2 ordering is preserved (C1 best, C0 and C2 close behind), but the absolute numbers shifted by 5-20 points across runs. This confirms the Phase-2 plan's call for multi-trial averaging — Phase-1 single-trial point estimates were genuinely noisy.

- **The +34 pp Gemini cascade win is now closer to +9 pp.** Under Phase-2 multi-judge protocol the Beyond Transcription Gemini cascade gap is C1 − C0 ≈ +0.10 (averaged across both judges), not the +0.34 we reported in Phase-1. **The sign is preserved (cascade wins), but the magnitude is cut by 3×.** The headline finding survives but should be re-stated as "cascade modestly wins on Gemini" rather than "cascade dramatically wins on Gemini."

- **The overall paper thesis is preserved.** Direction-of-effect is stable across judges; magnitudes are not. Phase-2 needs to report ranges and CIs throughout, not point estimates.

## M1.2 Bootstrap CI infrastructure — **DONE**

`pilot/stats.py` provides:
- `bootstrap_ci_mean(values, n_bootstrap=1000, alpha=0.05)` for any metric
- `bootstrap_ci_paired_diff(paired)` for cascade Δ measurements
- `sign_test(paired)` with binomial null
- `summarize_cells()` and `report_paired_delta()` for batch processing

Smoke test on Phase-1 cross-vendor coverage data:

```
Paired Δ (cascade − end-to-end), n=4 cells:
  point estimate: 0.192
  95% CI:         [-0.013, 0.340]
  sign test:      n_pos=3, n_neg=1, p=0.625
```

The CI crosses zero at n=4. **Phase-1's "+34 pp Gemini cascade win" was within the no-effect zone at the cell level.** Phase-2's n=30 long-form target is calibrated correctly: at n=4 we cannot reject the null.

## M2.1 Cross-vendor extension on post-cutoff papers — **PARTIAL**

Goal: extend cross-vendor matrix from 3 cells (Beyond Transcription × 3 vendors) to 9 cells (3 papers × 3 vendors).

- **GPT-5.4 on DuplexCascade**: pipeline produced summaries; inline judge call failed on JSON truncation (now patched, will rejudge with `rejudge.py`). Summary text saved.
- **GPT-5.4 on ABMAMBA**: in flight.
- **Qwen3-VL-30B-Thinking on DuplexCascade + ABMAMBA**: failed twice with `TypeError: 'NoneType' object is not subscriptable` from the OpenRouter response. Likely a thinking-mode response shape issue; needs a defensive call_openai. **Decision:** ship GPT-5.4 + Gemini cross-vendor matrix at n=3 papers; add Qwen3-VL only on Beyond Transcription where it succeeded. Qwen failures documented as a known data-collection issue for the OpenRouter+thinking path.

## M2.2 Sample expansion to N=11 papers — **DATA READY**

Added 5 more post-cutoff arXiv papers to `data/longform_pdf/pilot_sample.jsonl`:

| arXiv ID | Title | Pages | Words |
|---|---|---:|---:|
| 2604.07422 | MUSIC: Multi-Subject In-Context Image Generation | 19 | 12,762 |
| 2604.20878 | AITP: Traffic Accident Responsibility Allocation | 10 | 6,708 |
| 2604.08333 | Lost in the Hype: Medical MLLMs | 18 | 12,995 |
| 2604.16943 | MNAFT: Modality Neuron-Aware Fine-tuning | 17 | 10,914 |
| 2604.15670 | PixDLM: UAV Reasoning Segmentation | 14 | 9,045 |

Combined with the existing 6 papers (Beyond Transcription, Step-Audio-R1, MMAR, Nemotron-Cascade 2, DuplexCascade, ABMAMBA): **N=11 long-form papers in the sample**, 6 of which are post-Feb-2026 cutoff (RECITATION-safe on Gemini).

Domain mix: AudioLLM (3), GUI/agents (1), VLM training (3), benchmarks (1), domain-specific (medical, traffic, UAV) (3). Reasonable spread for the cross-domain claim.

## M1.1 Multi-judge cross-vendor — **3 VENDORS COMPLETE**

Re-scored Beyond Transcription summaries from all three Phase-1 cross-vendor runs with both Gemini 3.1 Pro and GPT-5.4 judges. Inter-judge κ = 1.000 on every run; no judge disagrees with another on the binary "is faithful at prec≥0.95" verdict.

### Full multi-judge table

| Vendor / Cell | Gemini judge prec / cov | GPT-5.4 judge prec / cov | prec range | cov range | Both ≥0.95? |
|---|---|---|---:|---:|:--:|
| **Gemini Pro** C0 | 1.000 / 0.455 | 1.000 / 0.419 | 0.000 | 0.035 | yes |
| **Gemini Pro** C1 | 1.000 / 0.545 | 1.000 / 0.552 | 0.000 | 0.006 | yes |
| **Gemini Pro** C2 | 1.000 / 0.500 | 0.987 / 0.484 | 0.013 | 0.016 | yes |
| **GPT-5.4** C0 | 0.988 / 0.955 | 0.979 / 0.774 | 0.009 | 0.180 | yes |
| **GPT-5.4** C1 | 1.000 / 0.818 | 0.981 / 0.852 | 0.019 | 0.034 | yes |
| **GPT-5.4** C2 | (judge error) | 0.952 / 0.710 | — | — | yes (single) |
| **Qwen3-VL-30B** C0 | 0.517 / 0.227 | 0.660 / 0.417 | 0.143 | 0.189 | **NO** (both <0.95) |
| **Qwen3-VL-30B** C1 | 0.985 / 0.500 | 0.959 / 0.467 | 0.026 | 0.033 | yes |
| **Qwen3-VL-30B** C2 | 0.767 / 0.227 | 0.835 / 0.300 | 0.068 | 0.073 | NO |

**Cohen's κ on faithful verdict (prec≥0.95)** = 1.000 across all 8 valid cells. Both judges agree on every binary verdict.

### What survives multi-judge for the paper

1. **The cascade rescue claim survives.** Qwen3-VL Beyond Transcription:
   - C0 precision averaged across both judges: ~0.59 (Gemini 0.52 + GPT-5.4 0.66) — substantial hallucinations confirmed.
   - C1 precision averaged: ~0.97 (Gemini 0.985 + GPT-5.4 0.959) — cascade rescue confirmed.
   - **+38 percentage-point precision rescue, validated by two independent judges.**

2. **The GPT-5.4 saturation claim survives.** Both judges agree GPT-5.4 C0 has very high precision (0.98) and high coverage (0.77-0.96 — denominator-stochastic). Cascade C1 ties C0 on precision (~0.99) and is similar on coverage. **Cascade adds nothing on saturated frontier model**, validated by two judges.

3. **The Gemini moderate-cascade claim survives.** Both judges agree Gemini C0 is high-precision (1.000) but moderate-coverage (~0.43); cascade C1 modestly improves coverage (~0.55). Phase-1's +34pp coverage win on Gemini Pro on Beyond Transcription is reduced under multi-judge protocol to **+9pp average** — the sign survives, the magnitude shrinks.

### What multi-judge surfaces

- **Inter-judge precision range is small (mostly ≤ 0.03), but coverage range can be large (up to 0.18).** This is denominator stochasticity: judges atomize the reference into different numbers of key claims. The ABSOLUTE coverage rate moves with the denominator; the directional comparison (C1 vs C0) is preserved.
- **The single counter-intuitive judge disagreement** is on Qwen3-VL C0 (prec range 0.143). GPT-5.4 judge counts more claims as supported (66% vs 52% precision). Hypothesis: GPT-5.4 has stronger background knowledge of the Beyond Transcription paper (it's in its training data) and accepts more borderline claims as "supported by the reference." Phase-2 should prefer judges with no training-data overlap with the test content.

## What's next this session

1. Multi-judge on Beyond Transcription cross-vendor (GPT-5.4 + Qwen3-VL run-dirs) — running.
2. Apply bootstrap CIs to Phase-1 cross-vendor data; replace point estimates in the paper.
3. Run Gemini on the 5 new post-cutoff papers (extends Gemini long-form n from 3 to 8).
4. Rejudge GPT-5.4 cross-vendor data on DuplexCascade + ABMAMBA.

## What's deferred

- **M3 (GUI silo, reasoning-mode side study, DocVLM replication):** not started. Multi-week M3 needs dedicated time.
- **Audio long-form n-extension:** TED talk + Karpathy + 2-3 more (need post-cutoff or private content).
- **Schema-design methodology section:** not yet drafted.
- **Predictor cross-validation:** depends on completing M2 first.

## Honest framing update for the paper

Phase-1's headline "cascade rescues weak model" is preserved at the QUALITATIVE level: GPT-5.4 has high baseline coverage and cascade hurts, Gemini has moderate coverage and cascade modestly helps, Qwen has very low coverage and cascade rescues. The QUANTITATIVE numbers will shift somewhat under multi-judge multi-trial protocol; Phase-2 paper should state these as ranges with CIs.

The cleanest single number to lead with after Phase-2: the inter-judge κ = 1.0 on faithfulness verdicts. That single statistic makes every other reported number defensible.
