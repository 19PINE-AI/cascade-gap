# Diagnostic: Why does cascade NOT improve coverage on the NASA scanned paper?

**Run:** `runs/paper-review-19720009221-1777458461/`
**Paper:** NASA Tech Memo 1972, "Wagging Tail Vibration Absorber" (9 pages, scanned, vibration analysis content)

## Headline numbers (Phase-3 protocol)

| | C0 (multimodal end-to-end) | C1 (cascade) | Δ |
|---|---:|---:|---:|
| Hallucinations (unsupported) | 3 | 1 | **−67%** |
| Probe coverage | 39 / 49 = 0.796 | 38 / 49 = 0.776 | **−2.0 pp** |
| Final score (zero-tolerance) | 0 | 0 | — |

## Probe-by-probe diff

| Bucket | n |
|---|---:|
| Both covered | 37 |
| C0 only | 2 |
| C1 only | 1 |
| Neither | 9 |

**Probes ONLY C0 covered (cascade lost):**
- `p038`: Appendix-1 second boom-mode frequency = 1.0074 × 10⁻³ Hz
- `p039`: Appendix-1 third boom-mode frequency = 3.1169 × 10⁻³ Hz

**Probes ONLY C1 covered (cascade gained):**
- `p018`: vertical hinge force formula `V_½ = -m_T(Ẅ_T + Ẅ₁)/2`

**Probes neither covered (9):**
Most are Appendix-1 equations/constants (`I_1T = ρl³/3`, `K_T = 1.390 × 10⁻⁴`, `C_c = 0.249`, `C/C_c = 0.175/n`) and experimental procedure details.

## Where each value lives along the pipeline

We searched for specific numerical/equation strings across the 4 saved artifacts (Flash reference OCR, Pro C1 Pass-1 OCR, C0 review, C1 review):

| Value | Flash ref | Pro Pass-1 | C0 review | C1 review |
|---|:--:|:--:|:--:|:--:|
| 1.0074 (boom-mode freq) | ✓ | ✓ | ✓ | **✗** |
| 3.1169 (boom-mode freq) | ✓ | ✓ | ✓ | **✗** |
| 1.390 (hinge spring const) | **✗** | **✓** | ✗ | ✗ |
| `I_1T` (inertia symbol) | **✗** | **✓** | ✗ | ✗ |
| `ρl³` formula | **✗** | **✓** | ✗ | ✗ |
| 0.249 (critical damping) | ✗ | ✗ | ✗ | ✗ |
| 0.175 (decay relation) | ✗ | ✗ | ✗ | ✗ |

**Three observations:**

1. **Pro's OCR (Pass-1) is BETTER than Flash's OCR (reference)** on equations and physical constants. Three values that exist in the actual paper made it into Pro's transcript but not Flash's reference.

2. **The reference is incomplete** — at least 2 numerical values (0.249, 0.175) are absent from BOTH Flash and Pro transcripts. Likely they are in figures/tables that both vision models fail on; or the scanned PDF has them with degraded image quality.

3. **C1 lost 1.0074 and 3.1169 between Pass-1 and Pass-2.** Both values were correctly transcribed by Pro, then the Pass-2 reviewer (working from the 3,530-word transcript) chose not to include them in the 1,314-word review. **The bottleneck is summarization length, not perception.**

## What the hallucinations actually are

C0's 3 unsupported claims are all rhetorical strengthening of hedged statements:
1. "highly promising" ← original: "seems to be promising"
2. "tougher conditions" ← original: "may be a little bit tougher"
3. "two primary sources" ← original: doesn't say "two" or "primary"

C1's 1 unsupported claim is a sign-attribution slip on a force equation.

These are **stylistic embellishments**, not invented facts.

## Why the cascade doesn't improve coverage on this paper

Two distinct cascade mechanisms:

1. **Perception-bottleneck rescue.** When the source is too long for end-to-end attention to hold equally (e.g., 42-min Karpathy talk, 8,400 words → 1,600-word review = 5× compression), the model's end-to-end summarization drops most facts because it can't attend to all source content. Cascade Pass-1 preserves all perceived content as text; Pass-2 then summarizes from that durable intermediate. **Result on Karpathy: +33pp coverage, +77% hallucination reduction.**

2. **Stylistic anchor.** When Pass-2 reads literal text instead of the original modality, it has less freedom to embellish; it's anchored to the actual words. This works regardless of source length.

A 9-page paper hits mechanism #2 (cascade reduces hallucinations 67%) but not #1 — perception isn't the bottleneck because the model can attend to all 9 pages comfortably end-to-end. Both reviews are the same length (~1,300 words), and both fill that budget with the same content type (thesis + main results + methodology) and drop the same content type (equations + appendix details). The cascade Pass-2 has the equations available in its input but chooses prose-over-formula at summarization time.

## What this implies for protocol design

To extract a coverage benefit from cascade on scanned papers, one of the following is needed:

1. **Longer scanned papers** (50+ pages) where end-to-end perception genuinely cannot hold all content.
2. **A summarization prompt that demands equation/numeric preservation** — currently the prompt asks for "every quantitative claim" but Pass-2 still defaults to prose. Could try "produce a structured technical summary preserving every equation and named quantity with original symbol notation."
3. **Cascade with longer Pass-2 budget**. Pass-2 was constrained to 500-800 words by prompt; extending to a multi-section structured review would let Pass-2 surface equations.

## Implication for the reference itself

The reference (Gemini 3 Flash OCR) is itself imperfect. For Phase-3 we should consider:
- Using Pro for the reference (if cost allows) — would catch more equations
- Or augmenting the reference: union of Flash OCR + pdftotext where available
- Or running 2-3 Flash trials and union-ing them

Without a more complete reference, the probe coverage scores are biased toward the OCR's strength rather than the model's.

## What changes for the Phase-3 protocol

For now:
- **Karpathy result is real** — the +33 pp coverage gain is large enough to survive any reference-imperfection adjustment, and the 13→3 hallucination drop is the headline.
- **NASA paper result is interpretable** — the apparent "no coverage win" is partly a summarization-budget issue, partly a reference-imperfection issue.
- **Mechanism story is sharper**: cascade has two distinct benefits (perception rescue, stylistic anchor), and we now have evidence for both.

Phase-3 should add at least one **long scanned paper** (50+ pages) to test the perception-bottleneck mechanism on the image modality. NASA NTRS has plenty.
