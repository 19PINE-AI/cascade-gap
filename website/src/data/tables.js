// Paper-level constants, mirrored from paper/main.tex (aggregates, appendix
// tables). Per-cell numbers live in paperData.json, extracted from runs/.

export const AGG = {
  cells: 21,
  covWins: 16,
  covP: 0.027,
  hallucWins: 18,
  hallucP: 0.0015,
  meanDCov: +0.118,
  meanDCovCI: [+0.048, +0.189],
  meanDH: -3.86,
  meanDHCI: [-5.62, -2.33],
  c0MeanCov: 0.65,
  pearsonR: -0.45,
  pearsonCI: [-0.73, -0.10],
  perceived: { pct: 99.7, num: 361, den: 362, ci: [98.5, 99.9] },
}

// E2/E1 condition grid (Appendix tab:mech_cond) — single-seed, 8 cells.
// h = unsupported claims, cov = probe coverage; null = no review emitted (budget exhausted).
export const E2_GRID = [
  { cell: 'MIT 6.034 (audio)', c0: [17, 0.77], c1: [4, 0.98], c1plus: null, single: 'budget', native: null },
  { cell: '3B1B Attention (audio)', c0: [11, 0.88], c1: [0, 0.96], c1plus: [5, 1.0], single: [1, 0.8], native: null },
  { cell: 'Wagging Tail 9pp', c0: [3, 0.8], c1: [1, 0.78], c1plus: [2, 0.78], single: [5, 0.63], native: null },
  { cell: 'Natural Vibration 42pp', c0: [4, 0.66], c1: [5, 0.49], c1plus: [9, 0.79], single: 'budget', native: null },
  { cell: 'Thermal 66pp', c0: [5, 0.68], c1: [2, 0.84], c1plus: [1, 0.68], single: [3, 0.4], native: null },
  { cell: 'Heat Pipes 104pp', c0: [14, 0.72], c1: [11, 0.78], c1plus: [10, 0.66], single: 'budget', native: null },
  { cell: 'arXiv Fairness 53pp', c0: [14, 0.5], c1: [15, 0.4], c1plus: [11, 0.38], single: [11, 0.24], native: [13, 0.34] },
  { cell: 'arXiv Perovskite 80pp', c0: [2, 0.9], c1: [3, 0.74], c1plus: [5, 0.8], single: [5, 0.8], native: [4, 0.8] },
]

export const E2_MULTISEED = {
  singleDCov: -0.111, singleCI: [-0.17, -0.038], singleNoReview: 7,
  c1plusDCov: +0.069, c1plusCI: [-0.001, +0.154], c1plusHallucCells: 14,
}

// E8 behavioral retrieval probe (frontier models), pooled over K ≤ 48.
export const E8 = [
  { model: 'Gemini 3.1 Pro', text: 1.0, image: 1.0, degraded: 0.2, gap: '+0.000' },
  { model: 'Claude Opus 4.7', text: 1.0, image: 1.0, degraded: 0.2, gap: '+0.000' },
]
// E9 multi-hop reasoning probe (sum 6 packed facts).
export const E9 = [
  { model: 'Gemini 3.1 Pro', text: 1.0, image: 0.99, degraded: 0.01, note: 'both at ceiling — equivalent' },
  { model: 'Claude Opus 4.7', text: 0.825, image: 1.0, degraded: 0.0, note: 'image reliably BETTER (+0.175, CI [0.10, 0.26])' },
]

// E7 audio substrate (Qwen2.5-Omni Thinker, 24 novel facts).
export const E7 = [
  { tts: 'espeak (robotic)', intel: 0.71, text: 0.96, audio: 0.83, equiv: false },
  { tts: 'mms-tts (clean)', intel: 0.88, text: 0.96, audio: 1.0, equiv: true },
  { tts: 'fish-speech (natural)', intel: 0.96, text: 0.96, audio: 1.0, equiv: true },
]

// Within-Claude comparison, six NASA papers (Appendix tab:claude_within).
export const CLAUDE_WITHIN = [
  { cell: 'Wagging Tail', len: '9 pp', c0: [5, 0.959], c1: [2, 0.98] },
  { cell: 'Env Test', len: '18 pp', c0: [3, 1.0], c1: [2, 1.0] },
  { cell: 'Dynamic Response', len: '41 pp', c0: [2, 1.0], c1: [1, 0.96] },
  { cell: 'Natural Vibration', len: '42 pp', c0: [5, 0.915], c1: [4, 0.851] },
  { cell: 'Thermal Analysis', len: '66 pp', c0: [11, 0.92], c1: [4, 1.0] },
  { cell: 'Heat Pipes', len: '104 pp', c0: [4, 0.9], c1: [20, 0.9], modeB: true },
]

// Gemini 2.5 Flash audio arm (Appendix tab:flash_audio).
export const FLASH_AUDIO = [
  { cell: '3B1B Attention', min: 26, c0: [5, 0.9], c1: [1, 0.92] },
  { cell: 'NeurIPS panel', min: 31, c0: [5, 0.98], c1: [6, 0.959] },
  { cell: 'Karpathy', min: 42, c0: [3, 0.922], c1: [9, 0.902] },
  { cell: 'MIT 6.034', min: 47, c0: [7, 0.833], c1: [4, 0.958] },
  { cell: 'Harvard Moot', min: 82, c0: [19, 0.6], c1: [12, 0.62] },
]

// Mixed-model pipelines vs native C0 (Appendix tab:mixed). Real per-run JSON
// also in paperData.mixed; this is the display ordering + native baseline.
export const MIXED = [
  { cell: '3B1B Attention', dir: 'audio-review-3b1b_attention-1778857367', nativeC0: [11, 0.88] },
  { cell: 'Karpathy', dir: 'audio-review-karpathy_sogpt-1777458038', nativeC0: [13, 0.63] },
  { cell: 'MIT 6.034', dir: 'audio-review-mit_6034_winston-1778857365', nativeC0: [17, 0.77] },
]

export const ROBUSTNESS = [
  {
    title: 'A second judge re-scores everything',
    stat: '19/21',
    body: 'Claude Opus 4.7 re-scored all 21 cells with the same prompts: the coverage direction agrees on 19/21 cells and per-probe agreement has median 0.94. Claude counts fewer fabrications overall (about 0.71× as many), but the conclusions hold under both judges.',
  },
  {
    title: 'Re-rolling the dice (5 seeds)',
    stat: 'n = 5',
    body: 'Pass-2 was re-run five times on the headline cells. The three wins keep their direction; the one apparent loss (Perovskite, −16pp) shrinks to −6pp — inside measurement noise.',
  },
  {
    title: 'New probes, same answer',
    stat: '6/7',
    body: 'A different model (Claude) re-extracted the fact checklists on seven cells spanning wins and losses. The cascade direction is preserved on 6/7 (the exception is a within-noise cell).',
  },
  {
    title: 'Independent transcribers',
    stat: '4/4',
    body: 'The reference was regenerated with completely independent tools (Whisper for audio, EasyOCR for scans). The coverage direction is preserved on all four cells tested — the result is not an artifact of grading against the model’s own kind of transcript.',
  },
]

export const CHECKLIST = [
  { source: 'Audio talk, lecture, or a moderate paper (40–70 pages)', diagnosis: 'Decomposition wins on both axes.', action: 'Use two passes (C₁) by default.' },
  { source: 'Moderate paper full of citations (e.g. Natural Vibration 42pp)', diagnosis: 'The model pads references from memory (Mode B).', action: 'Two passes + quote-grounded rewrite (C₁-iter).' },
  { source: 'Very long paper, notes ≫ writing budget (Heat Pipes 104pp)', diagnosis: 'The review can’t fit the notes (Mode A).', action: 'Split the transcript into chunks, review each (C₁c).' },
  { source: 'Long, citation-dense survey (SP-5100 176pp, Fairness AI)', diagnosis: 'Both failure modes compound.', action: 'Prefer one pass (C₀) if the source fits; otherwise chunked Pass-2 with multi-seed averaging.' },
  { source: 'Model already reviews this source well end-to-end', diagnosis: 'No headroom — nothing to recover.', action: 'Keep one pass (C₀). Decomposition buys nothing here.' },
]

export const LINKS = {
  code: 'https://github.com/19PINE-AI/cascade-gap',
  site: 'https://01.me/research/cascade-gap',
}

export const BIBTEX = `@article{li2026perceive,
  title   = {Perceive, Externalize, Synthesize: Why Two-Pass Decomposition
             Beats End-to-End on Long-Form Multimodal Review},
  author  = {Li, Bojie and Shi, Noah},
  year    = {2026},
  note    = {Preprint. Code and run artifacts:
             https://github.com/19PINE-AI/cascade-gap}
}`
