# Audio Music Schema (C2 augmented cascade, music-heavy tasks) — Pass-1 prompt spec

Goal: capture the musical content that a speech-centric UAS (`audio_uas.md`) drops. Pre-registered for validation of the alphabet-match thesis on MMAR music items where UAS collapsed audio to `events: [music]`.

## Schema

Pass 1 emits a structured musical description with:

```
<overview>
  genre: <hip-hop|classical|folk|pop|rock|jazz|electronic|traditional|other> | mixed
  tempo_bpm: <estimate, or range>
  meter: <4/4|3/4|6/8|other|unclear>
  mood: <free-text 2-4 words>
  duration_s: <seconds>
</overview>

<instrumentation>
  lead: [<instrument>*]             # e.g. electric guitar, piano, male voice
  accompaniment: [<instrument>*]
  percussion: [<instrument>*]
  effects: [<chorus|distortion|reverb|delay|none>*]
</instrumentation>

<tonal>
  key: <e.g. F major, A minor, modal-Dorian, atonal, unclear>
  key_confidence: low|medium|high
  chord_progression: [<chord-label>*]  # e.g. [C, Am, F, G] or [iv, VII, i]
  chord_confidence: low|medium|high
  melodic_range: <pitch range, e.g. "C4 to E5">
  notable_intervals: [<interval-name>*]  # e.g. "fifth", "octave", "tritone"
</tonal>

<structure>
  form: <through-composed|verse-chorus|AABA|intro-verse-chorus|other>
  sections: [(start_s, end_s, label)*]   # e.g. (0, 8, "intro"), (8, 24, "verse")
  dynamics: <crescendo|decrescendo|flat|swelling>
</structure>

<vocal>  # Omit if no singing
  voice_type: <soprano|alto|tenor|bass|male|female|child|group>
  style: <sung|rapped|spoken|throat-sung|operatic|folk|other>
  language: <language if identifiable>
  lyrics_snippet: <first line or salient phrase, verbatim>
</vocal>

<cultural>
  style_cues: [<cue>*]            # e.g. "pentatonic", "blue notes", "raga"
  inferred_origin: <region/era if confident>
  confidence: low|medium|high
</cultural>

<non_musical_events>
  [<applause|laughter|speech-over|environmental-sound|silence>*]
</non_musical_events>
```

## Pass-1 prompt

```
You are the perception pass of a two-pass audio analysis. The audio contains
music (with or without singing). Emit a structured musical description using
the schema in the system prompt. Do NOT answer any downstream question.

Fill in every section you can. Use "unknown" or omit a section only when you
cannot make even a low-confidence estimate. Be numerically concrete where
possible (tempo in BPM, duration in seconds, pitch in scientific notation).

Pay specific attention to:
- **tonal analysis**: identify the key (major/minor/modal) and the primary
  chord progression. These are load-bearing for music-QA tasks.
- **instrumentation**: list every instrument and every voice type you can
  distinguish; note timbral qualities (bright, dark, nasal, warm).
- **cultural/stylistic cues**: throat singing, blue notes, pentatonic scales,
  modal harmony — these often determine the correct answer for cultural-origin
  questions.
- **structure**: emit explicit section timings. Many MMAR items ask about
  what happens "before life appears" or similar time-indexed structure.

End output with: END_PERCEPTION
```

## Pass-2 prompt template

```
Below is a structured musical description of an audio clip, produced by an
earlier perception pass. Use ONLY the information below to answer the
question.

<perception>
{pass_1_output}
</perception>

Question: {task_question}
Choices: {task_choices}

Answer with ONLY the single letter of the correct choice (A, B, C, or D).
```

## When to use this schema vs. `audio_uas.md`

A simple router based on the task question / audio content type:

- Audio is primarily music (or music-dominant mixed) → `audio_music.md`.
- Audio is primarily speech (with or without paralinguistics) → `audio_uas.md`.
- Mixed (speech over music bed) → emit both schemas, concatenated.
- Environmental sounds with no speech or music → a third schema (not yet pre-registered).

The router itself can be a Pass-0 model call that asks "classify this audio into {speech, music, environmental, mixed}." This is a tiny call and keeps the Pass-1 schema on-task for Pass-2.

## Expected pattern

On the MMAR Perception Layer music items (5-ish of our pilot sample):
- Speech UAS (original C2): degenerate Pass-1 output like `[inaudible] events:[music]`, Pass-2 guesses.
- Music schema (this file): key, chord progression, instrumentation, style cues all available to Pass-2, which can answer "what is the key" or "what style" directly.

If Δ(music-schema C2 − speech-UAS C2) is large and positive on music items, the alphabet-match thesis is directly validated.
