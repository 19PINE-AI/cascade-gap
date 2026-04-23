"""Alphabet-match validation: re-run MMAR music-heavy items with
audio_music.md schema instead of audio_uas.md.

Identifies music items by keyword match on question and modality=music,
then re-runs only those items at C2 with the music schema. Compares against
the baseline C2 (speech UAS) from the existing Pro run.
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

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = REPO / "data" / "mmar" / "MMAR-main" / "pilot_sample.jsonl"
AUDIO_DIR = REPO / "data" / "mmar" / "MMAR-main" / "audio"
MUSIC_SCHEMA_PATH = REPO / "harness" / "schemas" / "audio_music.md"


def music_pass1_prompt():
    s = MUSIC_SCHEMA_PATH.read_text()
    m = re.search(r"## Pass-1 prompt\s*```\n(.*?)\n```", s, re.S)
    return m.group(1)


def pass2_prompt(question, choices, perception):
    return (
        f"Below is a structured musical description of an audio clip. Use ONLY the information "
        f"below to answer the question.\n\n<perception>\n{perception}\n</perception>\n\n"
        f"Question: {question}\n"
        f"Choices:\n" + "\n".join(f"  {chr(65+i)}. {c}" for i, c in enumerate(choices)) + "\n\n"
        f"Answer with ONLY the single letter of the correct choice (A, B, C, or D). No explanation."
    )


def score_mcq(item, output_text):
    try:
        correct_idx = item["choices"].index(item["answer"])
    except ValueError:
        return 0.0
    correct_letter = chr(65 + correct_idx)
    m = re.match(r"^[^A-Z]*([A-Z])", output_text.strip().upper())
    if m and m.group(1) == correct_letter:
        return 1.0
    if item["answer"].lower() in output_text.lower():
        return 1.0
    return 0.0


def is_music_item(item):
    # MMAR has modality='music' explicitly. Use that.
    if item.get("modality") == "music":
        return True
    # Also keyword-match questions asking about music, chords, keys, etc.
    q = (item.get("question") or "").lower()
    music_keywords = ["music", "chord", "key of", "instrument", "melody", "harmony",
                      "rhythm", "pitch", "song", "singer", "sing"]
    return any(k in q for k in music_keywords)


def call_gemini(client, model, prompt, audio_bytes):
    contents = [prompt]
    if audio_bytes is not None:
        contents.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"))
    t0 = time.time()
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.0, top_p=1.0, max_output_tokens=2048
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.1-pro-preview")
    ap.add_argument("--run-dir", type=pathlib.Path, default=None)
    args = ap.parse_args()

    run_dir = args.run_dir or REPO / "runs" / f"mmar-music-schema-{args.model}-{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run_dir] {run_dir}")

    items = [json.loads(l) for l in SAMPLE.open()]
    music_items = [it for it in items if is_music_item(it)]
    print(f"[music items] {len(music_items)} of {len(items)}")
    for it in music_items:
        print(f"  - [{it['category']:18s}] {it['id']}  {it['question'][:60]}")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    # Load original Pro run C2 results for comparison
    orig_items = {}
    for line in (REPO / "runs" / "pilot-1776931869" / "items.jsonl").open():
        d = json.loads(line)
        orig_items[d["item_id"]] = d

    results = []
    for i, item in enumerate(music_items):
        audio_path = AUDIO_DIR / pathlib.Path(item["audio_path"]).name
        if not audio_path.exists():
            continue
        audio_bytes = audio_path.read_bytes()
        t0 = time.time()
        try:
            p1_text, p1_in, p1_out, p1_ms = call_gemini(client, args.model, music_pass1_prompt(), audio_bytes)
            p2_text, p2_in, p2_out, p2_ms = call_gemini(
                client, args.model, pass2_prompt(item["question"], item["choices"], p1_text), None
            )
            c2_music_score = score_mcq(item, p2_text)

            # Save calls
            with (run_dir / "calls.jsonl").open("a") as f:
                f.write(json.dumps({
                    "item_id": item["id"], "model": args.model, "condition": "C2-music",
                    "stage": "pass1", "output_text": p1_text, "output_tokens": p1_out, "latency_ms": p1_ms,
                }) + "\n")
                f.write(json.dumps({
                    "item_id": item["id"], "model": args.model, "condition": "C2-music",
                    "stage": "pass2", "output_text": p2_text, "output_tokens": p2_out, "latency_ms": p2_ms,
                }) + "\n")

            orig = orig_items.get(item["id"], {})
            result = {
                "item_id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "answer": item["answer"],
                "C0_score": orig.get("C0_score"),
                "C1_score": orig.get("C1_score"),
                "C2_speech_score": orig.get("C2_score"),
                "C2_music_score": c2_music_score,
                "C2_music_pass1_tokens": p1_out,
                "C2_music_pass1": p1_text[:500],
                "C2_music_answer": p2_text,
            }
            with (run_dir / "items.jsonl").open("a") as f:
                f.write(json.dumps(result) + "\n")
            results.append(result)
            print(
                f"  [{i+1}/{len(music_items)}] {item['id']:40s}  "
                f"C0={orig.get('C0_score', '?')} C1={orig.get('C1_score', '?')} "
                f"C2-speech={orig.get('C2_score', '?')} C2-music={c2_music_score:.0f}  ({int(time.time()-t0)}s)"
            )
        except Exception as e:
            print(f"  [{i+1}] FAILED: {type(e).__name__}: {e}")

    # Summary
    n = len(results)
    if n:
        c0 = sum(r["C0_score"] for r in results if r["C0_score"] is not None) / n
        c1 = sum(r["C1_score"] for r in results if r["C1_score"] is not None) / n
        c2_speech = sum(r["C2_speech_score"] for r in results if r["C2_speech_score"] is not None) / n
        c2_music = sum(r["C2_music_score"] for r in results) / n
        print(f"\n=== Summary (n={n} music items on {args.model}) ===")
        print(f"  C0 (end-to-end):         {c0:.3f}")
        print(f"  C1 (plain cascade):      {c1:.3f}")
        print(f"  C2 (speech UAS):         {c2_speech:.3f}")
        print(f"  C2 (music schema):       {c2_music:.3f}    Δ(music−speech) = {c2_music-c2_speech:+.3f}")
        (run_dir / "summary.json").write_text(json.dumps({
            "model": args.model, "n": n,
            "C0": c0, "C1": c1, "C2_speech": c2_speech, "C2_music": c2_music,
            "delta_music_vs_speech": c2_music - c2_speech,
        }, indent=2))
        print(f"[wrote] {run_dir}/summary.json")


if __name__ == "__main__":
    main()
