# Reorganization plan: from lab notes to a NeurIPS submission

Target: NeurIPS-style ~9-page body + references + appendices. Design rules adopted
throughout: (1) **no dense number runs in prose** — every quantitative claim points at a
figure or table; body text keeps only the one or two stats that carry the sentence;
(2) **at least one figure per body page**; (3) narrative arc = *observation → mechanism →
solution*, with one real running example threaded through all three acts.

---

## 1. Diagnosis of the current draft

- The body has only **2 figures in ~8 pages** (protocol schematic, inverse-correlation
  scatter); Sections 3–7 are wall-to-wall statistics. Fourteen figures/tables sit in the
  appendix while the body paragraphs re-narrate their numbers — the worst of both.
- The current order (Protocol → Main result → Mechanism → Failure modes → Iter →
  Robustness) presents the solution *first* and the question *last*. The reader meets
  C0/C1 notation and 21-cell statistics before ever seeing what a failure looks like.
- Figure 1 is an architecture schematic, which sells method, not results.
- The abstract is itself number-dense (seven statistics in one paragraph).

## 2. New narrative arc (three acts)

**Act I — Observation.** End-to-end multimodal review *satisfices*: the model drops ~1/3
of the content it demonstrably perceived and embellishes the rest. Shown on one real
cell, with verbatim artifacts.

**Act II — Mechanism.** Nine experiments adjudicate three hypotheses. Not perception
(E3), not substrate (E6–E9), but **generation under load** (E2/E1). The mechanism
*predicts* the fix.

**Act III — Solution.** Perceive–externalize–synthesize: two same-weights passes with
independent output budgets. 21-cell headline results, inverse-baseline law, cross-model
generality, the two predicted failure modes, and the quote-grounded fix.

### Running example (recommended): **Karpathy "State of GPT" (42-min audio)**

- Recognizable to the NeurIPS audience; artifacts on disk
  (`runs/audio-review-karpathy_sogpt-*/judge_halluc_C0.json`, probe files) contain
  verbatim, quotable failures: C0 emits 13 unsupported claims (e.g. *"a typical
  vocabulary size is around 10,000 tokens"* where the talk says *"a couple ten thousand
  tokens"*; RLHF misdescribed as a fourth serial stage) and covers only 32/51 probes,
  while the model's **own transcript contains 100% of the dropped probes**. C1: 3
  hallucinations, 49/51 probes.
- Alternative if we prefer raw magnitude over recognizability: MIT 6.034 (17h→4h,
  0.77→0.98) or Harvard Moot Court (largest coverage gain, +50pp). Karpathy's
  pre-cutoff date is already handled by the memorization-is-conservative argument in
  Limitations; keep that sentence.
- The example recurs at each act: Act I (what C0 dropped/invented), Act II (the dropped
  fact sits verbatim in the model's own Pass-1 transcript; single-call collapse on this
  cell), Act III (C1 numbers, and the cell's position on the inverse-baseline line).

## 3. Proposed section structure

| # | Section (new) | Content pulled from (old) | Page budget |
|---|---|---|---|
| 1 | **Introduction** | §1, reframed around the three acts | 1.5 |
| 2 | **The observation: end-to-end review satisfices** — running example + task/scoring protocol (compact) + the perception surprise (E3) | §2 Protocol, §3 ¶"structural caveat" (footnote), old E3 from §4 | 1.5 |
| 3 | **Mechanism: why one pass fails** — H1/H2/H3; substrate null E6–E9; single-call collapse E2; modality re-attachment E1; verdict | §4, appendix A substance (details stay in appendix) | 2 |
| 4 | **The solution: perceive–externalize–synthesize** — C0/C1 defined via schematic; 21-cell headline; inverse-baseline law; cross-model generality (Claude-within, 2.5 Flash, mixed pipelines, 3-vendor Thermal) | §2 notation, §3 Main result, appendix D/E/F | 2 |
| 5 | **Where it breaks: two failure modes, and fixes** — Mode A/B + triggers; chunked Pass-2; C1iter verdict; retractions stated once | §5, §6, appendix G/H | 1.5 |
| 6 | **Robustness** — one composite figure + ≤0.5 page prose (inter-judge, probe circularity, reference bias, multi-seed, LOOCV predictor) | §7, appendices I/J/K | 0.5–0.75 |
| 7 | **Related work** | §9, trimmed ~30% (Step-Audio-R1 paragraph halved; it repeats itself) | 0.75 |
| 8 | **Discussion, limitations, conclusion** — inverse-baseline law as the portable claim; validation plan compressed to one paragraph | §8, §10 | 0.75 |

Everything currently in appendices stays available there; the change is that each body
section *shows* its evidence in a figure and delegates raw counts to appendix tables,
instead of narrating the counts inline.

## 4. Figure plan (≥1 per page; ★ = new, ◆ = promoted from appendix, ● = existing body)

| Fig | Page | Content | Source of data |
|---|---|---|---|
| **1 ★ Headline results showcase** | 1 | NOT the schematic. Multi-panel results poster: (a) paired slope/dumbbell chart, C0→C1 coverage per cell (21 cells, audio vs paper color-coded); (b) same for hallucinations; (c) small cross-model strip — Gemini Pro, Gemini 2.5 Flash, Claude-within, mixed gpt-audio→{Claude, GPT-5.4, Gemini} — each as a tiny win/flat/loss summary. One glance = "decomposition wins broadly, across models." | `tab:all_cells`, `tab:claude_within`, `tab:flash_audio`, `tab:mixed` (all in phase3_data.json / pilot aggregates) |
| **2 ★ Running example panel** | 2 | Typeset quote-tree (LaTeX tcolorbox, not matplotlib): source quote → C0 review's hallucinated version (real, verbatim) + a dropped probe → the same fact verbatim in the model's own Pass-1 transcript → C1 review sentence. Annotated with the cell's counts. | `runs/audio-review-karpathy_sogpt-*/judge_halluc_C0.json`, probe + transcript files |
| **3 ◆ E3 perception bars** | 3 | Existing `fig_mech_e3` (transcript ≈1.0 vs C0 0.65 vs C1 0.77 per cell) promoted to body; add the 361/362 callout as an annotation on the figure, not in prose. | exists |
| **4 ★ Substrate-null composite (E6–E9)** | 4 | 3 panels: (a) E6 load-sweep curves (from `fig_mech_e6load`); (b) E8 frontier retrieval accuracy text vs legible-image vs degraded across K (currently a table — becomes grouped bars/lines); (c) E9 reasoning: Claude text 0.825 vs image 1.00 with CI (currently a table). Tables tab:e7–tab:e9 move to appendix. | tab:e8/tab:e9 data in pilot/mech artifacts |
| **5 ★ E2 single-call collapse + E1** | 4–5 | Dot plot per cell: coverage under C1 vs single-call vs C1+ (from `tab:mech_cond` + the n=5 aggregate); "no review emitted" cells shown as ✗ markers at zero. Replaces the in-prose −0.111/CI recitation. | tab:mech_cond, mech aggregates |
| **6 ●+◆ Protocol schematic + inverse-baseline law** | 5–6 | Old Fig 0 (schematic) relocated here, paired side-by-side with existing `fig1_inverse_correlation`; annotate the running-example cell on the scatter. | exists |
| **7 ★ Cross-model generality grid** | 6–7 | 2×2: (a) Thermal 66pp three-vendor bars (`fig2_xvendor_thermal`, exists); (b) Claude-within ΔH per paper (dumbbells, from tab:claude_within); (c) 2.5 Flash audio Δcov vs C0 baseline (headroom-gating made visual, from tab:flash_audio); (d) mixed-model pipelines vs Gemini C0 (from tab:mixed). Tables move to appendix. | exists + tables |
| **8 ◆+◆ Failure modes + iter Pareto** | 7–8 | (a) `fig4_failure_modes` (Mode A/B on Heat Pipes) promoted; (b) `fig11_iter_pareto` promoted. Mode-A/B trigger thresholds become a 3-row mini-table beside them. | exist |
| **9 ★ Robustness composite** | 8–9 | 4 small panels from existing appendix figures: inter-judge scatter (`fig10`), probe-circularity (`fig8`), reference-bias (`fig9`), multi-seed envelopes (`fig12`). Full-size versions stay in appendix. | exist |

New matplotlib work: Figs 1, 4(b,c), 5, 7(b,c,d), 9 (composite assembly) — all buildable
from `paper/figures/phase3_data.json`, `make_figures.py`, and the pilot aggregate JSONs;
no new experiments needed. Fig 2 is LaTeX-only.

## 5. Number-to-figure migration rules

- Body prose retains at most: the headline sign-test pair (18/21, 16/21), r = −0.45, and
  the 99.7% E3 number — each stated once, next to its figure. Everything else
  (CIs, per-cell counts, seeds, medians, judge ranges) lives in figure annotations,
  captions, or appendix tables.
- Captions do the quantitative storytelling (current captions are already good at this —
  keep the style).
- The abstract is rewritten to ≤3 numbers (18/21, r = −0.45, 99.7%).
- Retractions (citation-strip, Megagauss chunked) are kept — they are a credibility asset
  — but consolidated into one place (§5 + Robustness), stated once each instead of
  re-litigated in three sections.

## 6. What does NOT change

- No new experiments, no new claims, no reframing of the mechanism (the win is
  decomposition / generation-under-load — per project memory, do not reintroduce
  substrate language as an explanation).
- All caveats survive: shared-reference threat, single-vendor headline, judge variance,
  headroom-gated cross-vendor picture. They move to where the reader needs them
  (a caveat box/footnote near Fig 1; Limitations).
- Appendices keep every raw table; body figures cite them.

## 7. Execution order

1. Build new figures (Fig 1 showcase first — it anchors page 1).
2. Restructure `main.tex` per §3 (keep a `main.tex.bak.pre-reorg` snapshot).
3. Rewrite Intro/abstract around the three acts + running example.
4. Migrate numbers out of prose section by section; move demoted tables to appendix.
5. Length pass to 9 pages; check ≥1 figure per page in the compiled PDF.
