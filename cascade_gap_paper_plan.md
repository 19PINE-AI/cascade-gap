# The Cascade Gap — Comprehensive Paper Plan

## 1. Paper identity

**Title:** The Cascade Gap: When Pipelines Beat End-to-End Multimodal Agents

**One-sentence thesis:** For a wide and predictable class of multimodal reasoning tasks, prompting the same frontier model in a two-pass self-cascade — perceive-and-transcribe, then reason — yields meaningfully better task accuracy than the model's native end-to-end mode, and the sign of this *cascade gap* is predictable from properties of the task.

**Contribution claims, in priority order:**
1. **A measurement.** First systematic, same-weights, cross-modality measurement of the cascade gap, covering audio, document, and GUI-agent domains using both open-weight and frontier closed-source multimodal models.
2. **A predictive rule.** A task-property-based predictor of the cascade gap's sign and magnitude, which a practitioner can apply to a new task without running the experiment.
3. **A mechanistic story.** Demonstration that the gap closes (sometimes fully) when the intermediate textual representation is enriched with task-relevant non-lexical tags, evidence that the *content* of the bottleneck — not just its presence — drives the effect.
4. **A practical prescription.** Concrete recommendations for builders of multimodal agents, including the cost-accuracy Pareto for each task class.

**Target venue (in order of fit):** COLM 2026, EMNLP 2026 main, NeurIPS 2026 D&B track. ICLR 2027 if timing slips. Workshop fallback: NeurIPS Foundation Model Eval workshop, ICLR R2-FM workshop.

**Honest novelty boundary:** the *observation* that cascades sometimes win is not new in any single silo. The novelty is the cross-modality unification under a same-weights protocol with a predictive rule.

---

## 2. Related work

### Silo 1 — Speech / audio LLMs

The cleanest single antecedent. Cuervo et al. ("Closing the Gap Between Text and Speech Understanding in LLMs", arXiv 2510.13632, Oct 2025) names the *text-speech understanding gap* and shows speech-LLMs underperform text-LLMs on equivalent reasoning tasks. We adopt the "gap" terminology and generalize it across modalities. X-Talk (arXiv 2512.18706, Dec 2025) shows optimized cascaded speech-to-speech pipelines beat omni models on latency without accuracy loss; URO-Bench (EMNLP Findings 2025) documents speech-LLM regression on instruction-following relative to backbone text models. "Beyond Transcription" (arXiv 2604.12506) is the closest existing analogue to our augmented-cascade condition — it decomposes audio into transcription + paralinguistics + non-linguistic events and shows the structured intermediate alphabet matters; we extend this with same-model cascades and cross-modality comparison.

The principal opposing voice is **Step-Audio-R1** (arXiv 2511.15848, Nov 2025), which argues end-to-end audio reasoning *can* work via Modality-Grounded Reasoning Distillation, and that "textual surrogate reasoning" is the failure mode. We engage Step-Audio-R1 directly: their finding is consistent with ours under one reading — that an audio-only alphabet (their MGRD-trained CoT) outperforms a text-only alphabet on tasks needing acoustic features. This is exactly the alphabet-fit story our boundary condition predicts. Audio-Reasoner (arXiv 2503.02318) is a milder counterpoint.

### Silo 2 — Vision / document understanding

**DocVLM** (CVPR 2025, arXiv 2412.08746) is the methodological template. It is the only existing paper with a *compute-controlled* ablation, showing OCR-augmented VLMs beat pure-vision VLMs at every fixed token budget (DocVQA 56.0% → 86.6% on InternVL2 at 448×448). We replicate its compute-control rigor and extend its scope from vision-only to cross-modality. **OCR-Reasoning Benchmark** (arXiv 2505.17163, ICLR 2026) sharpens the boundary: pure-OCR cascades cap below 50% on text-rich reasoning, indicating that *some* text-rich tasks need spatial information the OCR alphabet drops. This is our paper's exact thesis empirically demonstrated within one modality. **ColPali** (ICLR 2025) shows vision-only document retrieval beats OCR pipelines for retrieval — a useful counterexample we discuss as a task-class boundary (retrieval ≠ reasoning).

### Silo 3 — GUI / computer-use agents

This silo is our hardest. **UGround / SeeAct-V** (arXiv 2410.05243, ICLR 2025) and **UI-TARS-2** (arXiv 2509.02544) report vision-only agents beating DOM/a11y-tree-augmented agents on Mind2Web, OSWorld, and related benchmarks. We do not contest these results; we predict them. The a11y tree was designed for screen readers, not agents — its loss function targets linear readability for blind users, not affordance/state/spatial reasoning for action. Our same-model cascade test in this silo asks a different question: can the same vision model, prompted to *first describe the screen as structured text, then act*, do better than acting end-to-end? Even if HTML/a11y trees underperform, a model-generated structured description may close the gap. **OmniParser** (arXiv 2408.00203) is the closest extant instance of this idea (vision → structured text → reasoning); we generalize it as one point on the alphabet-richness sweep.

### Cross-cutting theory

Bengio's **Consciousness Prior** (arXiv 1709.08568) is our high-level theoretical anchor: cognition benefits from sparse, discrete, compositional bottlenecks between perception and reasoning. We do not claim to validate the prior in its strong form; we adopt the *operational* idea — that an externalized discrete bottleneck can do work equivalent to an architecturally-enforced one. **Discrete JEPA** (ICML 2025, arXiv 2506.14373) makes the closest related theoretical move within vision. The 2024 ResearchGate preprint "Unintended Realization of the Consciousness Prior in Modern Language Models" makes the analogous argument for chain-of-thought in text. **"Thinking with Images for Multimodal Reasoning"** (arXiv 2506.23918) and the **Interleaved-Modal CoT** line argue *against* discrete textual bottlenecks for visuospatial reasoning; we engage these as principled disagreements about a specific task class (visuospatial), not as falsifications of the cross-task pattern.

### Positioning statement (one paragraph for the paper)

> A growing set of single-modality results — in speech, in document understanding, in GUI control — show cascaded inference sometimes outperforms native end-to-end multimodal models. These results are individually striking but collectively unexplained: they appear in different communities, use different protocols, and have not been related to one another. We provide the first cross-modality, same-weights measurement of this *cascade gap*, show that its sign is predictable from a small set of task properties, and demonstrate that the gap closes — sometimes fully — when the intermediate textual representation is enriched to carry task-relevant non-lexical information.

---

## 3. Framing

### The three-move argument structure

**Move 1: Establish the gap, with a clean protocol.** Define the cascade gap as $\Delta = \text{Acc}_\text{cascade} - \text{Acc}_\text{end-to-end}$, measured under a same-weights protocol where one model performs both the perceive-and-transcribe pass and the reason pass. Report $\Delta$ across modalities, models, and tasks. Show it is non-trivial (frequently 5-20+ points) and signed (positive on symbolic tasks, negative on perceptual ones).

**Move 2: Predict the sign of $\Delta$.** Define a small set of task-property features (does the answer depend on lexical content? on prosody/emotion? on spatial layout? on visual affordance?) and show a simple predictor (logistic regression or similar) on these features predicts the sign of $\Delta$ across held-out tasks. This is what makes the paper a framework, not a benchmark.

**Move 3: Probe the mechanism via alphabet richness.** Show that for tasks where end-to-end currently wins, enriching the cascade's intermediate representation (with paralinguistic tags / layout markers / affordance annotations) closes the gap, sometimes completely. This evidences that *what the bottleneck carries* — not the mere existence of a bottleneck — is the load-bearing factor.

### Key terms and how to use them

- **Cascade gap ($\Delta$):** the headline measured quantity. Always signed.
- **Self-cascade:** a cascade in which both passes use the same model weights. Headline protocol.
- **End-to-end / native multimodal:** the model called once, raw modality in, answer out.
- **Plain cascade:** Pass 1 prompt = "transcribe" / "extract text" / "list elements," with no augmentation.
- **Augmented cascade:** Pass 1 prompt enriched to carry task-relevant non-lexical tags.
- **Symbolic-content task:** the answer is determined entirely by content expressible in standard text.
- **Perceptual task:** the answer requires non-symbolic perceptual features (prosody, layout, affordance, aesthetics).

We deliberately do *not* coin a new term beyond "cascade gap." The paper's identity rests on the measurement, not vocabulary.

### Scope-limiting statements (essential, must appear in the abstract)

- We measure inference-time architectural choice, not training-time architectural choice. We do not claim native multimodal pretraining is wrong; we claim the *deployment* form of these models for *symbolic-content tasks* should often be the self-cascade.
- We do not train any models. All results use released open-weight and frontier closed-source models.
- The cascade gap is a *current-generation* measurement. We expect it to shift as omni models gain more reasoning training; we report what is true now and identify which task properties the gap is most likely to persist on.

---

## 4. Experimental plan

### 4.1 Model coverage

**Tier 1 (headline, same weights both passes):**

| Model | Audio | Document/Vision | GUI |
|---|---|---|---|
| Gemini 3 Pro | ✓ | ✓ | ✓ |
| Gemini 3 Flash | ✓ | ✓ | ✓ |
| GPT-4o / o4 (audio + vision) | ✓ | ✓ | ✓ |
| Claude 4 Opus / Sonnet | — | ✓ | ✓ |
| Qwen2.5-Omni-7B / 72B | ✓ | ✓ | partial |
| Step-Audio-R1 | ✓ | — | — |
| UI-TARS-2 | — | partial | ✓ |

Approximately 15-18 (model × modality) cells. Same weights for both perceive-and-transcribe and reason; comparison against the same model's end-to-end mode.

**Tier 2 (robustness, decoupled cascades):** Gemini-3-Flash perceives → Gemini-3-Pro reasons; Gemini perceives → Claude reasons; Qwen2.5-Omni perceives → Llama-3.1-405B reasons. Tests whether the same-model constraint is necessary or whether the gap is purely architectural.

**Tier 3 (deployed-baseline reference):** Whisper-v3 → GPT-4o text; PaddleOCR → Claude 4; OmniParser → GPT-4o. For the practical-prescription section only.

### 4.2 Task axes

For each modality, 5-6 tasks ordered from purely-symbolic to purely-perceptual.

**Audio:**
1. Spoken-SQuAD / LibriSQA factual QA (symbolic)
2. AMI / ICSI meeting minutes generation (mostly symbolic)
3. MELD-derived sentiment-aware summarization (mixed)
4. MELD / IEMOCAP emotion classification (paralinguistic)
5. MUStARD sarcasm detection (paralinguistic)
6. DIHARD speaker diarization (perceptual)

**Document / vision:**
1. DocVQA text-heavy split (symbolic)
2. WikiTableQuestions visualized (mixed)
3. ChartQA (mixed-perceptual)
4. InfographicVQA (perceptual)
5. IAM handwriting (perceptual)

**GUI:**
1. WebArena form-filling subset (structured)
2. VisualWebArena standard SaaS (mixed)
3. OSWorld text-heavy subset (mixed)
4. OSWorld creative / canvas subset (perceptual)
5. Custom: small game-UI suite (perceptual)

Each task uses an established benchmark where possible. Custom tasks are constructed only where the symbolic→perceptual axis has gaps in existing benchmarks; these are released alongside the paper.

### 4.3 Conditions

For each (model, task) cell, three measurements:
- **C0 — End-to-end:** raw modality in, answer out, single call.
- **C1 — Plain self-cascade:** Pass 1 = "transcribe" (audio) / "extract text" (document) / "describe screen" (GUI); Pass 2 = task answer using only Pass 1 output.
- **C2 — Augmented self-cascade:** Pass 1 prompt enriched with task-class-relevant tag schema (paralinguistic for audio, layout for documents, affordance/state for GUI); Pass 2 unchanged.

For a subset of representative tasks per modality, an additional **C3 — Rich self-cascade** with chain-of-thought-style perceptual reasoning embedded in Pass 1, to test whether the augmented gap-closing is monotonic in alphabet richness.

### 4.4 Controls

1. **Decoding parity.** Same temperature, top-p, max tokens (per pass) across all conditions.
2. **Prompt fairness.** End-to-end prompts and Pass 1 prompts both go through the same iteration protocol — fixed budget of N prompt revisions on a held-out dev subset, with all final prompts released. This pre-empts the "your cascade prompt was better-engineered" attack.
3. **Compute reporting.** Three numbers per cell: answer-side output tokens, total output tokens (cascade pays for Pass 1), wall-clock latency. Report all three. Headline accuracy comparison is unconditional; cost-accuracy Pareto is reported as Figure 4.
4. **Reasoning-mode handling.** End-to-end measurements use the model's default mode. A separate focused experiment compares reasoning-mode end-to-end (e.g., Gemini 3 with thinking, GPT-o-style) against the self-cascade, to test whether internal CoT substitutes for an externalized bottleneck. This is a side study, not part of the main matrix.
5. **Statistical reporting.** Three random seeds per (model × task × condition); report mean ± 1.96σ. Significance tests on the cascade gap's sign.

### 4.5 Headline figures

**Figure 1 — The cascade gap landscape.** Heatmap or signed-bar grid: rows = modalities, columns = tasks ordered along the symbolic→perceptual axis, cells = mean cascade gap across models. Single image conveys the entire result.

**Figure 2 — Same-weights validation.** For each modality, a grouped bar chart showing C0 vs. C1 accuracy for each Tier-1 model. The figure that pre-empts "your cascade had a better text model."

**Figure 3 — Alphabet richness closes the gap.** For 4 representative tasks (one symbolic-favored, one mixed, two perceptual-favored), bars showing C0 / C1 / C2 / C3 accuracy with the C0 score as a horizontal reference. Tasks where C2/C3 reach C0 = alphabet-limited; tasks where they don't = genuinely perceptual.

**Figure 4 — Accuracy-cost Pareto.** Scatter plot, accuracy vs. total output tokens, points colored by task class, shaped by condition. Shows where each architectural choice sits on the deployment frontier.

### 4.6 Predictive rule formulation

A simple supervised model (logistic regression with hand-designed task features, or a small classifier over task descriptions) trained to predict $\text{sign}(\Delta)$. Features: presence of lexical-only content, presence of paralinguistic content, presence of spatial layout, presence of dynamic/canvas UI. Cross-validated across tasks; reported as both classification accuracy and held-out modality generalization (train on audio+document, test on GUI).

The point is not to publish a state-of-the-art classifier; it is to show that *a few coarse features predict the gap's sign well above chance*, justifying the framework as a practical decision aid.

---

## 5. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Reviewer: "cascades obviously win because they use more compute" | High | Compute-Pareto Figure 4; budget-matched ablation in appendix; same-weights design eliminates cross-model confound |
| Reviewer: "your prompts are unfair" | High | Released prompts; identical iteration budget for end-to-end and cascade prompts; prompt-perturbation robustness in appendix |
| Reviewer: "Step-Audio-R1 already addresses this" | High | Direct engagement section; reframe MGRD as alphabet-richness within the audio-tag space, supporting our framework |
| Reviewer: "UI-TARS shows you're wrong for GUI" | Medium | Predicted result under our framework; canvas-UI tasks confirm boundary condition; use UI-TARS as a Tier-1 model where the cascade-on-screenshot test is also clean |
| Effect doesn't replicate cleanly across models | Medium | Pilot 2-3 tasks per modality first before full matrix; if effect is model-specific, retitle to focus on which models benefit from cascading |
| Augmented cascade prompts hard to design well | Medium | Build augmentation prompt schema before running full experiments; validate on dev subset that augmented cascade sometimes beats plain cascade |
| Closed-source API behavior changes mid-study | High | Pin model versions where possible; record snapshot date for each measurement; budget for re-running headline experiments if Gemini/GPT versions deprecate |
| Paper is scooped by a same-modality follow-up | Medium | Cross-modality unification + same-weights protocol is the moat; even if a single-silo paper appears, ours generalizes |

---

## 6. Timeline and resources

**Phase 1 — Pilot and infrastructure (weeks 1-3).**
- Build evaluation harness (single interface for all 7 models, 3 modalities, 3 conditions).
- Pilot 2 tasks per modality on Tier-1 models. Decision gate: do C0 and C1 differ by ≥3 points on at least 2 of 6 pilot tasks per modality, in either direction? If yes, proceed. If no, reconsider.

**Phase 2 — Headline matrix (weeks 4-7).**
- Run full Tier 1 matrix: ~18 cells × 5 tasks × 3 conditions × 3 seeds ≈ 800 measurement runs.
- API budget estimate: $3-6k for closed-source calls, plus open-source compute (4×H100 weeks, manageable on rented).

**Phase 3 — Robustness and augmentation (weeks 8-10).**
- Tier 2 cross-model cascades.
- C2/C3 augmented-cascade sweep on representative subset.
- Reasoning-mode side study.

**Phase 4 — Predictive rule and writing (weeks 11-13).**
- Train and validate predictor.
- Build figures, write paper.
- Internal review, prompt for external reads.

**Phase 5 — Submission prep (week 14+).**
- Anonymize, release prompts/code/data, submit.

**Resource estimate:** ~14 weeks for two people, $5-8k API budget, ~6 GPU-weeks of open-source compute, no model training.

---

## 7. Open decisions to resolve

1. **Do you want to include reasoning-mode end-to-end** (Gemini-with-thinking, o-style) in the main matrix or only as a side study? Including it tests whether internal CoT substitutes for external bottleneck — interesting but expands scope.
2. **How aggressive on GUI?** GUI is where the field's evidence runs against us. Including it makes the paper's cross-modality claim stronger but also exposes us to UI-TARS-style counter-evidence. Alternative: include GUI but explicitly frame it as the boundary case.
3. **Augmented-cascade alphabet — model-generated or hand-designed?** Model-generated tags are easier to scale but harder to control; hand-designed schemas are more rigorous but more work.
4. **Do we publish a small custom benchmark** to fill the perceptual-end gap on the GUI axis (canvas/Figma/game UI), or only use existing benchmarks? Custom benchmarks add release/maintenance burden but make the cross-modality story crisper.
