"""E1 (both-condition C1+) and E2 (single-call interleaved).

E1 — C1+: the reasoning/write step gets BOTH the model's own transcript AND the
raw modality attached. Discriminates:
  C1+ ~= C1 >> C0  -> pixels redundant once text present  => externalization (H2)
  C1+ ~= C0 <  C1  -> pixels poison reasoning even w/ text => substrate/dilution (H1/H3)
  C1+ >  C1        -> modality still adds value           => weak thesis

E2 — single call: modality attached, model told to FIRST transcribe verbatim,
THEN write the review, all in one completion. Tests whether the benefit is the
externalized-text scratchpad (E2 ~= C1) vs. the two-pass split / modality removal
(E2 < C1).

Both reuse REVIEW_PROMPT and the GPT-5.4 judge. Results -> runs/mechanism/<exp>_summary.json
and judge_*_<LABEL>.json inside each run dir.
"""
from __future__ import annotations
import argparse, json, sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pilot_audio_review import REVIEW_PROMPT
import mech_common as mc


def e1_prompt(transcript: str, modality: str) -> str:
    src = "audio recording" if modality == "audio" else "multi-page document (page images)"
    tag = "transcript" if modality == "audio" else "document"
    return (
        f"You are given a {src} (attached) AND a verbatim "
        f"{'transcript' if modality=='audio' else 'OCR transcript'} of that same source. "
        "Use BOTH the attached source and the transcript together to write the requested output.\n\n"
        f"<{tag}>\n{transcript}\n</{tag}>\n\n"
        f"Task:\n{REVIEW_PROMPT}"
    )


def e2_prompt(modality: str) -> str:
    if modality == "audio":
        step1 = ("STEP 1 — Transcribe: transcribe the full audio verbatim, capturing every "
                 "spoken sentence, including disfluencies and false starts.")
        src = "an audio recording (attached)"
    else:
        step1 = ("STEP 1 — Transcribe: OCR the full text of the document verbatim, page by page, "
                 "in reading order, capturing every paragraph, heading, figure caption, table, and footnote.")
        src = "a multi-page document as page images (attached)"
    return (
        f"You are given {src}. Do the following TWO steps in order, in a SINGLE response:\n\n"
        f"{step1}\n\n"
        "STEP 2 — Review: using ONLY the transcript you just produced in STEP 1, write the review.\n\n"
        "Format your response EXACTLY as:\n"
        "=== TRANSCRIPT ===\n<your verbatim transcript>\n=== REVIEW ===\n<your review>\n\n"
        f"The review task is:\n{REVIEW_PROMPT}"
    )


def run_e1(cell: str) -> dict:
    rd, transcript, reference, probes = mc.load_cell(cell)
    m = mc.REGISTRY[cell]["modality"]
    out_path = rd / "review_E1.txt"
    if out_path.exists():
        review = out_path.read_text()
        print(f"  [{cell}/E1] reuse review ({len(review.split())}w)", flush=True)
    else:
        prompt = e1_prompt(transcript, m)
        kw = dict(images=mc.image_paths(cell)) if m == "paper" else dict(audio=mc.audio_path(cell))
        review, ms = mc.gemini_call(prompt, **kw)
        out_path.write_text(review)
        print(f"  [{cell}/E1] gen {len(review.split())}w ({ms/1000:.0f}s)", flush=True)
    if not review.strip():
        return {"cell": cell, "exp": "E1", "error": "empty generation"}
    sc = mc.score_and_record(review, reference, probes, "E1", rd)
    return {"cell": cell, "exp": "E1", "regime": mc.REGISTRY[cell]["regime"],
            "review_words": len(review.split()), **sc, "baseline": mc.existing_c0_c1(rd)}


def run_e2(cell: str) -> dict:
    rd, transcript, reference, probes = mc.load_cell(cell)
    m = mc.REGISTRY[cell]["modality"]
    raw_path = rd / "raw_E2.txt"
    rev_path = rd / "review_E2.txt"
    if rev_path.exists():
        review = rev_path.read_text()
        raw = raw_path.read_text() if raw_path.exists() else ""
        print(f"  [{cell}/E2] reuse review ({len(review.split())}w)", flush=True)
    else:
        prompt = e2_prompt(m)
        kw = dict(images=mc.image_paths(cell)) if m == "paper" else dict(audio=mc.audio_path(cell))
        raw, ms = mc.gemini_call(prompt, **kw)
        raw_path.write_text(raw)
        if "=== REVIEW ===" in raw:
            review = raw.split("=== REVIEW ===", 1)[1].strip()
            trunc = False
        else:
            review = ""
            trunc = True
        rev_path.write_text(review)
        print(f"  [{cell}/E2] gen raw {len(raw.split())}w -> review {len(review.split())}w "
              f"{'[NO REVIEW MARKER/truncated]' if trunc else ''} ({ms/1000:.0f}s)", flush=True)
    if not review.strip():
        return {"cell": cell, "exp": "E2", "regime": mc.REGISTRY[cell]["regime"],
                "error": "no review section (single-call output budget exceeded by transcript)",
                "raw_words": len(raw.split()), "baseline": mc.existing_c0_c1(rd)}
    sc = mc.score_and_record(review, reference, probes, "E2", rd)
    return {"cell": cell, "exp": "E2", "regime": mc.REGISTRY[cell]["regime"],
            "review_words": len(review.split()), **sc, "baseline": mc.existing_c0_c1(rd)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", choices=["E1", "E2"], required=True)
    ap.add_argument("--cells", required=True, help="comma-separated cell keys, or 'all'")
    args = ap.parse_args()
    cells = list(mc.REGISTRY) if args.cells == "all" else args.cells.split(",")
    fn = run_e1 if args.exp == "E1" else run_e2
    results = []
    for c in cells:
        t0 = time.time()
        try:
            r = fn(c)
        except Exception as e:
            r = {"cell": c, "exp": args.exp, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            print(f"  [{c}/{args.exp}] FAILED: {r['error']}", flush=True)
        results.append(r)
        b = r.get("baseline", {})
        if "coverage" in r:
            print(f"  => {c}: {args.exp} {r['n_unsupported']}h/{r['coverage']:.2f}cov | "
                  f"C0 {b.get('C0',{}).get('n_unsupported')}h/{b.get('C0',{}).get('coverage')} "
                  f"C1 {b.get('C1',{}).get('n_unsupported')}h/{b.get('C1',{}).get('coverage')} "
                  f"({time.time()-t0:.0f}s)", flush=True)
    out = mc.MECH / f"{args.exp.lower()}_summary.json"
    # merge with any existing
    prev = json.loads(out.read_text()) if out.exists() else []
    prev = [p for p in prev if p["cell"] not in {r["cell"] for r in results}]
    out.write_text(json.dumps(prev + results, indent=2))
    print(f"[wrote] {out}", flush=True)


if __name__ == "__main__":
    main()
