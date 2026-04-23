# Audio Unified Schema (C2 augmented cascade) — Pass-1 prompt spec

Goal: enrich the transcription pass so downstream reasoning has access to paralinguistic and non-lexical information that plain ASR drops. Draws on "Beyond Transcription" (arXiv 2604.12506) schema plus additions for diarization and temporal structure.

## Schema

Pass 1 emits a sequence of **segments**, each tagged with:

```
[<start_time>–<end_time>] [<speaker_id>] <text>
  prosody: {pitch: low|mid|high|rising|falling, pace: slow|normal|fast, volume: quiet|normal|loud, stress: <word_or_phrase>*}
  affect: {emotion: neutral|happy|sad|angry|fearful|surprised|disgusted, arousal: low|mid|high, valence: neg|neu|pos, sarcasm: yes|no|uncertain}
  events: [<non_speech_event>*]   # e.g. laughter, cough, music, door_slam, silence>2s
  confidence: low|medium|high       # self-reported lexical confidence
```

**Speaker IDs** are assigned incrementally (`S1`, `S2`, …) and kept consistent across segments in the same clip.

**Times** use `MM:SS.sss` anchored to clip start.

## Pass-1 prompt (Python f-string friendly)

```
You are performing the perception pass of a two-pass audio analysis.
Do NOT answer the downstream question. Do NOT paraphrase the audio's meaning.
Your single job is to emit a structured transcript that a separate reasoning
step can later consume.

Emit a sequence of segments, one per line, in this exact form:

[MM:SS.sss–MM:SS.sss] [S<n>] <verbatim transcript of the segment>
  prosody: {pitch: ..., pace: ..., volume: ..., stress: <word|phrase|->}
  affect: {emotion: ..., arousal: ..., valence: ..., sarcasm: yes|no|uncertain}
  events: [comma-separated non-speech events in the segment, or "none"]
  confidence: low|medium|high

Rules:
- Verbatim transcript: include disfluencies (um, uh), repetitions, and audible
  interjections. Use [inaudible] for segments you cannot transcribe.
- Speakers: assign S1, S2, ... in order of first appearance. Keep consistent.
- Prosody stress: quote the stressed word or short phrase. Use "-" if flat.
- Affect: use "neutral" when unsure rather than guessing.
- Events: include laughter, crying, sighs, coughs, music, background noise,
  long silences (>2s), door slams, phone rings, applause, etc. Use "none"
  if the segment has no non-speech content.
- Confidence: rate only the lexical transcript, not the affect tags.

End your output with a single line: END_PERCEPTION
```

## Pass-2 prompt template

```
Below is a structured transcript of an audio clip, produced by an earlier
perception pass. Use ONLY the information below to answer the question.
Do not assume anything not present in the transcript.

<structured_transcript>
{pass_1_output}
</structured_transcript>

Question: {task_question}

Answer:
```

## C3 Rich variant (per §4.3)

Same schema; Pass-1 prompt additionally asks for a short free-form **"perceptual summary"** at the top (before the segments), listing salient non-lexical cues (e.g., "speaker 2 is audibly sarcastic in the second half", "sudden volume drop at 00:12 suggests surprise"). This tests whether free-form perceptual reasoning at Pass 1 closes more of the gap than structured tags alone.

## Ablation variants (for §4.3 alphabet-richness sweep)

- **UAS-transcription-only**: strip `prosody`, `affect`, `events`, `confidence` — leaves only text + timestamps + speakers. This is the "plain cascade" C1 baseline.
- **UAS-prosody**: add `prosody` only.
- **UAS-affect**: add `affect` only.
- **UAS-events**: add `events` only.
- **UAS-full**: C2.
- **UAS-full+summary**: C3.

Running the 6-point sweep on MUStARD (sarcasm) and MELD (emotion) gives us Figure 3 directly.
