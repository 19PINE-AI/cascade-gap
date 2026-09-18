# Transcribe, Then Reason: Two-Pass Decomposition for Multimodal Review

**Paper:** [arXiv:2609.18958](https://arxiv.org/abs/2609.18958) · [PDF](https://arxiv.org/pdf/2609.18958)
**Interactive companion site:** https://01.me/research/cascade-gap
**Authors:** Bojie Li (Pine AI), Noah Shi (University of Washington)

This repo contains the code, prompts, and per-run artifacts for the paper.
It investigates whether two-pass self-cascades (transcribe, then review the
transcript) improve over end-to-end multimodal generation on long-form review
tasks. Across a 21-source suite of long recordings and scanned / rendered
papers, the decomposition improves both faithfulness and coverage; the paper
explains why (generation under load, not perception) and when it fails.

```bibtex
@misc{li2026transcribe,
  title         = {Transcribe, Then Reason: Two-Pass Decomposition for Multimodal Review},
  author        = {Li, Bojie and Shi, Noah},
  year          = {2026},
  eprint        = {2609.18958},
  archivePrefix = {arXiv},
  primaryClass  = {cs.MM},
  url           = {https://arxiv.org/abs/2609.18958}
}
```

The paper source lives in `paper/`; the companion site in `website/`.

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

## Results

The full 21-source results, mechanism controls, and failure-mode analysis are
in the paper ([arXiv:2609.18958](https://arxiv.org/abs/2609.18958)) and can
be explored case by case on the companion site
(https://01.me/research/cascade-gap). The early two-source pilot is documented
in `research_log/2026-04-29_phase3_audio_review.md` and
`research_log/2026-04-29_nasa_paper_diagnostic.md`.

## Keys required

```
GEMINI_API_KEY      # for Gemini 3 Flash + Pro
OPENAI_API_KEY      # for GPT-5.4 judge with reasoning_effort=high
```
