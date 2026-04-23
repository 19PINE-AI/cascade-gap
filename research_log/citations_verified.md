# Citation Verification Table

Verified 2026-04-23. Every citation in §2 of the plan resolved via `arxiv.org/abs/<id>` or web search; authors and abstracts checked against plan claims.

## arXiv citations

| # | arXiv ID | Plan ref | Actual title | Submit | Verdict |
|---|---|---|---|---|---|
| 1 | 2510.13632 | Cuervo "Closing the Gap Between Text and Speech Understanding in LLMs" | *Closing the Gap Between Text and Speech Understanding in LLMs* — Cuervo et al. (Apple) | 2025-10-15 | ✅ Match |
| 2 | 2512.18706 | X-Talk "cascaded S2S beats omni on latency without accuracy loss" | *X-Talk: On the Underestimated Potential of Modular Speech-to-Speech Dialogue System* | 2025-12-21 | ⚠️ Exists, but plan's "no accuracy loss" wording exceeds what abstract says. Soften. |
| 3 | 2604.12506 | "Beyond Transcription" closest analogue to augmented cascade | *Beyond Transcription: Unified Audio Schema for Perception-Aware AudioLLMs* | **2026-04-14** | ⚠️ Exists; 9 days old; training-time UAS supervision, not inference-time prompting. See findings doc §3. |
| 4 | 2511.15848 | Step-Audio-R1, principal opposing voice | *Step-Audio-R1 Technical Report* — StepFun | 2025-11-19 | ⚠️ Exists, but "textual surrogate reasoning is the failure mode" is NOT a quote — our paraphrase. Fix attribution. |
| 5 | 2503.02318 | Audio-Reasoner milder counterpoint | *Audio-Reasoner* — Xie et al. | 2025-03-04 | ✅ Match |
| 6 | 2412.08746 | DocVLM CVPR 2025 template | *DocVLM: Make Your VLM an Efficient Reader* | 2024-12-11 | ✅ Match |
| 7 | 2505.17163 | OCR-Reasoning Bench ICLR 2026 | *OCR-Reasoning Benchmark* | 2025-05-22 | ✅ Match; ICLR 2026 acceptance not independently verified |
| 8 | 2410.05243 | UGround / SeeAct-V ICLR 2025 | *Navigating the Digital World as Humans Do: Universal Visual Grounding for GUI Agents* | 2024-10-07 | ✅ Match (UGround is the model name) |
| 9 | 2509.02544 | UI-TARS-2 | *UI-TARS-2 Technical Report* | 2025-09-02 | ✅ Match |
| 10 | 2408.00203 | OmniParser | *OmniParser for Pure Vision Based GUI Agent* | 2024-08-01 | ✅ Match |
| 11 | 1709.08568 | Bengio Consciousness Prior | *The Consciousness Prior* | 2017-09-25 | ✅ Match |
| 12 | 2506.14373 | Discrete JEPA ICML 2025 | *Discrete JEPA: Learning Discrete Token Representations without Reconstruction* | 2025-06-17 | ✅ Match; ICML 2025 venue claim plausible |
| 13 | 2506.23918 | Thinking with Images | *Thinking with Images for Multimodal Reasoning: Foundations, Methods, and Future Frontiers* | 2025-06-30 | ✅ Match |

## Non-arXiv citations

| Plan ref | Resolved to | Verdict |
|---|---|---|
| URO-Bench (EMNLP Findings 2025) | arXiv 2502.17810, EMNLP Findings 2025 | ✅ Match |
| ColPali (ICLR 2025) | arXiv 2407.01449, ICLR 2025 Poster | ✅ Match |
| "Unintended Realization of the Consciousness Prior in Modern Language Models" ResearchGate 2024 | ResearchGate publication 392739595 | ✅ Exists |

## New citations to add (from Phase 0 discovery)

| arXiv ID | Title | Relevance |
|---|---|---|
| 2602.17598 | *The Cascade Equivalence Hypothesis: When Do Speech LLMs Behave Like ASR→LLM Pipelines?* | §2 Silo 1 + §3 Move 3 mechanism: speech LLMs are internally cascading |
| 2505.13032 | *MMAR: A Challenging Benchmark for Deep Reasoning in Speech, Audio, Music, and Their Mix* | §4.2 audio headline benchmark — hierarchical Signal→Perception→Semantic→Cultural stratification fits symbolic→perceptual axis |
| 2508.13992 | *MMAU-Pro* | §4.2 long-form audio stratification |
