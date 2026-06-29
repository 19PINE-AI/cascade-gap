"""Mixed-model audio cascade (off-protocol PRODUCTION probe).

The same-weights cascade is Gemini-only for audio by API constraint (Claude takes
no audio; OpenAI's audio model refuses text-only Pass-2). In production you would
not use one model for everything -- you would use the best model per stage. This
probe does exactly that: an INDEPENDENT non-Google transcript from OpenAI
gpt-audio (Pass-1), then a text-only synthesis Pass-2 by several frontier text
models that cannot touch audio at all on their own (Claude Opus 4.7, GPT-5.4),
plus Gemini for reference. It tests whether decomposition UNLOCKS text-only
frontier models for audio review, and how the mixed pipeline compares to Gemini's
end-to-end C0.

NOT same-weights: this deliberately mixes vendors across stages, so it speaks to
the generality of decomposition, not the paper's same-weights claim.

Judging: GPT-5.4 judge for all (comparable to the rest of the paper), PLUS a
Claude judge cross-check on the GPT-5.4-authored review to rule out self-grading.

Usage:
  python3 pilot/mixed_cascade_audio.py \
    --run-dir runs/audio-review-karpathy_sogpt-1777458038 \
    --audio data/longform_audio/karpathy_sogpt_32k.mp3
"""
from __future__ import annotations
import argparse, base64, json, os, pathlib, subprocess, sys, time
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from anthropic import Anthropic
from openai import OpenAI

from pilot_audio_review import REVIEW_PROMPT, pass2_review_prompt, score_review
from inter_judge_claude import judge_halluc as claude_judge_halluc, judge_probes as claude_judge_probes

GPT_AUDIO = "openai/gpt-audio"
GPT54 = "openai/gpt-5.4"


def _orc():
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])


def gpt_audio_transcribe(audio_path: str, chunk_seconds: int = 720) -> str:
    """Independent Pass-1 transcript from OpenAI gpt-audio, chunked to stay under
    OpenRouter's 10MB base64 cap and any per-call audio-length limit."""
    orc = _orc()
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", audio_path], capture_output=True, text=True).stdout.strip())
    work = pathlib.Path(audio_path).parent / f".chunks_gptaudio_{pathlib.Path(audio_path).stem}"
    work.mkdir(exist_ok=True)
    starts = list(range(0, int(dur), chunk_seconds))
    pieces = []
    for i, start in enumerate(starts):
        end = min(dur, start + chunk_seconds)
        cp = work / f"chunk_{i:02d}.mp3"
        if not cp.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", audio_path, "-ss", str(start),
                            "-to", str(end), "-c:a", "libmp3lame", "-b:a", "32k", str(cp)], check=True)
        b64 = base64.b64encode(cp.read_bytes()).decode()
        txt = ""
        for attempt in range(4):
            try:
                r = orc.chat.completions.create(model=GPT_AUDIO, max_tokens=8000, modalities=["text"],
                    messages=[{"role": "user", "content": [
                        {"type": "input_audio", "input_audio": {"data": b64, "format": "mp3"}},
                        {"type": "text", "text": "Transcribe this audio segment verbatim, in full. "
                                                 "Output only the transcript text, no commentary."}]}])
                txt = (r.choices[0].message.content or "").strip()
                if len(txt.split()) > 20:
                    break
            except Exception as e:
                print(f"      [gpt-audio chunk {i+1} retry {attempt+1}] {str(e)[:90]}", flush=True)
                time.sleep(5 * (2 ** attempt))
        print(f"      [gpt-audio chunk {i+1}/{len(starts)}] {len(txt.split())} words", flush=True)
        pieces.append(txt)
    return "\n\n".join(pieces)


def synth_claude(prompt: str) -> str:
    r = Anthropic().messages.create(model="claude-opus-4-7", max_tokens=8192,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}])
    return "\n".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()


def synth_gpt54(prompt: str) -> str:
    # GPT-5.4 reasoning can consume the whole completion budget and return empty;
    # give it room (24k), use medium effort for a generation task, and retry.
    for attempt in range(4):
        try:
            r = _orc().chat.completions.create(model=GPT54, max_tokens=24000, reasoning_effort="medium",
                messages=[{"role": "user", "content": prompt}])
            txt = (r.choices[0].message.content or "").strip()
            if len(txt.split()) > 50:
                return txt
            print(f"      [gpt54 synth retry {attempt+1}] empty/short ({len(txt.split())} words)", flush=True)
        except Exception as e:
            print(f"      [gpt54 synth retry {attempt+1}] {str(e)[:90]}", flush=True)
        time.sleep(4)
    return ""


def synth_gemini(prompt: str) -> str:
    import google.genai as genai
    from google.genai import types
    c = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    r = c.models.generate_content(model="gemini-3.1-pro-preview", contents=[prompt],
        config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=65536))
    return (r.text or "").strip()


SYNTHS = {"claude": synth_claude, "gpt54": synth_gpt54, "gemini": synth_gemini}


def run(run_dir: pathlib.Path, audio: pathlib.Path):
    reference = (run_dir / "reference_transcript.txt").read_text()
    probes = json.loads((run_dir / "probes.json").read_text()).get("probes", [])
    print(f"[run_dir] {run_dir.name}  ({len(probes)} probes)", flush=True)

    # Pass-1: independent gpt-audio transcript
    p1 = run_dir / "transcript_mix_pass1_gptaudio.txt"
    if p1.exists():
        pass1 = p1.read_text(); print(f"  [Pass-1 gpt-audio] reuse ({len(pass1.split())} words)", flush=True)
    else:
        print("  [Pass-1 gpt-audio] transcribing...", flush=True)
        pass1 = gpt_audio_transcribe(str(audio)); p1.write_text(pass1)
        print(f"    transcript: {len(pass1.split())} words", flush=True)
    if len(pass1.split()) < 100:
        raise RuntimeError("gpt-audio transcript too short")

    prompt = pass2_review_prompt(pass1, REVIEW_PROMPT)
    results = {}
    for name, fn in SYNTHS.items():
        rv_path = run_dir / f"review_mix_{name}.txt"
        if rv_path.exists():
            review = rv_path.read_text(); print(f"  [Pass-2 {name}] reuse", flush=True)
        else:
            print(f"  [Pass-2 {name}] synthesizing...", flush=True)
            review = fn(prompt); rv_path.write_text(review)
            print(f"    {name}: {len(review.split())} words", flush=True)
        # GPT-5.4 judge (standard, comparable across the paper); the judge
        # occasionally emits malformed JSON, so retry a couple of times.
        s = None
        for attempt in range(3):
            try:
                s = score_review(review, reference, probes, f"mix_{name}", run_dir); break
            except Exception as e:
                print(f"    [judge retry {attempt+1}] {type(e).__name__}: {str(e)[:80]}", flush=True)
                time.sleep(3)
        if s is None:
            raise RuntimeError(f"scoring failed for mix_{name}")
        results[name] = {"gpt5_judge": {"n_unsupported": s.n_unsupported, "coverage": round(s.probe_coverage, 3)}}
        # Claude-judge cross-check on the GPT-5.4-authored review (self-grade control)
        if name == "gpt54":
            try:
                ch = claude_judge_halluc(review, reference, run_dir / "judge_halluc_mix_gpt54_claudejudge.json", "mix_gpt54_cj")
                cp = claude_judge_probes(review, probes, run_dir / "judge_probes_mix_gpt54_claudejudge.json", "mix_gpt54_cj")
                results[name]["claude_judge"] = {"n_unsupported": ch.get("n_unsupported"),
                                                 "coverage": round(cp.get("coverage", 0), 3)}
            except Exception as e:
                print(f"    [claude-judge cross-check failed] {str(e)[:80]}", flush=True)

    summary = {"cell": run_dir.name, "pass1": "gpt-audio", "pass1_words": len(pass1.split()), "synth": results}
    (run_dir / "summary_mix.json").write_text(json.dumps(summary, indent=2))
    print(f"\n=== MIXED {run_dir.name} (Pass-1 = gpt-audio) ===", flush=True)
    for name, r in results.items():
        line = f"  Pass-2 {name:7s}  GPT5-judge {r['gpt5_judge']['n_unsupported']}h/{r['gpt5_judge']['coverage']:.3f}"
        if "claude_judge" in r:
            line += f"   Claude-judge {r['claude_judge']['n_unsupported']}h/{r['claude_judge']['coverage']:.3f}"
        print(line, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--audio", type=pathlib.Path, required=True)
    args = ap.parse_args()
    run(args.run_dir, args.audio)


if __name__ == "__main__":
    main()
