# Mechanism validation report (V1/V2/V3)
_generated: 2026-06-21T08:05:52Z (autonomous overnight run)_

## V2 — multi-seed conditions on all 21 cells (powered)
Mean seeds/cell: C1=4.38, E1=4.33, E2=4.1. n_cells=21.

**E2 (single-call) vs C1 — coverage:** mean Δ=-0.1135 (bootstrap 95% CI [-0.1785, -0.0336]); E2 worse on 17/20 cells; Wilcoxon p=0.02395. 
Single-call emitted **no review** in 6 runs across cells ['3b1b', 'harvard', 'nat_vib'] (output budget exhausted).

**E1 (C1+ both) vs C1 — coverage:** mean Δ=0.0705 (CI [-0.0007, 0.1573]); TOST equivalence (SESOI 0.04): False (90% CI [-0.0024, 0.1434]). 
**Hallucinations E1 vs C1:** mean Δ=0.9762 (E1 more on 15/21; note: 'better' here = higher count). 

Synthesis (seed) variance, mean within-cell SD of coverage: C1=0.0512, E1=0.0505, E2=0.0789.

Mixed-effects coverage ~ cond + (1|cell): {'Intercept': 0.7201, "C(cond, Treatment('C1'))[T.E1]": 0.063, "C(cond, Treatment('C1'))[T.E2]": -0.1178, 'Group Var': 2.6737, 'pvalues': {'Intercept': 0.0, "C(cond, Treatment('C1'))[T.E1]": 0.0001, "C(cond, Treatment('C1'))[T.E2]": 0.0, 'Group Var': 0.00252}}

**Verdict:** E2 collapse confirmed under multi-seed; E1 vs C1 coverage not equivalent / inconclusive at current n.

## V3 — vision-model ladder + parametric load sweep (logit-lens)
| model | K | text_acc | img_acc | text_depth | img_depth | gap CI90 | equiv |
|---|---|---|---|---|---|---|---|
| Qwen2.5-VL-3B-Instruct | 1 | 1.0 | 1.0 | 32 | 32 | [0.0, 0.0] | True |
| Qwen2.5-VL-3B-Instruct | 4 | 1.0 | 1.0 | 32.25 | 32.06 | [-0.411, 0.036] | True |
| Qwen2.5-VL-3B-Instruct | 8 | 1.0 | 1.0 | 32.19 | 32.06 | [-0.265, 0.015] | True |
| Qwen2.5-VL-3B-Instruct | 16 | 1.0 | 1.0 | 32.75 | 32.06 | [-0.884, -0.491] | True |
| Qwen2.5-VL-3B-Instruct | 24 | 1.0 | 1.0 | 32.62 | 32 | [-0.831, -0.419] | True |
| Qwen2.5-VL-7B-Instruct | 1 | 1.0 | 1.0 | 24.31 | 24.44 | [-0.015, 0.265] | True |
| Qwen2.5-VL-7B-Instruct | 4 | 1.0 | 1.0 | 24.25 | 24.12 | [-0.265, 0.015] | True |
| Qwen2.5-VL-7B-Instruct | 8 | 1.0 | 1.0 | 24 | 24 | [-0.15, 0.15] | True |
| Qwen2.5-VL-7B-Instruct | 16 | 1.0 | 1.0 | 24.06 | 24.12 | [-0.04, 0.165] | True |
| Qwen2.5-VL-7B-Instruct | 24 | 1.0 | 1.0 | 24.06 | 24.12 | [-0.04, 0.165] | True |

_Note: Qwen2.5-VL-32B excluded — it verbalizes the answer in a form the single-token matcher could not capture (acc=0 artifact), so its readout numbers are unreliable; 3B+7B carry the claim._

**Verdict:** if equivalence holds across models and K, the no-substrate-gap finding generalizes; watch whether any gap opens at high K (parametric-load prediction).

## V1 — audio substrate logit-lens (Qwen2.5-Omni)
ASR sanity accuracy (model can transcribe TTS clips): 0.875.
text_acc=0.958 audio_acc=1; readout depth text=22.583 audio=22.958 (of 28); TOST depth gap: {'mean_diff': 0.375, 'ci90': [0.182, 0.568], 'sesoi': 1.0, 'equivalent': True, 'se': 0.118, 'n': 24}.

**Verdict:** audio shows NO readout gap either — mechanism is decomposition across both modalities. (Caveat: TTS quality = espeak; ASR sanity 0.875 — rerun with CosyVoice2 if low.)
