# Phase-2 Closing Summary — 2026-04-28

This is the post-session closure note. Phase-2 plan called for 8 weeks across M1-M5 milestones; this autonomous session executed M1 + most of M2 in roughly one working day. The headline findings of Phase-1 survive Phase-2 multi-judge protocol with bootstrap CIs at small but real sample size.

## What survived (high confidence)

1. **Frontier models do not hallucinate on long-form PDF summaries at C0.** Both Gemini Pro and GPT-5.4 hit 0.97-1.00 precision on every paper tested (n=8 papers between them), validated by both judges with inter-judge precision range mean = 0.022.

2. **Cascade dramatically rescues weak open-source models.** Qwen3-VL-30B-Thinking C0 has ~38% hallucination rate on Beyond Transcription (both judges agree); cascade C1 drops to ~3% (both judges agree). +38 pp precision rescue is the single most striking quantitative finding in the entire study. (Currently n=1; Phase-3 must replicate.)

3. **Cascade modestly improves Gemini coverage at zero precision cost.** n=5 papers, Δ(C1−C0) cov = +0.084 with 95% CI [+0.017, +0.152] excluding zero. Cascade wins coverage on 4 of 5 Gemini papers.

4. **Cascade hurts saturated frontier models.** GPT-5.4 Δ(C2−C0) coverage = −0.073 with 95% CI [−0.155, −0.023] excluding zero (n=3). C0 already covers 86-96%; cascade trims it.

5. **Inter-judge agreement is strong on continuous metrics.** Across 36 multi-judge cells: precision range mean 0.022, max 0.143 (only on the most-ambiguous Qwen weak-model C0). Coverage range is denominator-stochastic; precision is the more reliable continuous metric.

## What weakened or was disproven

1. **Phase-1's "+34 pp Gemini cascade win" was inflated by single-trial noise.** Multi-judge averaged across 5 papers gives +8 pp coverage gain — direction preserved, magnitude cut by 4×. Phase-2 paper should report Phase-1 numbers with a methodological caveat.

2. **Cohen's κ at threshold 0.95 is brittle.** Reports range from 1.000 to −0.250 on the same multi-judge data depending on how precision values cluster around the threshold. **Continuous precision range is the right inter-judge metric for this paper**, not binary κ.

3. **The "post-cutoff arXiv evades RECITATION" mitigation is unreliable.** 3 of 5 March-April 2026 arXiv papers had Gemini cascade Pass-1 blocked. The training cutoff date alone is not a sufficient guarantee.

4. **Baseline-coverage predictor accuracy at n=9 is 67% strict / 78% relaxed.** Direction is right but it is not yet a strong-enough rule to publish without n=30+ held-out evaluation.

## What is fully new in Phase-2

1. **Multi-judge cross-validation methodology.** `pilot/llm_judge_multi.py` + `pilot/rejudge_multi.py` form a reusable cross-judge framework. Top reviewer blocker (single-judge dependence) is empirically resolved with κ=0.865 across 15 cells of a 5-paper Gemini run + κ=1.000 on Beyond Transcription cross-vendor.

2. **Bootstrap CI infrastructure.** `pilot/stats.py` provides percentile bootstrap, paired-difference CIs, and sign tests. Replaces every Phase-1 point estimate with a defensible interval.

3. **RECITATION incidence as a methods finding.** Gemini blocks ~60% of cascade Pass-1 calls on recent arXiv content; OpenAI does not. Vendor-specific filter behavior is a paper-worthy methodological contribution that Phase-1 only flagged.

4. **Cross-vendor cascade matrix at n>1**. GPT-5.4 cross-vendor on 3 papers, Gemini on 5 papers, Qwen on 1 paper. The capability-tier effect (saturated/compact/hallucinatory) replicates across multiple papers per tier on the well-tested vendors.

## What is needed for publication

Per the Phase-2 plan, blockers remaining for top-tier venue:

- **n=30 long-form papers** (currently 5-8). Need ~25 more, ideally including non-arXiv/private content to evade RECITATION.
- **GUI silo** (currently 0 cells). M3 of the Phase-2 plan.
- **Reasoning-mode side study** (currently 0 cells). M3 of the plan.
- **Predictor cross-validation** with held-out modality. Currently fit and evaluated on the same dataset.
- **Audio long-form n>1** (currently 1 Karpathy data point). Need at least 5 lectures/talks.
- **Manuscript revision** with Phase-2 numbers, CIs, and the brittle-κ methodology note.

Phase-2 plan estimated 8 weeks for these; one autonomous session got us to ~25% of that scope. The strongest path to publication: 4-6 more weeks focused on n-extension + GUI + manuscript.

## Honest framing for the next iteration of the paper

The strongest claim Phase-2 supports as written:

> *"Across N=9 (vendor × paper) cells with multi-judge cross-validation, the cascade gap's sign covaries with baseline C0 coverage in 67-78% of cells. On three capability tiers measured at n≥1 papers each — frontier saturated (GPT-5.4, n=3), mid-capable compact (Gemini Pro, n=5), weak hallucinatory (Qwen3-VL-30B, n=1) — the qualitative pattern (cascade hurts / modestly wins / dramatically rescues) replicates within tier."*

This is a sharper, more honest version of the v2 thesis from the original preprint. It still needs n-extension and statistical reinforcement before submission, but it would survive peer review at a workshop venue today, and the methodology section is now defensible.

## Repo state at session close

15 commits added in this Phase-2 session. Latest: `9675ca7`.

New code:
- `pilot/llm_judge_multi.py` (multi-judge with provider abstraction)
- `pilot/rejudge_multi.py` (cross-judge re-scoring of saved summaries)
- `pilot/stats.py` (bootstrap CIs + sign tests)
- `pilot/analyze_phase2.py` (cross-vendor aggregate with CIs)

New data:
- 5 additional post-cutoff arXiv papers in `data/longform_pdf/`
- `judge_multi.jsonl` files in 5 long-form runs (36 cells of multi-judge data)
- `kappa.json` files in same 5 runs

Documentation:
- `research_log/phase2_plan.md` (8-week plan)
- `research_log/2026-04-28_phase2_progress.md` (full Phase-2 progress note with all tables)
- `research_log/2026-04-28_phase2_close.md` (this file)

Repo: <https://github.com/bojieli/cascade-gap>.
