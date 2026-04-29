# Cascade Gap — Phase-3 protocol

This repo investigates whether two-pass self-cascades (perceive-and-record, then reason) improve over end-to-end multimodal generation on long-form review tasks.

**Phase-3 reset (April 2026):** all Phase-1 / Phase-2 short-QA benchmarks (MMAR, DocVQA, ChartQA) and the older long-form pilot scripts have been removed. We now run a single, sharper protocol on long-form review generation only.

## Protocol

For each source (audio talk or scanned multi-page paper):

1. **Reference transcript** — Gemini 3 Flash transcribes / OCRs the source.
2. **C0 (end-to-end)** — Gemini 3.1 Pro reads the raw source and writes a comprehensive review article in one call.
3. **C1 (cascade)** — Gemini 3.1 Pro Pass-1 transcribes, Pass-2 writes the review from its own transcript (no source in Pass-2).

Both C0 and C1 are scored against the reference by **GPT-5.4** (`reasoning_effort='high'`):
- **Hallucination test:** judge lists every claim in the review not supported by reference. Zero tolerance — any unsupported claim → halluc_score = 0.
- **Probe coverage:** GPT-5.4 extracts 30-50 atomic factual probes from the reference; judge marks each as COVERED / MISSING in the review.
- `final_score = halluc_score × probe_coverage`.

## Layout

```
pilot/
  pilot_audio_review.py    # audio-source review pipeline
  pilot_paper_review.py    # multi-page-image source review pipeline
  stats.py                 # bootstrap CIs + sign tests

data/
  longform_audio/          # audio sources (.mp3)
  longform_pdf/scanned/    # scanned papers + pre-rendered page images
                           # + pilot_sample.jsonl

runs/
  audio-review-<id>-<ts>/  # one directory per audio run
  paper-review-<id>-<ts>/  # one directory per paper run
    reference_transcript.txt
    review_C0.txt
    review_C1.txt
    transcript_C1_pass1.txt
    probes.json
    judge_halluc_C0.json   judge_probes_C0.json
    judge_halluc_C1.json   judge_probes_C1.json
    summary.json

research_log/
  2026-04-29_phase3_audio_review.md       # current Phase-3 first results
  2026-04-29_nasa_paper_diagnostic.md     # why NASA paper coverage didn't improve
  phase2_plan.md                          # roadmap (predates Phase-3 reset)

cascade_gap_paper_plan.md                 # original (Phase-0) plan
```

## How to run

```bash
# Audio
python3 pilot/pilot_audio_review.py \
  --audio data/longform_audio/karpathy_sogpt_32k.mp3 \
  --id karpathy_sogpt \
  --title "Andrej Karpathy: State of GPT"

# Paper (multi-page scanned)
python3 pilot/pilot_paper_review.py \
  --sample data/longform_pdf/scanned/pilot_sample.jsonl \
  --items 19720009221
```

## Current results (n=2)

| Source | C0 hallucinations | C1 hallucinations | C0 probe cov | C1 probe cov |
|---|---:|---:|---:|---:|
| Karpathy 42-min talk | 13 | 3 | 0.627 | **0.961** |
| NASA Wagging Tail (1972, 9pp scanned) | 3 | 1 | **0.796** | 0.776 |

**Cascade reduces hallucinations 67-77% on both modalities.**
**Coverage benefit is modality-specific** — present on long audio, absent on short paper.

See `research_log/2026-04-29_nasa_paper_diagnostic.md` for why the NASA paper does not show a coverage win — primarily a summarization-budget bottleneck rather than a perception bottleneck.

## Keys required

```
GEMINI_API_KEY      # for Gemini 3 Flash + Pro
OPENAI_API_KEY      # for GPT-5.4 judge with reasoning_effort=high
```
