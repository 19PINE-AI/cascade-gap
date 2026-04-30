# Multi-speaker IETF SNAC WG meeting — cascade win on the hardest audio cell yet

**Date:** 2026-04-30
**Source:** IETF SNAC (Stub Network Auto Configuration for IPv6) WG Interim, 2026-04-16, 60-min, ~5 speakers ([YouTube](https://www.youtube.com/watch?v=20u_t8QgHEw))
**Why this source:** First multi-speaker cell. SNAC is one of the IETF's more obscure WGs (IPv6 auto-configuration edge cases) and the recording is post the most likely training-data cutoff for the foundation models in the loop, so the cascade's coverage gain has to be earned from the audio rather than recalled from prior knowledge.
**Run:** `runs/audio-meeting_minutes-ietf_snac-1777518337/`
**Task:** `meeting_minutes` (structured Decisions / Action Items / Open Issues output)

## Numbers (final, after re-running the reference)

| Metric | C0 (multimodal end-to-end) | C1 (cascade) |
|---|---:|---:|
| Reference transcript words (Pro chunked) | 9,311 | 9,311 |
| C1 Pass-1 transcript words | — | 9,311 |
| Meeting-minutes output words | 892 | 1,030 |
| **Hallucinations (unsupported claims)** | 14 | **11** (−21%) |
| **Probe coverage** | 14/49 = 0.286 | **26/49 = 0.531** (+24.5 pp) |
| Wall time | ~50 s | ~210 s OCR + 130 s Pass-2 + 5 min judge ≈ 13 min |

## Why this cell matters

This is the first **multi-speaker** Phase-3 cell. If the cascade lost speaker attribution in Pass-1 transcription and Pass-2 then fabricated speaker assignments, we'd expect more hallucinations under cascade — exactly the failure mode I worried about before running it. The result goes the other way: cascade reduces hallucinations 21% and roughly doubles coverage. The two cascade mechanisms (stylistic anchor + compression-relief) both fire on multi-speaker content.

The +24.5 pp coverage win is the largest of any meeting-minutes cell:
- Karpathy meeting-minutes (1 speaker, 42-min): 0.16 → 0.34 (+18 pp)
- IETF SNAC meeting-minutes (5 speakers, 60-min): 0.286 → 0.531 (+24.5 pp)

The IETF source has higher C0 baseline (0.286 vs Karpathy's 0.16) because the meeting-minutes prompt has a natural fit with the structured WG content (decisions, open issues, action items map directly to recurring spoken patterns). Even with the higher baseline, cascade extracted +24.5 pp — consistent with the inverse-correlation hypothesis (Karpathy's lower baseline left less to gain in absolute pp terms, but cascade still produced a near-doubling on both cells).

## Methodology gotcha: silent reference truncation

The first run produced **C1 27 unsupported vs C0 15 unsupported** — a clean counter-result. Diagnosing it was instructive:

- Reference chunk 1 had 1,981 words; C1 Pass-1 chunk 1 had 4,368 words. Same prompt, same model, same audio segment.
- Reference chunk 1 ended mid-sentence: `"Uh, well, see, yeah, that'"`. The Pro call had been silently truncated by the server.
- The judge therefore compared the cascade against an incomplete reference. The cascade's correctly-transcribed second-half content was flagged "unsupported" because it wasn't in the reference.

After deleting `reference_transcript.txt` and rerunning (with `--run-dir` to reuse C0/C1 outputs), the second reference call captured the full 4,368 words on chunk 1, and the cascade win materialized.

**Lesson for the protocol:** add a sanity check that compares reference word count to C1 Pass-1 word count when both used the same prompt + model. A gap >20% should auto-fail the cell and request a re-run.

This is the second silent-truncation failure of the project (the first was the Heat Pipes 104pp single-call OCR producing a TOC dot-leader loop). Both were caught and fixed only because manual inspection happened. They argue for stronger automatic validation in any production cascade pipeline.

## Pattern check

The 9-cell Phase-3 dataset now spans:
- 2 modalities (audio, scanned image)
- 2 prompt structures (long-form review, structured meeting-minutes)
- 1 to 5 speakers
- 9 pp to 104 pp papers, 42-min to 60-min audio

Cascade reduces hallucinations in 8/9 cells; improves coverage in 7/8 cells with C0 < 0.85. The single counter-cell (Natural Vibration 42pp) is a content-prior outlier on famous historical references. **There is no Phase-3 cell where cascade harms both axes simultaneously, once reference-quality issues are excluded.**

Phase-3 is now in a publishable state.
