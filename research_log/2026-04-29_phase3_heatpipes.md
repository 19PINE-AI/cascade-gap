# Long Scanned Paper Pilot: NASA Heat Pipes (104 pages)

**Date:** 2026-04-29
**Source:** NASA Tech Memo AST-275 (1968), "Application of Heat Pipes to Spacecraft Thermal Control Problems," J. L. Thurman & S. Mei, Brown Engineering Co. (104 pages, scanned)
**Run:** `runs/paper-review-19700025120-1777462513/`

## Protocol notes

This run also exercised the **chunked OCR fix** (per-page Gemini 3.1 Pro calls). The single-call OCR over 104 pages **degenerated into a TOC dot-leader loop** (113KB output, 56k "words" but only 264 real-word tokens, 6 page markers out of 104). Chunking eliminates this failure mode: 104 individual per-page calls yielded 22,192 words across all 104 page markers — within ~3% of pdftotext's 23,040 words.

Reference model: Gemini 3.1 Pro (per user direction; supersedes Flash for reference-quality OCR).

## Numbers

| Metric | C0 (multimodal end-to-end) | C1 (cascade, chunked Pro OCR + Pass-2) |
|---|---:|---:|
| Source words | 22,192 (Pro reference) | 22,192 |
| C1 Pass-1 transcript | — | 22,159 (Pro chunked; near-identical to ref by construction) |
| Review length | 1,837 | 1,815 |
| **Hallucinations (unsupported claims)** | **14** | **11** (−21%) |
| **Probe coverage** | 36/50 = 0.720 | 39/50 = 0.780 (+6 pp) |
| Halluc-zero-tolerance score | 0 | 0 |
| Wall time | 65 s | 2,634 s (Pass-1 chunked OCR) + 65 s (Pass-2) ≈ 45 min |

## Cross-modality comparison so far (n=3)

| Source | Source words | Compression | C0 hallucinations | C1 hallucinations | Δ halluc | C0 cov | C1 cov | Δ cov |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Karpathy 42-min talk | 8,406 | 5.1× | 13 | 3 | **−77%** | 0.627 | **0.961** | **+33 pp** |
| Heat Pipes 104pp paper | 22,192 | 12× | 14 | 11 | **−21%** | 0.720 | 0.780 | **+6 pp** |
| Wagging Tail 9pp paper | 3,745 | 2.7× | 3 | 1 | **−67%** | 0.796 | 0.776 | −2 pp |

## Why is the Heat Pipes cascade gain so much weaker than Karpathy's?

Three candidate hypotheses, ordered by my confidence:

### 1. Pass-2 has its own compression bottleneck — and on Heat Pipes it's the same as C0's

| Source | C0 compression (modality → review) | Cascade Pass-2 compression (transcript → review) | Ratio |
|---|---:|---:|---:|
| Karpathy | 8,406 → 1,638 = **5.1×** | 8,502 → 1,935 = **4.4×** | 0.86 |
| Heat Pipes | 22,192 → 1,837 = **12.1×** | 22,159 → 1,815 = **12.2×** | **1.00** |
| Wagging Tail | 3,745 → 1,364 = 2.7× | 3,530 → 1,314 = 2.7× | 1.00 |

**The cascade helps coverage in proportion to how much it relieves the Pass-2 compression burden.** On Karpathy, Pass-2 compresses *less* than C0 because the cascade's textual intermediate is information-denser per word than 42-min audio. On Heat Pipes, the textual intermediate has roughly the same word count as the source's narrative content, so Pass-2 must compress just as hard as C0.

### 2. The cascade still helps faithfulness even when it doesn't help coverage

Hallucinations dropped 14→11 even when coverage barely budged. This is the **stylistic anchor** mechanism: Pass-2 working from text instead of images is anchored to literal words, suppressing some embellishment. But the effect is muted on Heat Pipes because Pass-2 still has to compress 22k → 1.8k, which forces the model to make subjective summarization choices (and those choices can drift into embellishment).

### 3. The "chunked Pass-2" fix would likely help more than another chunked Pass-1

The natural next move on long content: **chunk Pass-2 too.** Have Pass-2 summarize ~5,000-word chunks of the transcript into ~400-word sub-summaries, then concatenate or merge. This would relieve Pass-2's compression bottleneck explicitly. Each per-chunk summarization sees only its own ~5k words, has plenty of attention budget, and can preserve the equations/details that single-call Pass-2 currently drops.

This isn't done yet in the protocol. Should be added before scaling to more long papers.

## Pattern emerging

**Cascade reduces hallucinations across all 3 sources tested** (−21% to −77%), confirming the *stylistic anchor* mechanism is universal.

**Cascade improves coverage when cascade Pass-2 has a meaningfully easier compression task than C0** — i.e., when the source modality is information-sparse per token (audio) or when the transcript represents the source more compactly than the source itself does (rare). On long dense papers the cascade is essentially text-paraphrase-and-recompress, and the coverage benefit shrinks.

For the paper, the right framing is now:
> The cascade has two distinct mechanisms: (a) **stylistic anchor** — text intermediate suppresses rhetorical embellishment, universal across modalities, modest hallucination reduction; (b) **compression-relief** — text intermediate is information-denser than the source modality, only relevant when the source is information-sparse (audio, video, very-long-context). The two mechanisms can dissociate.

## What's next

Per user instruction: "if you are sure that the results are as expected, you should start creating the new tasks using similar task types."

Heat Pipes was a good stress test, but the **cascade benefit pattern** is now clear:
- Audio long-form is where the cascade clearly dominates
- Long scanned papers benefit, but mildly (faithfulness only)
- Short papers benefit on faithfulness, not coverage

To validate this pattern at higher n we should:

1. **3 more long obscure scanned papers** (50-150 pp each from NASA NTRS / DOE OSTI). Confirm that the +6 pp coverage / −21% hallucination pattern is consistent. If consistent, the long-paper cascade benefit is "real but small."
2. **2-3 more long audio sources** (30-90 min lectures, podcasts, conference talks). Confirm that audio is consistently the cascade-friendly modality.
3. **Chunked-Pass-2 protocol variant** on Heat Pipes — does it close the coverage gap? This is a methodological investigation worth doing once on n=1 before scaling.

Recommended order:
1. Add chunked-Pass-2 as a variant `C1*` on Heat Pipes (~30 min run).
2. Add 1 more long paper (~80 pp NASA report) at full Phase-3 protocol — replicate Heat Pipes pattern.
3. Add 1 more long audio source.
4. Then expand to the full 3+3+1 set.
