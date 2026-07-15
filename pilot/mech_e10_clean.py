"""E10, clean re-run: thinking-budget ladder with a modality-NEUTRAL prompt.

Why: the original review prompt is audio-worded ("based on this audio (a talk,
lecture, or podcast)"). On paper cells (page images) at low thinking budgets,
Gemini notices the mismatch and refuses, producing degenerate 0.00-coverage
outputs that contaminate the ladder. This runner swaps in a modality-neutral
review prompt (identical intent, no "audio" wording) so the same ladder is clean
on papers, and adds a DEF rung (default/uncapped thinking, no thinking_config)
as the natural one-pass anchor.

One cell per process, writing to runs/mechanism/e10_clean/<cell>.json, so many
cells can run in parallel with no write races. Reuses the standard GPT-5.4 judge
via mech_common, so scores are comparable to the C0/C1 cells. Judge artifacts
land under label C0think_<LEVEL>_neu.
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mech_common as mc
from google.genai import types

# Modality-neutral analogue of pilot_audio_review.REVIEW_PROMPT: same instructions,
# no "this audio (a talk, lecture, or podcast)" wording that triggers paper refusals.
NEUTRAL_PROMPT = """\
Write a comprehensive, detailed review article based on the provided source
(a recording or a document). Cover every substantive point the source makes:
- The main thesis and supporting arguments.
- All examples, anecdotes, and analogies.
- Every quantitative claim (numbers, dates, percentages, names).
- Notable quotes.
- Any framework, taxonomy, or step-by-step procedure described.

Write it as a faithful prose summary. Be exhaustive on the substantive points
but don't add anything not stated in the source. Do not speculate, do not
embellish, do not add framing context."""

# DEF = default/uncapped thinking (no thinking_config); then the 256x budget ladder.
BUDGETS = {"DEF": None, "MIN": 128, "MID": 4096, "MAX": 32768}
OUTDIR = mc.MECH / "e10_clean"
OUTDIR.mkdir(parents=True, exist_ok=True)


def gemini_call(prompt, level, *, images=None, audio=None,
                max_output_tokens=65_536, temperature=0.0, retries=4):
    parts = [prompt]
    for ip in (images or []):
        parts.append(types.Part.from_bytes(data=pathlib.Path(ip).read_bytes(), mime_type="image/png"))
    if audio is not None:
        ext = pathlib.Path(audio).suffix.lstrip(".").lower()
        mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg"}.get(ext, "audio/mpeg")
        parts.append(types.Part.from_bytes(data=pathlib.Path(audio).read_bytes(), mime_type=mime))
    budget = BUDGETS[level]
    cfg_kw = dict(temperature=temperature, top_p=1.0, max_output_tokens=max_output_tokens)
    if budget is not None:
        cfg_kw["thinking_config"] = types.ThinkingConfig(thinking_budget=budget, include_thoughts=True)
    cfg = types.GenerateContentConfig(**cfg_kw)
    client = mc._client()
    t0 = time.time()
    last_err = None
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=mc.PRO, contents=parts, config=cfg)
            break
        except Exception as e:
            last_err = e
            wait = min(60, 5 * (2 ** attempt))
            print(f"      [retry {attempt+1}/{retries}] {type(e).__name__}: {str(e)[:120]} (sleep {wait}s)", flush=True)
            time.sleep(wait)
    else:
        raise RuntimeError(f"gemini_call failed after {retries} retries: {last_err}")
    ms = int((time.time() - t0) * 1000)
    answer, thoughts = [], []
    cand = resp.candidates[0] if resp.candidates else None
    if cand and cand.content and cand.content.parts:
        for p in cand.content.parts:
            if getattr(p, "text", None) is None:
                continue
            (thoughts if getattr(p, "thought", False) else answer).append(p.text)
    text = ("".join(answer)).strip() or (resp.text or "").strip()
    um = resp.usage_metadata
    meta = {"ms": ms, "thinking_budget": budget,
            "thoughts_tokens": getattr(um, "thoughts_token_count", None),
            "output_tokens": getattr(um, "candidates_token_count", None),
            "finish_reason": str(getattr(cand, "finish_reason", "?")) if cand else "?"}
    return text, "\n".join(thoughts).strip(), meta


def run_cell_level(cell, level):
    rd, _t, reference, probes = mc.load_cell(cell)
    m = mc.REGISTRY[cell]["modality"]
    label = f"C0think_{level}_neu"
    rev_path = rd / f"review_{label}.txt"
    if rev_path.exists():
        review = rev_path.read_text()
        meta = json.loads((rd / f"meta_{label}.json").read_text()) if (rd / f"meta_{label}.json").exists() else {}
    else:
        kw = dict(images=mc.image_paths(cell)) if m == "paper" else dict(audio=mc.audio_path(cell))
        review, thoughts, meta = gemini_call(NEUTRAL_PROMPT, level, **kw)
        rev_path.write_text(review)
        (rd / f"thoughts_{label}.txt").write_text(thoughts)
        (rd / f"meta_{label}.json").write_text(json.dumps(meta, indent=2))
    base = mc.existing_c0_c1(rd)
    refusal = review.strip().lower().startswith(("i cannot", "i'm sorry", "i am sorry", "i can't"))
    if not review.strip() or refusal:
        return {"cell": cell, "level": level, "error": "empty/refusal", "review_words": len(review.split()),
                "meta": meta, "baseline": base}
    sc = mc.score_and_record(review, reference, probes, label, rd)
    return {"cell": cell, "level": level, "review_words": len(review.split()), **sc,
            "meta": meta, "baseline": base}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    ap.add_argument("--levels", default=",".join(BUDGETS))
    args = ap.parse_args()
    out = OUTDIR / f"{args.cell}.json"
    results = json.loads(out.read_text()) if out.exists() else []
    for level in args.levels.split(","):
        results = [r for r in results if r.get("level") != level]
        t0 = time.time()
        try:
            r = run_cell_level(args.cell, level)
        except Exception as e:
            r = {"cell": args.cell, "level": level, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        results.append(r)
        out.write_text(json.dumps(results, indent=2))
        b = r.get("baseline", {})
        cov = r.get("coverage", r.get("error"))
        print(f"  => {args.cell}/{level}: {cov} | C0={b.get('C0',{}).get('coverage')} "
              f"C1={b.get('C1',{}).get('coverage')} think={r.get('meta',{}).get('thoughts_tokens')} "
              f"({time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
