"""Phase-3 audio long-form review protocol.

Per user direction:
  - Reference transcript: Gemini 3 Flash (gemini-3-flash-preview) on raw audio.
  - C0 end-to-end: Gemini 3.1 Pro reads raw audio, writes a detailed faithful review.
  - C1 cascade: Gemini 3.1 Pro Pass-1 transcribes, Pass-2 summarizes the transcript.
  - Same-weights cascade: both C1 passes use Gemini 3.1 Pro.
  - Judge: GPT-5.4 with reasoning_effort='high'.
  - Probes: extracted by GPT-5.4 from the reference transcript.

Two-stage scoring:
  1. Hallucination test (zero tolerance): judge lists any claim in the review
     not supported by the reference transcript. If count > 0, the cell scores 0.
  2. Probe coverage: judge checks each pre-extracted factual probe → covered/missing.
     Score on probe coverage rate.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import time
from dataclasses import asdict, dataclass

from google import genai
from google.genai import types
from openai import OpenAI

REPO = pathlib.Path(__file__).resolve().parent.parent

# --- prompts -----------------------------------------------------------------

REVIEW_PROMPT = """\
Write a comprehensive, detailed review article based on this audio (a talk,
lecture, or podcast). Cover every substantive point the speaker makes:
- The main thesis and supporting arguments.
- All examples, anecdotes, and analogies.
- Every quantitative claim (numbers, dates, percentages, model names).
- Notable quotes attributed to the speaker.
- Any framework, taxonomy, or step-by-step procedure they describe.

Write it as a faithful prose summary. Be exhaustive on the substantive points
but don't add anything not stated by the speaker. Do not speculate, do not
embellish, do not add framing context."""


MEETING_MINUTES_PROMPT = """\
Generate detailed meeting minutes based on this audio recording. Structure:

1. PARTICIPANTS — identify each distinct speaker (name if introduced, else
   "Speaker A", "Speaker B"). For each, note their role if mentioned.
2. TOPICS DISCUSSED — for each topic, summarize the substantive content
   covered, who introduced it, and key points raised.
3. DECISIONS — any explicit decisions, agreements, or conclusions reached.
4. ACTION ITEMS — any tasks, commitments, or follow-ups assigned, with
   the owner if stated.
5. NOTABLE QUOTES — verbatim quotes (≤30 words) that capture key positions
   or memorable phrasings, attributed to the speaker.
6. UNRESOLVED QUESTIONS — any open issues or disagreements not concluded.

Be faithful to what was said. Attribute every claim to the correct speaker.
Do not invent participants, decisions, or action items. If a section has
no content, write "(none)" for that section."""


PROMPTS_BY_TASK = {
    "review": REVIEW_PROMPT,
    "meeting_minutes": MEETING_MINUTES_PROMPT,
}


REFERENCE_TRANSCRIPTION_PROMPT = """\
Transcribe this audio recording in full. Capture every spoken sentence,
including disfluencies (um, uh), repetitions, and false starts. Identify
speaker changes when audible (label as Speaker 1, Speaker 2, etc.). Output
plain text only; do not summarize, paraphrase, or add commentary."""


C1_PASS1_PROMPT = REFERENCE_TRANSCRIPTION_PROMPT  # same prompt; same model


def pass2_review_prompt(transcript: str, task_prompt: str = REVIEW_PROMPT) -> str:
    return (
        "Below is a verbatim transcript of an audio recording. "
        "Use ONLY this transcript to write the requested output — do not assume "
        "anything not present here.\n\n"
        f"<transcript>\n{transcript}\n</transcript>\n\n"
        f"Task:\n{task_prompt}"
    )


PROBE_EXTRACTION_PROMPT = """\
You are extracting specific factual probes from a TRANSCRIPT of a talk or
lecture. A downstream step will use these probes to test whether a
generated review article preserves the speaker's substantive points.

Extract 30-50 concrete, atomic factual probes. Each probe must be:
- A single specific factual assertion (one fact per probe).
- Concrete: name, number, date, ratio, model identifier, named procedure, etc.
- Verifiable by inspection of the transcript: a downstream judge can mark
  it COVERED or MISSING in a paraphrase.
- Diverse: cover early, middle, and late portions of the talk; cover quotes,
  examples, statistics, and procedural claims.

Avoid generic framing claims like "the speaker discusses X" — those are not
probes. Only specific assertions count.

Output strict JSON:
{"probes": [{"id": "p001", "fact": "<atomic fact>"}, ...]}

TRANSCRIPT:
<<<
{transcript}
>>>

JSON output:"""


HALLUCINATION_PROMPT = """\
You are a hallucination judge. Given a REVIEW article and the REFERENCE
TRANSCRIPT it should be faithful to, identify every claim in the REVIEW
that is NOT supported by the TRANSCRIPT.

A claim is "unsupported" if the transcript does not say it (verbatim or
clear paraphrase). Claims that contradict the transcript are also unsupported.

Be strict: any fabricated detail, embellished number, attributed quote not
in the transcript, or invented context is a hallucination. The transcript
may have transcription errors; treat them as the ground truth anyway.

Common-knowledge framing ("this is about machine learning") is exempt unless
it makes a specific factual claim about what the speaker said.

Output strict JSON:
{"unsupported_claims": [
   {"claim": "<exact text or close paraphrase from review>",
    "reason": "<why it is unsupported>"},
   ...
 ]}
If the review is fully faithful, output {"unsupported_claims": []}.

REFERENCE TRANSCRIPT:
<<<
{transcript}
>>>

REVIEW ARTICLE:
<<<
{review}
>>>

JSON output:"""


PROBE_CHECK_PROMPT = """\
You are checking whether a REVIEW ARTICLE covers a list of factual PROBES
extracted from the original transcript.

For each probe, mark COVERED if the review states or clearly paraphrases
the same fact, and MISSING otherwise.

Output strict JSON:
{"results": [
   {"id": "<probe id>",
    "fact": "<probe text>",
    "status": "COVERED|MISSING",
    "evidence": "<short quote from review if covered, or empty string>"},
   ...
 ]}

PROBES:
<<<
{probes_json}
>>>

REVIEW ARTICLE:
<<<
{review}
>>>

JSON output:"""


# --- API callers -------------------------------------------------------------

def call_gemini(prompt: str, audio_path: str | None, model: str, max_output_tokens: int = 65_536):
    """Single Gemini call with optional audio attached — used for C0 review."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    parts: list = [prompt]
    if audio_path is not None:
        ext = pathlib.Path(audio_path).suffix.lstrip(".").lower()
        mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg"}.get(ext, "audio/mpeg")
        parts.append(types.Part.from_bytes(data=pathlib.Path(audio_path).read_bytes(), mime_type=mime))
    t0 = time.time()
    resp = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.0, top_p=1.0, max_output_tokens=max_output_tokens
        ),
    )
    ms = int((time.time() - t0) * 1000)
    text = (resp.text or "").strip()
    if not text:
        cand = resp.candidates[0] if resp.candidates else None
        fr = getattr(cand, "finish_reason", "?") if cand else "?"
        u = resp.usage_metadata
        print(f"      [warn] empty Gemini response; finish_reason={fr}; usage={u}", flush=True)
    return text, ms


def call_gemini_chunked_audio(
    audio_path: str,
    model: str,
    chunk_seconds: int = 1800,  # 30 min default
    overlap_seconds: int = 5,
    workdir: pathlib.Path | None = None,
) -> tuple[str, int]:
    """Chunked audio transcription: split with ffmpeg, transcribe each chunk,
    concatenate. Avoids the long-input degenerate-loop and attention-decay
    failure modes on multi-hour audio.

    Returns (concatenated_transcript, total_ms).
    """
    import subprocess
    import shutil

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found; chunked audio needs it")

    audio_p = pathlib.Path(audio_path)
    workdir = workdir or audio_p.parent / f".chunks_{audio_p.stem}_{int(time.time())}"
    workdir.mkdir(parents=True, exist_ok=True)

    # Duration
    dur_str = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_p)],
        capture_output=True, text=True,
    ).stdout.strip()
    duration = float(dur_str) if dur_str else 0.0
    if duration <= 0:
        raise RuntimeError(f"Could not determine duration of {audio_p}")

    n_chunks = max(1, int((duration - 1) // chunk_seconds) + 1)
    print(f"      [chunk] duration {duration:.0f}s, splitting into {n_chunks} chunk(s) of {chunk_seconds}s + {overlap_seconds}s overlap", flush=True)

    chunk_paths: list[pathlib.Path] = []
    for i in range(n_chunks):
        start = max(0, i * chunk_seconds - (overlap_seconds if i > 0 else 0))
        end = min(duration, (i + 1) * chunk_seconds)
        out = workdir / f"chunk_{i:02d}.mp3"
        if not out.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-i", str(audio_p), "-ss", str(start), "-to", str(end),
                 "-c:a", "libmp3lame", "-b:a", "32k", str(out)],
                check=True,
            )
        chunk_paths.append(out)

    # Transcribe each chunk
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    chunk_prompt = (
        "Transcribe this audio segment in full. Capture every spoken sentence "
        "verbatim, including disfluencies and false starts. Identify speaker "
        "changes when audible. Output plain text only; do not summarize or paraphrase."
    )
    pieces: list[str] = []
    total_ms = 0
    for i, cp in enumerate(chunk_paths):
        parts: list = [chunk_prompt]
        ext = cp.suffix.lstrip(".").lower()
        mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg"}.get(ext, "audio/mpeg")
        parts.append(types.Part.from_bytes(data=cp.read_bytes(), mime_type=mime))
        t0 = time.time()
        try:
            resp = client.models.generate_content(
                model=model, contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0.0, top_p=1.0, max_output_tokens=65_536,
                ),
            )
            chunk_text = (resp.text or "").strip()
        except Exception as e:
            chunk_text = ""
            print(f"        [warn] chunk {i+1}/{n_chunks} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
        chunk_ms = int((time.time() - t0) * 1000)
        total_ms += chunk_ms
        marker_start = i * chunk_seconds
        marker_end = min(duration, (i + 1) * chunk_seconds)
        pieces.append(f"=== chunk {i+1}/{n_chunks} ({marker_start:.0f}-{marker_end:.0f}s) ===\n{chunk_text or '(empty)'}")
        print(f"      [chunk {i+1}/{n_chunks}] {chunk_ms/1000:.1f}s, {len(chunk_text.split())} words", flush=True)

    return "\n\n".join(pieces), total_ms


def call_gpt5_judge(prompt: str, max_completion_tokens: int = 32_768) -> tuple[str, int]:
    """GPT-5.4 with reasoning_effort='high' — used for probe extraction & judging.

    Routes via OpenRouter when CASCADE_USE_OPENROUTER=1 (the OPENAI_API_KEY in this
    environment has insufficient scope; OpenRouter has working access).
    Retries up to 3 times on empty responses (GPT-5.4 reasoning sometimes returns
    empty content when reasoning budget consumes the whole completion budget).
    """
    if os.environ.get("CASCADE_USE_OPENROUTER", "1") == "1":
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        model = "openai/gpt-5.4"
        kwargs = {"max_tokens": max_completion_tokens, "reasoning_effort": "high"}
    else:
        client = OpenAI()
        model = "gpt-5.4"
        kwargs = {"max_completion_tokens": max_completion_tokens, "reasoning_effort": "high"}
    t0 = time.time()
    text = ""
    for attempt in range(3):
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        text = (r.choices[0].message.content or "").strip()
        if text:
            break
        print(f"      [warn] judge returned empty on attempt {attempt+1}/3; retrying", flush=True)
    ms = int((time.time() - t0) * 1000)
    return text, ms


# --- JSON parsing ------------------------------------------------------------

def parse_json(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*\n?", "", t)
    t = re.sub(r"\n?\s*```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start_obj, start_arr = t.find("{"), t.find("[")
    starts = [x for x in [start_obj, start_arr] if x != -1]
    if not starts:
        raise ValueError(f"no JSON in response. first 300: {text[:300]!r}")
    start = min(starts)
    depth, in_str, esc, end = 0, False, False, None
    open_ch, close_ch = t[start], ("}" if t[start] == "{" else "]")
    for i in range(start, len(t)):
        c = t[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        # Truncated JSON — salvage what we can by finding the last complete object/element.
        # Useful when judge's reasoning + JSON exceeded the completion budget.
        salvaged = _salvage_truncated(t[start:])
        if salvaged is not None:
            print(f"      [warn] judge JSON truncated; salvaged partial parse", flush=True)
            return salvaged
        raise ValueError(f"unbalanced JSON. first 300: {text[:300]!r}")
    return json.loads(t[start:end])


def _salvage_truncated(s: str):
    """Salvage a partial JSON object that was cut mid-stream.
    Walks the string forward and finds the last position where the JSON parses cleanly
    after closing any open brackets/braces. Returns the parsed object or None.
    """
    # Strategy: try truncating progressively from the end, attempting to close
    # any open structures, and parse. Return the best partial.
    if not s or s[0] not in "[{":
        return None
    # Find the last comma or `]`/`}` followed by valid context, then close
    last_known_good_idx = None
    depth_stack = []
    in_str = False
    esc = False
    for i, c in enumerate(s):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c in "[{":
            depth_stack.append(c)
        elif c in "]}":
            if depth_stack:
                depth_stack.pop()
        # After a closed element, this is a safe restart point
        if not in_str and c in "]}" and depth_stack:
            last_known_good_idx = i + 1
    # Try to construct a closing tail
    if last_known_good_idx is None:
        return None
    head = s[:last_known_good_idx]
    # Close any remaining open structures
    # Re-scan to find depth at last_known_good_idx
    remaining = list(depth_stack)
    # Need to scan head to count remaining stack
    rem_stack = []
    in_str = False
    esc = False
    for c in head:
        if esc:
            esc = False; continue
        if c == "\\":
            esc = True; continue
        if c == '"':
            in_str = not in_str; continue
        if in_str: continue
        if c in "[{":
            rem_stack.append(c)
        elif c in "]}":
            if rem_stack: rem_stack.pop()
    closer = "".join("]" if x == "[" else "}" for x in reversed(rem_stack))
    candidate = head + closer
    try:
        return json.loads(candidate)
    except Exception:
        return None


# --- pipeline ----------------------------------------------------------------

@dataclass
class CellScore:
    condition: str
    n_unsupported: int
    n_probes: int
    n_covered: int
    halluc_score: int  # 0 if any hallucination, else 1
    probe_coverage: float  # 0..1
    final_score: float  # halluc_score * probe_coverage


def score_review(
    review_text: str,
    reference_transcript: str,
    probes: list[dict],
    label: str,
    out_dir: pathlib.Path,
) -> CellScore:
    print(f"  [{label}] hallucination check...", flush=True)
    hp = HALLUCINATION_PROMPT.replace("{transcript}", reference_transcript[:120_000]).replace("{review}", review_text)
    halluc_text, _ = call_gpt5_judge(hp)
    halluc_data = parse_json(halluc_text)
    unsupported = halluc_data.get("unsupported_claims", [])
    n_unsupp = len(unsupported)
    halluc_score = 0 if n_unsupp > 0 else 1
    print(f"    {label}: unsupported = {n_unsupp}", flush=True)
    (out_dir / f"judge_halluc_{label}.json").write_text(json.dumps({
        "label": label,
        "n_unsupported": n_unsupp,
        "unsupported_claims": unsupported,
    }, indent=2))

    print(f"  [{label}] probe coverage check ({len(probes)} probes)...", flush=True)
    pp = PROBE_CHECK_PROMPT.replace("{probes_json}", json.dumps(probes, indent=2)).replace("{review}", review_text)
    probe_text, _ = call_gpt5_judge(pp)
    probe_data = parse_json(probe_text)
    results = probe_data.get("results", [])
    n_covered = sum(1 for r in results if r.get("status") == "COVERED")
    cov = n_covered / max(1, len(results))
    print(f"    {label}: covered = {n_covered}/{len(results)} = {cov:.3f}", flush=True)
    (out_dir / f"judge_probes_{label}.json").write_text(json.dumps({
        "label": label,
        "n_probes": len(results),
        "n_covered": n_covered,
        "coverage": cov,
        "results": results,
    }, indent=2))

    final = halluc_score * cov
    return CellScore(
        condition=label,
        n_unsupported=n_unsupp,
        n_probes=len(results),
        n_covered=n_covered,
        halluc_score=halluc_score,
        probe_coverage=cov,
        final_score=final,
    )


def run(
    audio_path: pathlib.Path,
    audio_id: str,
    title: str,
    out_dir: pathlib.Path,
    pro_model: str = "gemini-3.1-pro-preview",
    flash_model: str = "gemini-3-flash-preview",
    task: str = "review",
):
    out_dir.mkdir(parents=True, exist_ok=True)
    task_prompt = PROMPTS_BY_TASK.get(task, REVIEW_PROMPT)
    print(f"[run_dir] {out_dir}", flush=True)
    print(f"[audio]   {audio_path}  ({title})  [task={task}]", flush=True)

    # 1. Reference transcript — chunked (default 30-min chunks)
    ref_path = out_dir / "reference_transcript.txt"
    if ref_path.exists():
        print(f"  [ref] already exists ({ref_path.stat().st_size} bytes), reusing", flush=True)
        reference = ref_path.read_text()
    else:
        print(f"  [ref] generating with {flash_model} (chunked, 30min/call)...", flush=True)
        reference, ms = call_gemini_chunked_audio(str(audio_path), flash_model)
        ref_path.write_text(reference)
        print(f"    ref: {len(reference.split())} words ({ms/1000:.1f}s)", flush=True)
    if not reference or len(reference.split()) < 50:
        raise RuntimeError(f"Reference transcript too short ({len(reference.split())} words).")

    # 2. C0: end-to-end review
    c0_path = out_dir / "review_C0.txt"
    if c0_path.exists():
        print(f"  [C0] already exists, reusing", flush=True)
        review_c0 = c0_path.read_text()
    else:
        print(f"  [C0] {pro_model} end-to-end {task}...", flush=True)
        review_c0, ms = call_gemini(task_prompt, str(audio_path), pro_model)
        c0_path.write_text(review_c0)
        print(f"    C0: {len(review_c0.split())} words ({ms/1000:.1f}s)", flush=True)

    # 3. C1: cascade — Pass-1 transcribe with Pro (chunked)
    c1p1_path = out_dir / "transcript_C1_pass1.txt"
    if c1p1_path.exists():
        print(f"  [C1.p1] already exists, reusing", flush=True)
        c1_pass1 = c1p1_path.read_text()
    else:
        print(f"  [C1.p1] {pro_model} transcribe (chunked, 30min/call)...", flush=True)
        c1_pass1, ms = call_gemini_chunked_audio(str(audio_path), pro_model)
        c1p1_path.write_text(c1_pass1)
        print(f"    C1.p1: {len(c1_pass1.split())} words ({ms/1000:.1f}s)", flush=True)

    # 3b. C1 Pass-2: summarize transcript (no audio)
    c1_path = out_dir / "review_C1.txt"
    if c1_path.exists():
        print(f"  [C1.p2] already exists, reusing", flush=True)
        review_c1 = c1_path.read_text()
    else:
        if not c1_pass1:
            raise RuntimeError("C1 Pass-1 transcript is empty — cannot run Pass-2.")
        print(f"  [C1.p2] {pro_model} {task} from transcript...", flush=True)
        review_c1, ms = call_gemini(pass2_review_prompt(c1_pass1, task_prompt), None, pro_model)
        c1_path.write_text(review_c1)
        print(f"    C1: {len(review_c1.split())} words ({ms/1000:.1f}s)", flush=True)

    # 4. Probe extraction with GPT-5.4
    probes_path = out_dir / "probes.json"
    if probes_path.exists():
        print(f"  [probes] already exist, reusing", flush=True)
        probes = json.loads(probes_path.read_text()).get("probes", [])
    else:
        print(f"  [probes] extracting with GPT-5.4...", flush=True)
        pe = PROBE_EXTRACTION_PROMPT.replace("{transcript}", reference[:120_000])
        probe_text, ms = call_gpt5_judge(pe, max_completion_tokens=16_384)
        probe_data = parse_json(probe_text)
        probes = probe_data.get("probes", [])
        probes_path.write_text(json.dumps({"probes": probes}, indent=2))
        print(f"    probes: {len(probes)} extracted ({ms/1000:.1f}s)", flush=True)

    # 5. Score each review
    score_c0 = score_review(review_c0, reference, probes, "C0", out_dir)
    score_c1 = score_review(review_c1, reference, probes, "C1", out_dir)

    summary = {
        "audio_id": audio_id,
        "title": title,
        "audio_path": str(audio_path),
        "models": {
            "reference_transcript": flash_model,
            "review_under_test": pro_model,
            "judge": "gpt-5.4 (reasoning_effort=high)",
        },
        "reference_word_count": len(reference.split()),
        "review_C0_word_count": len(review_c0.split()),
        "review_C1_word_count": len(review_c1.split()),
        "transcript_C1_pass1_word_count": len(c1_pass1.split()),
        "n_probes": len(probes),
        "scores": {
            "C0": asdict(score_c0),
            "C1": asdict(score_c1),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n=== Summary ({audio_id}) ===", flush=True)
    for s in [score_c0, score_c1]:
        print(
            f"  {s.condition}  halluc_score={s.halluc_score} (unsupported={s.n_unsupported})  "
            f"probe_cov={s.probe_coverage:.3f} ({s.n_covered}/{s.n_probes})  "
            f"final={s.final_score:.3f}",
            flush=True,
        )
    print(f"[wrote] {out_dir}/summary.json", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", type=pathlib.Path, required=True)
    ap.add_argument("--id", required=True, help="Short identifier, used in run-dir name")
    ap.add_argument("--title", default="")
    ap.add_argument("--pro-model", default="gemini-3.1-pro-preview")
    ap.add_argument("--flash-model", default="gemini-3.1-pro-preview")
    ap.add_argument("--task", choices=list(PROMPTS_BY_TASK), default="review",
                    help="Output task type: 'review' (long-form review article) or "
                    "'meeting_minutes' (structured minutes for multi-speaker audio)")
    ap.add_argument("--run-dir", type=pathlib.Path, default=None)
    args = ap.parse_args()

    out_dir = args.run_dir or REPO / "runs" / f"audio-{args.task}-{args.id}-{int(time.time())}"
    run(args.audio, args.id, args.title or args.id, out_dir,
        args.pro_model, args.flash_model, task=args.task)


if __name__ == "__main__":
    main()
