"""Long-form audio summarization pilot — probes the scenario where end-to-end
audio models hallucinate on long lectures/podcasts.

Each item is a 15-60 minute audio file with a reference transcript. Conditions:

  C0 — end-to-end: audio + "write a comprehensive summary" → summary.
  C1 — plain cascade: Pass-1 = "transcribe verbatim"; Pass-2 = "summarize".
  C2 — structured cascade: Pass-1 = audio_uas schema with speaker labels +
       topic segments + key-quote extraction; Pass-2 = summarize structured.

Scoring via llm_judge.py against the reference transcript.

Hypothesis per user: on long audio, C0 hallucinates significantly; C1/C2
produce faithful summaries. If precision(C0) << precision(C1) ≈ precision(C2),
the paper's thesis is validated on this boundary case.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import time
from dataclasses import asdict, dataclass

from google import genai
from google.genai import types

from llm_judge import score_coverage, score_faithfulness

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = REPO / "data" / "longform_audio" / "pilot_sample.jsonl"
UAS_SCHEMA_PATH = REPO / "harness" / "schemas" / "audio_uas.md"


SUMMARY_PROMPT = """\
Write a comprehensive summary of this audio (a talk, lecture, or podcast).
Cover:
- The main thesis or argument.
- Key supporting examples, anecdotes, or evidence mentioned.
- Any specific quantitative claims (numbers, statistics, dates).
- Notable quotes or memorable statements (with attribution to the speaker).

Length: 500-800 words. Plain prose. Be faithful to the source — do not
embellish, do not speculate, do not add context that was not stated in the
audio."""


C1_PASS1_PROMPT = """\
Transcribe this audio verbatim. Include disfluencies (um, uh), repetitions,
false starts, and speaker-identification when multiple speakers are audible.
Do NOT summarize. Do NOT paraphrase. Just produce the full transcript."""


def c2_pass1_prompt() -> str:
    schema = UAS_SCHEMA_PATH.read_text()
    m = re.search(r"## Pass-1 prompt.*?```\n(.*?)\n```", schema, re.S)
    base = m.group(1)
    # Adapt for long audio: ask for topic segmentation and quote flags
    return base + "\n\nThis is a long-form recording. In addition to per-segment tags, at the END of the output emit a TOPIC_OUTLINE block with time-stamped topic segments, and a KEY_QUOTES block with 5-10 verbatim quotes the speaker gave."


def pass2_summary_prompt(perception_text: str, rich: bool) -> str:
    header = "Below is a structured audio perception (UAS segments + topic outline + key quotes)." if rich else "Below is a plain-text transcription of an audio clip."
    return (
        f"{header} Use ONLY the information below to write a comprehensive summary.\n\n"
        f"<perception>\n{perception_text}\n</perception>\n\n"
        f"Task:\n{SUMMARY_PROMPT}"
    )


@dataclass
class CallLog:
    item_id: str
    model: str
    condition: str
    stage: str
    prompt_tokens: int
    output_tokens: int
    latency_ms: int
    output_text: str


def call_gemini(client, model, prompt, audio_path):
    parts = [prompt]
    if audio_path:
        data = pathlib.Path(audio_path).read_bytes()
        ext = pathlib.Path(audio_path).suffix.lstrip(".").lower()
        mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg"}.get(ext, "audio/mpeg")
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))
    t0 = time.time()
    resp = client.models.generate_content(
        model=model, contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.0, top_p=1.0, max_output_tokens=32_768
        ),
    )
    ms = int((time.time() - t0) * 1000)
    u = resp.usage_metadata
    return (
        (resp.text or "").strip(),
        getattr(u, "prompt_token_count", 0) or 0,
        getattr(u, "candidates_token_count", 0) or 0,
        ms,
    )


def run_one(client, model: str, item: dict, run_dir: pathlib.Path) -> dict:
    audio_path = item["audio_path"]
    ref_text = pathlib.Path(item["reference_path"]).read_text()

    logs: list[CallLog] = []

    print(f"    [C0] end-to-end summary...")
    c0_text, c0_in, c0_out, c0_ms = call_gemini(
        client, model, SUMMARY_PROMPT, audio_path
    )
    logs.append(CallLog(item["item_id"], model, "C0", "e2e", c0_in, c0_out, c0_ms, c0_text))

    print(f"    [C1.p1] transcribing...")
    p1_text, p1_in, p1_out, p1_ms = call_gemini(client, model, C1_PASS1_PROMPT, audio_path)
    logs.append(CallLog(item["item_id"], model, "C1", "pass1", p1_in, p1_out, p1_ms, p1_text))
    print(f"    [C1.p2] summarizing transcript ({p1_out} tokens)...")
    c1_text, c1_in, c1_out, c1_ms = call_gemini(
        client, model, pass2_summary_prompt(p1_text, rich=False), None
    )
    logs.append(CallLog(item["item_id"], model, "C1", "pass2", c1_in, c1_out, c1_ms, c1_text))

    print(f"    [C2.p1] structured extraction...")
    p2_text, p2_in, p2_out, p2_ms = call_gemini(client, model, c2_pass1_prompt(), audio_path)
    logs.append(CallLog(item["item_id"], model, "C2", "pass1", p2_in, p2_out, p2_ms, p2_text))
    print(f"    [C2.p2] summarizing structured ({p2_out} tokens)...")
    c2_text, c2_in, c2_out, c2_ms = call_gemini(
        client, model, pass2_summary_prompt(p2_text, rich=True), None
    )
    logs.append(CallLog(item["item_id"], model, "C2", "pass2", c2_in, c2_out, c2_ms, c2_text))

    with (run_dir / "calls.jsonl").open("a") as f:
        for log in logs:
            f.write(json.dumps(asdict(log)) + "\n")
    for cond, text in [("C0", c0_text), ("C1", c1_text), ("C2", c2_text)]:
        (run_dir / f"summary_{item['item_id']}_{cond}.txt").write_text(text)

    print(f"    [judge] scoring C0...")
    c0_faith = score_faithfulness(c0_text, ref_text)
    c0_cov = score_coverage(c0_text, ref_text)
    print(f"      C0: {c0_faith.n_supported}/{c0_faith.n_claims} supported, "
          f"{c0_cov['n_covered']}/{c0_cov['n_key_claims']} covered")
    print(f"    [judge] scoring C1...")
    c1_faith = score_faithfulness(c1_text, ref_text)
    c1_cov = score_coverage(c1_text, ref_text)
    print(f"      C1: {c1_faith.n_supported}/{c1_faith.n_claims} supported, "
          f"{c1_cov['n_covered']}/{c1_cov['n_key_claims']} covered")
    print(f"    [judge] scoring C2...")
    c2_faith = score_faithfulness(c2_text, ref_text)
    c2_cov = score_coverage(c2_text, ref_text)
    print(f"      C2: {c2_faith.n_supported}/{c2_faith.n_claims} supported, "
          f"{c2_cov['n_covered']}/{c2_cov['n_key_claims']} covered")

    (run_dir / f"judge_{item['item_id']}.json").write_text(json.dumps({
        "C0_faith": asdict(c0_faith), "C0_cov": c0_cov,
        "C1_faith": asdict(c1_faith), "C1_cov": c1_cov,
        "C2_faith": asdict(c2_faith), "C2_cov": c2_cov,
    }, indent=2))

    return {
        "item_id": item["item_id"],
        "title": item["title"],
        "duration_s": item.get("duration_s"),
        **{f"{c}_n_claims": faith.n_claims for c, faith in [("C0", c0_faith), ("C1", c1_faith), ("C2", c2_faith)]},
        **{f"{c}_supported_rate": faith.supported_rate for c, faith in [("C0", c0_faith), ("C1", c1_faith), ("C2", c2_faith)]},
        **{f"{c}_unsupported": faith.n_unsupported for c, faith in [("C0", c0_faith), ("C1", c1_faith), ("C2", c2_faith)]},
        **{f"{c}_contradicted": faith.n_contradicted for c, faith in [("C0", c0_faith), ("C1", c1_faith), ("C2", c2_faith)]},
        **{f"{c}_coverage_rate": cov["coverage_rate"] for c, cov in [("C0", c0_cov), ("C1", c1_cov), ("C2", c2_cov)]},
        "C0_out_tokens": c0_out,
        "C1_pass1_tokens": p1_out, "C1_pass2_tokens": c1_out,
        "C2_pass1_tokens": p2_out, "C2_pass2_tokens": c2_out,
        "C0_ms": c0_ms,
        "C1_ms": p1_ms + c1_ms,
        "C2_ms": p2_ms + c2_ms,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.1-pro-preview")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--run-dir", type=pathlib.Path, default=None)
    args = ap.parse_args()

    run_dir = args.run_dir or REPO / "runs" / f"longform-audio-{args.model}-{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run_dir] {run_dir}")

    items = [json.loads(l) for l in SAMPLE.open()]
    if args.limit > 0:
        items = items[: args.limit]
    print(f"[items] {len(items)}")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    results = []
    for i, item in enumerate(items):
        print(f"\n  [{i+1}/{len(items)}] {item['item_id']} ({item.get('duration_s', '?')}s, {item['title']})")
        t0 = time.time()
        try:
            r = run_one(client, args.model, item, run_dir)
        except Exception as e:
            print(f"    FAILED: {type(e).__name__}: {str(e)[:200]}")
            r = {"item_id": item["item_id"], "error": str(e)}
        results.append(r)
        print(f"    ({int(time.time()-t0)}s)")
        with (run_dir / "items.jsonl").open("a") as f:
            f.write(json.dumps(r) + "\n")

    valid = [r for r in results if "error" not in r]
    print(f"\n=== Aggregate === N={len(valid)} errors={len(results)-len(valid)}")
    for cond in ["C0", "C1", "C2"]:
        if not valid:
            continue
        supp = sum(r[f"{cond}_supported_rate"] for r in valid) / len(valid)
        unsup = sum(r[f"{cond}_unsupported"] for r in valid)
        cont = sum(r[f"{cond}_contradicted"] for r in valid)
        cov = sum(r[f"{cond}_coverage_rate"] for r in valid) / len(valid)
        lat = sum(r[f"{cond}_ms"] for r in valid) / len(valid) / 1000
        print(f"  {cond}  precision={supp:.3f}  hallucinated={unsup}  contradicted={cont}  coverage={cov:.3f}  lat={lat:.1f}s")

    summary = {
        "model": args.model, "n": len(valid),
        "by_condition": {
            cond: {
                "precision": sum(r[f"{cond}_supported_rate"] for r in valid) / len(valid) if valid else 0,
                "total_hallucinated": sum(r[f"{cond}_unsupported"] for r in valid),
                "total_contradicted": sum(r[f"{cond}_contradicted"] for r in valid),
                "coverage": sum(r[f"{cond}_coverage_rate"] for r in valid) / len(valid) if valid else 0,
                "lat_s": sum(r[f"{cond}_ms"] for r in valid) / len(valid) / 1000 if valid else 0,
            } for cond in ["C0", "C1", "C2"]
        }
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[wrote] {run_dir}/summary.json")


if __name__ == "__main__":
    main()
