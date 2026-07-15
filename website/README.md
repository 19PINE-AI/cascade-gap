# Paper website — interactive companion

React (Vite) single-page site explaining the cascade-gap paper to first-time
readers, in three parts:

1. **How it works** — plain-language walkthrough of the protocol, the
   observation, the mechanism experiments (E1–E9), and the two failure modes.
2. **Major evaluation results** — interactive charts: 21-cell dumbbell
   (coverage / hallucinations), inverse-baseline-law scatter, E3 transcript
   ceiling, cross-model tables, robustness checks, practitioner checklist.
3. **Trajectory visualizer** — per-case explorer: source → Pass-1 transcript →
   both reviews (full text) → judge verdicts, with the probe checklist,
   flagged-claim lists, side-by-side reviews, and other-model runs.

All numbers and text excerpts are extracted from `../runs/` by
`extract_data.py` (verbatim run artifacts, nothing regenerated). The sanity
check at the end of that script asserts the aggregates match the paper
(mean Δcov +0.118, mean Δhalluc −3.86, 16/21, 18/21).

## Build

```bash
python3 extract_data.py     # regenerate src/data/paperData.json from runs/
npm install
npx vite build              # emits self-contained dist/index.html (~1.3 MB)
npx vite                    # dev server
```

`vite-plugin-singlefile` inlines everything into one HTML file, so the built
site works from `file://` or any static host with no assets directory.
