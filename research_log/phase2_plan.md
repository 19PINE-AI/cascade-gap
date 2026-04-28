# Phase-2 Plan: Cascade Gap → Publication-Ready

**Target venues (in order of fit):**
1. COLM 2026 main track (deadline mid-2026)
2. NeurIPS 2026 Foundation Model Eval workshop or D&B track
3. ICLR 2027 main if timing slips

**Target effort:** 2 months, 1-2 people, ~$3-5k API budget, ~6 GPU-weeks.

**Bar to clear:** address the 5 top blockers from the Phase-1 critique (n, single judge, predictor overfit, missing GUI, no significance tests). Preserve the strongest Phase-1 findings (cross-vendor Qwen rescue, alphabet-match ablation, RECITATION filter as methods contribution).

---

## Week-level milestones

### M1 (Weeks 1-2): Methodology hardening — protocol freeze

**Goal:** every Phase-2 number is defensible with statistical testing and judge-bias control.

**Deliverables:**
- [ ] **Second LLM-judge wired in.** Add GPT-5.4 as judge alongside Gemini 3.1 Pro. Score every long-form sample with both judges; report inter-judge agreement (Cohen's κ on per-claim verdicts) and conclusions only where the two judges agree directionally.
- [ ] **Multi-trial judge averaging.** Run each (item, condition, judge) tuple 3 times at temperature 0.0–0.3 and report mean ± SEM. Single-trial pp-level differences are within judge stochasticity; multi-trial shrinks the error bars.
- [ ] **Human-annotated subset.** Two of the authors hand-rate 50 (item × condition) cells using the same atomized-claim rubric. Report per-judge agreement with humans on faithfulness verdicts. This is 2-3 days of work but it's how reviewers will believe the LLM-judge.
- [ ] **Bootstrap CI infrastructure.** Replace point estimates everywhere with bootstrap (n=1000, BCa) CIs on coverage, precision, hallucination rate. Report Δ with 95% CIs and a sign test against zero.
- [ ] **Protocol freeze.** Pre-register the exact prompts, schemas, judge rubric, and per-condition decoding settings as a separate `docs/phase2_protocol.md` file in the repo. After M1 freeze, no prompt edits without re-running affected cells.

**Decision gate:** if inter-judge κ < 0.6 on faithfulness verdicts, redesign the rubric before proceeding (κ < 0.6 means the "hallucination rate" numbers are noise).

---

### M2 (Weeks 3-4): Long-form n-extension

**Goal:** turn n=4 (vendor × paper) cells into n≥150.

**Long-form PDF (target n=30 papers × 5 vendors = 150 cells):**

Paper sourcing strategy to avoid RECITATION confound:
- **15 post-cutoff arXiv papers** (March-June 2026, after Gemini's Feb 2026 cutoff) — already partially seeded with 3 papers.
- **10 non-arXiv technical reports** (industry whitepapers, standards documents, internal-style memos with public licenses). NOT in any model's training data. Sources: NIST publications, IETF RFCs, OpenReview rejected papers (publicly readable, less indexed), PhD thesis chapters.
- **5 private documents** authored for this study (e.g., 20-page made-up technical reports we write, internal-style meeting notes with synthetic content). RECITATION will not fire; serves as ground-truth control.

Vendors:
- Gemini 3.1 Pro Preview, Gemini 3 Flash Preview (2)
- GPT-5.4, GPT-5.4-mini (2 — adds capability axis on the same family)
- Qwen3-VL-30B-Thinking, Qwen3-VL-235B-Thinking (2 — open-weight axis)
- **Phase-2 stretch:** add Claude Opus 4.7 for the document/vision modalities (extends the cross-vendor cell count to 7).

**Long-form audio (target n=10 sources):**

- 5 hour-long YouTube lectures with auto-caption references (Karpathy, MIT OCW, Andrew Ng — already partially set up).
- 3 podcasts with public transcripts (NPR Hidden Brain, 99% Invisible — public, RECITATION-likely; mitigate with paraphrase prompt).
- 2 author-recorded private talks (we record 30-45 min each, transcribe with Whisper-large-v3, score against that reference). RECITATION will not fire on these.

Vendors: Gemini 3.1 Pro, Gemini 3 Flash, Qwen2.5-Omni-7B local, Qwen3-Omni-30B if GPU frees up. GPT-5.4 has no audio so it stays out of this matrix.

**Compute estimate:** 150 PDF cells × 5 calls/cell × ~$0.05/call = $40 (Gemini), comparable on OpenAI/OpenRouter. Audio is more expensive ($100-200 audio tokens cost). Total API budget: $1500-2500.

**Decision gate at end of M2:**
- If the cross-vendor Qwen-rescue effect on Beyond Transcription replicates on ≥7 of 10 papers, the headline finding holds. Proceed to write-up.
- If the effect is paper-specific (replicates on <5 of 10), retitle the paper to *"On the Schema-Match Determinant of the Cascade Gap"* and lead with the music-schema ablation as the cleanest causal evidence.

---

### M3 (Weeks 5-6): Cross-modality (GUI) + side studies

**Goal:** restore the cross-modality unification claim and add the two side studies the Phase-1 plan promised but did not deliver.

**GUI silo (priority 1):**
- WebArena form-filling subset (n=15 tasks).
- OSWorld text-heavy subset (n=15 tasks).
- VisualWebArena standard SaaS subset (n=10 tasks).
- Models: Gemini 3.1 Pro, GPT-5.4 (vision), Qwen3-VL-30B-Thinking, UI-TARS-2-72B-DPO.
- C2 condition uses the pre-registered GUI affordance schema (`harness/schemas/gui_affordance.md`).
- This is the heaviest part of M3 — agent benchmarks are slow and require careful environment setup. Budget 1.5 weeks.

**Reasoning-mode side study:**
- Compare end-to-end-with-thinking vs same-weights cascade on a fixed subset (n=20 from each modality).
- Models with switchable thinking: Gemini 3.1 Pro (thinking_budget control), GPT-5.4 (always thinks), Qwen3-VL-30B-Thinking.
- Test the hypothesis: does internal CoT substitute for an externalized cascade?
- This is a small but reviewer-load-bearing experiment — every reviewer will ask.

**DocVLM replication:**
- Run our same-protocol pilot on a 2024-vintage VLM where DocVLM reported +30 points: InternVL2 at 448×448 on DocVQA.
- Confirms the cascade gap effect generalizes to weaker vintage models, not just the contemporary Qwen3-VL-30B.
- Budget: 1 day. The model is HF-available; we already have the DocVQA pilot.

**Decision gate at end of M3:**
- If the GUI silo shows even a moderate cascade signal (sign(Δ) ≠ 0 on ≥30% of cells), the cross-modality framing is restored.
- If GUI is uniformly null (cascade hurts everywhere), drop the cross-modality framing and tighten to "audio + document + long-form generation."

---

### M4 (Week 7): Analysis & predictor cross-validation

**Goal:** turn the inductive "C0 coverage < 0.7 → cascade wins" rule into a predictive claim a reviewer can falsify.

**Predictor evaluation:**
- Train the single-feature predictor (logistic regression on baseline-coverage) on 2 of 3 modalities (audio + document) and test on the held-out third (chart or GUI).
- Report classification accuracy, ROC-AUC, calibration plot.
- Add 2 secondary features (model parameter count log10, schema-content matching score) and re-fit; report whether they improve held-out accuracy.
- Run a permutation test: shuffle baseline-coverage labels and re-fit 1000 times to compute a null distribution.

**Schema-design methodology section:**
- Promote schema design from "implementation detail" to a methods contribution.
- Formalize: (a) load-bearing-feature identification, (b) observable-proxy enumeration, (c) confidence-per-field annotation, (d) router from input → schema.
- Worked examples: speech-UAS (audio), music-schema (audio), document-layout (vision), GUI-affordance (GUI), chart-structure (chart).
- This is partly already done in the existing `harness/schemas/` files; needs writing up.

**Statistical analysis:**
- Run sign tests on every reported Δ.
- Bonferroni-correct across all (vendor × paper) cells in cross-vendor table.
- Add a meta-analysis-style forest plot showing Δ ± CI for each cell, ordered by baseline coverage.

**Cost-Pareto figure:**
- Promote the "5-20× wall-time" finding to Figure 1 alongside the headline cross-vendor result.
- Plot accuracy gain (Δ) on y-axis vs token cost ratio on x-axis, points colored by model, shape by condition. This is the figure practitioners will screenshot.

---

### M5 (Week 8): Writing & submission prep

**Goal:** publication-ready manuscript.

**Title and framing:**
- Drop "When and Why" framing in favor of the strongest empirical claim. Candidates:
  - *"Baseline Coverage Predicts the Self-Cascade Gap: A Cross-Vendor Study"* — leads with the predictor.
  - *"Same-Weights Cascades Rescue Hallucinatory Multimodal Models"* — leads with the Qwen rescue.
  - *"On the Alphabet-Match Determinant of the Cascade Gap"* — leads with the schema ablation.
- Decide based on M2/M3 results: whichever finding holds strongest in n-extension is the title.

**Manuscript revision:**
- Move compute-Pareto + RECITATION filter findings into the abstract (currently buried).
- Add Figure 1 (Pareto), Figure 2 (heatmap of Δ across vendor × benchmark), Figure 3 (alphabet-richness sweep on a fixed task), Figure 4 (predictor calibration plot).
- Replace single-trial point estimates with mean ± CI throughout.
- Add a `protocol.md` appendix with all prompts and decoding parameters verbatim.
- Anonymize for submission.

**Submission targets:**
- COLM 2026 if deadline aligns (typically June-July).
- NeurIPS 2026 D&B track for the benchmark contribution (deadline May).
- NeurIPS 2026 Foundation Model Eval workshop for the methodology piece.
- Workshop fallback: ICLR R2-FM if main-track deadlines are missed.

**Camera-ready prep:**
- Release prompts, schemas, per-call logs, judge transcripts under MIT/CC-BY.
- Release a small Python harness that reproduces the headline cross-vendor table from a fresh checkout.

---

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Cross-vendor Qwen rescue doesn't replicate at n>5 | Medium | Decision gate at M2; pivot title to schema-ablation as headline |
| Inter-judge κ < 0.6 → faithfulness numbers are noise | Medium-High | Redesign rubric in M1; if κ stays low, drop "hallucination" framing and use ROUGE/BERTScore as fallback metrics |
| GUI silo shows null effect → cross-modality framing dies | Medium | Document and present as a boundary condition rather than a contradiction |
| Private long-form content can't be sourced cleanly | Medium | Author-record talks ourselves; use academic theses (PhD chapters are public but less indexed) |
| Vendor APIs change mid-study (Gemini 3.2 release etc.) | Medium-High | Version-pin all calls; record snapshot date per cell; budget for a re-run if a Tier-1 model deprecates |
| Compute-Pareto numbers shift with thinking-budget changes | Medium | Re-run reasoning-mode side study at end of M3 with current vendor settings |
| Reviewer says "cross-modality is asserted, not measured" | High → Low after M3 | GUI silo addition addresses this directly |
| Reviewer says "this is just a benchmark, not a paper" | Medium | The predictor + alphabet-match ablation are the framework contributions; emphasize them |
| RECITATION filter changes mid-study (Google updates policy) | Low | Document as a methods finding regardless |

---

## What to cut if behind schedule

If M1 + M2 take longer than 4 weeks:
- **First cut:** DocVLM replication (1-day item; nice-to-have, not load-bearing).
- **Second cut:** drop GPT-5.4-mini and Qwen3-VL-235B from the headline matrix; keep only the contrasting endpoints (GPT-5.4 vs Gemini 3.1 Pro vs Qwen3-VL-30B).
- **Third cut:** drop GUI silo and reframe as "two-modality study"; submit to a workshop instead of main track.
- **Last resort:** keep only the cross-vendor Qwen rescue + RECITATION filter findings; submit as a methods short paper to a workshop.

What never gets cut:
- Two-judge cross-validation (top blocker #2).
- Bootstrap CIs (top blocker #5).
- The schema-match ablation (the cleanest causal experiment we have).

---

## Estimated budget

| Item | Estimate |
|---|---|
| API calls (Gemini Pro + Flash + GPT-5.4/-mini + OpenRouter) | $2000-3500 |
| GPU-weeks for open-weight pilots (Qwen2.5-Omni, Qwen3-Omni, Step-Audio if accessible) | $300-500 (rented H100) |
| Author-recorded private content production | $0 (in-house) |
| Human annotation (50 cells × 30 min) | 2-3 author-days |
| **Total cash budget** | **~$2.5-4k** |

---

## Single-line success criterion

**At the end of M5, we should be able to make this claim with statistical backing:**

*"Across N=30+ long-form documents and 5 multimodal models, the same-weights self-cascade improves precision over end-to-end on weak-model cells (parameter count < 50B, baseline C0 precision < 0.8) by Δ_prec = 0.X ± 0.0Y (p < 0.001), and the sign of Δ is predicted out-of-sample by baseline C0 coverage with held-out classification accuracy AUC > 0.85."*

If we can defend that sentence with data, we have a paper.

---

## Followups beyond Phase-2

Out of scope for the 2-month plan but worth flagging:

- **Public benchmark contribution.** Release the curated long-form mix (post-cutoff arXiv + private content + audio) as a held-out cascade-gap benchmark. NeurIPS D&B track is the natural venue.
- **Schema-router as a deployable system.** The Pass-0 classifier + per-task-class schema selector is itself a publishable artifact for the practical-prescription claim.
- **Audio-only deep-dive.** If the cross-vendor flip replicates on audio (need GPT-audio access or open omni model that works long-form), there's a focused audio paper hiding in the data.
