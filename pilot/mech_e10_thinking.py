"""E10 — thinking-budget control on C0.

Reviewer objection this answers: "the two-pass win is trivial — you just gave
the model 2x the budget; increase the single pass's thinking budget and it will
recover." Prediction from the generation-load account: it will NOT. The model
will not spontaneously externalize a verbatim transcript inside its reasoning,
so more thinking buys more planning of a satisficed review, not recovery.

Design: keep the C0 configuration IDENTICAL (same REVIEW_PROMPT + raw modality,
same temperature=0, same 65k output cap) and only vary the thinking budget along
a ladder (MINIMAL / LOW / HIGH). If coverage is flat across the whole axis and
stays at C0 level far below C1, "just think more" is ruled out regardless of
where the untuned default sat. We also record thinking-token counts and thought
summaries to check directly whether the reasoning contains the dropped content.

Reuses REVIEW_PROMPT and the GPT-5.4 judge via mech_common, so every review is
scored identically to the original C0/C1 cells. Judge artifacts land in the run
dir under label C0think_<LEVEL>; summary -> runs/mechanism/e10_summary.json.
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pilot_audio_review import REVIEW_PROMPT
import mech_common as mc
from google.genai import types

# Gemini 3.1 Pro accepts thinking_budget in [128, 32768]; ladder spans the full
# 256x range, ceiling included. Labels are stable keys for artifacts/summary.
BUDGETS = {"MIN": 128, "MID": 4096, "MAX": 32768}
LEVELS = list(BUDGETS)  # ascending thinking budget


def gemini_call_think(prompt, level, *, images=None, audio=None,
                      max_output_tokens=65_536, temperature=0.0, retries=4):
    """C0-style single call with an explicit thinking_budget; returns (text, thoughts, meta)."""
    parts = [prompt]
    for ip in (images or []):
        parts.append(types.Part.from_bytes(data=pathlib.Path(ip).read_bytes(), mime_type="image/png"))
    if audio is not None:
        ext = pathlib.Path(audio).suffix.lstrip(".").lower()
        mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg"}.get(ext, "audio/mpeg")
        parts.append(types.Part.from_bytes(data=pathlib.Path(audio).read_bytes(), mime_type=mime))
    cfg = types.GenerateContentConfig(
        temperature=temperature, top_p=1.0, max_output_tokens=max_output_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=BUDGETS[level], include_thoughts=True),
    )
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
        raise RuntimeError(f"gemini_call_think failed after {retries} retries: {last_err}")
    ms = int((time.time() - t0) * 1000)
    # split answer parts from thought-summary parts
    answer, thoughts = [], []
    cand = resp.candidates[0] if resp.candidates else None
    if cand and cand.content and cand.content.parts:
        for p in cand.content.parts:
            if getattr(p, "text", None) is None:
                continue
            (thoughts if getattr(p, "thought", False) else answer).append(p.text)
    text = ("".join(answer)).strip() or (resp.text or "").strip()
    um = resp.usage_metadata
    meta = {
        "ms": ms,
        "thinking_budget": BUDGETS[level],
        "thoughts_tokens": getattr(um, "thoughts_token_count", None),
        "output_tokens": getattr(um, "candidates_token_count", None),
        "finish_reason": str(getattr(cand, "finish_reason", "?")) if cand else "?",
    }
    return text, "\n".join(thoughts).strip(), meta


def run_cell_level(cell: str, level: str) -> dict:
    rd, _transcript, reference, probes = mc.load_cell(cell)
    m = mc.REGISTRY[cell]["modality"]
    label = f"C0think_{level}"
    rev_path = rd / f"review_{label}.txt"
    thought_path = rd / f"thoughts_{label}.txt"
    meta_path = rd / f"meta_{label}.json"
    if rev_path.exists():
        review = rev_path.read_text()
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        print(f"  [{cell}/{level}] reuse review ({len(review.split())}w)", flush=True)
    else:
        kw = dict(images=mc.image_paths(cell)) if m == "paper" else dict(audio=mc.audio_path(cell))
        review, thoughts, meta = gemini_call_think(REVIEW_PROMPT, level, **kw)
        rev_path.write_text(review)
        thought_path.write_text(thoughts)
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"  [{cell}/{level}] gen {len(review.split())}w | think {meta['thoughts_tokens']}tok "
              f"| thought-summary {len(thoughts.split())}w ({meta['ms']/1000:.0f}s)", flush=True)
    base = mc.existing_c0_c1(rd)
    if not review.strip():
        return {"cell": cell, "level": level, "regime": mc.REGISTRY[cell]["regime"],
                "error": "empty review", "meta": meta, "baseline": base}
    sc = mc.score_and_record(review, reference, probes, label, rd)
    return {"cell": cell, "level": level, "regime": mc.REGISTRY[cell]["regime"],
            "review_words": len(review.split()), **sc, "meta": meta, "baseline": base}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="all", help="comma-separated cell keys, or 'all'")
    ap.add_argument("--levels", default=",".join(LEVELS), help="comma-separated thinking levels")
    args = ap.parse_args()
    cells = list(mc.REGISTRY) if args.cells == "all" else args.cells.split(",")
    levels = args.levels.split(",")
    out = mc.MECH / "e10_summary.json"
    results = json.loads(out.read_text()) if out.exists() else []
    for cell in cells:
        for level in levels:
            key = (cell, level)
            results = [r for r in results if (r["cell"], r["level"]) != key]
            t0 = time.time()
            try:
                r = run_cell_level(cell, level)
            except Exception as e:
                r = {"cell": cell, "level": level, "error": f"{type(e).__name__}: {str(e)[:200]}"}
                print(f"  [{cell}/{level}] FAILED: {r['error']}", flush=True)
            results.append(r)
            out.write_text(json.dumps(results, indent=2))
            b = r.get("baseline", {})
            if "coverage" in r:
                print(f"  => {cell}/{level}: {r['n_unsupported']}h/{r['coverage']:.2f}cov "
                      f"| C0 {b.get('C0',{}).get('n_unsupported')}h/{b.get('C0',{}).get('coverage')} "
                      f"C1 {b.get('C1',{}).get('n_unsupported')}h/{b.get('C1',{}).get('coverage')} "
                      f"({time.time()-t0:.0f}s)", flush=True)
    print(f"[wrote] {out}", flush=True)


if __name__ == "__main__":
    main()
