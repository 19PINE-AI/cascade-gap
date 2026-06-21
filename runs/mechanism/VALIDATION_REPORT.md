# Mechanism validation report (V1/V2/V3)
_generated: 2026-06-21T10:21:52Z (autonomous overnight run)_

## V2 — multi-seed conditions on all 21 cells (powered)
Mean seeds/cell: C1=5.0, E1=4.95, E2=4.67. n_cells=21.

**E2 (single-call) vs C1 — coverage:** mean Δ=-0.1106 (bootstrap 95% CI [-0.1704, -0.0376]); E2 worse on 17/20 cells; Wilcoxon p=0.01923. 
Single-call emitted **no review** in 7 runs across cells ['3b1b', 'harvard', 'nat_vib'] (output budget exhausted).

**E1 (C1+ both) vs C1 — coverage:** mean Δ=0.0693 (CI [-0.0014, 0.1537]); TOST equivalence (SESOI 0.04): False (90% CI [-0.0024, 0.141]). 
**Hallucinations E1 vs C1:** mean Δ=0.5833 (E1 more on 14/21; note: 'better' here = higher count). 

Synthesis (seed) variance, mean within-cell SD of coverage: C1=0.0634, E1=0.0538, E2=0.0807.

Mixed-effects coverage ~ cond + (1|cell): {'Intercept': 0.7134, "C(cond, Treatment('C1'))[T.E1]": 0.0697, "C(cond, Treatment('C1'))[T.E2]": -0.1105, 'Group Var': 2.5017, 'pvalues': {'Intercept': 0.0, "C(cond, Treatment('C1'))[T.E1]": 1e-05, "C(cond, Treatment('C1'))[T.E2]": 0.0, 'Group Var': 0.00233}}

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

## V1/E7 — audio substrate logit-lens (Qwen2.5-Omni), three TTS engines
| TTS | ASR-intellig. | text_acc | audio_acc | depth-gap CI90 | TOST-equiv |
|---|---|---|---|---|---|
| espeak | 0.708 | 0.958 | 0.833 | [0.64, 1.777] | False |
| mms-tts | 0.875 | 0.958 | 1 | [0.182, 0.568] | True |
| fish-speech-1.5 | 0.958 | 0.958 | 1 | [0.209, 0.541] | True |

**Verdict:** the apparent audio substrate gap is a TTS-intelligibility artifact: it vanishes (TOST-equivalent) with two independent clean voices (mms-tts, fish-speech). Audio behaves like documents (E6) — the cascade win is decomposition, not substrate, in both modalities.
