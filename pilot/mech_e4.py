"""E4 — DPI / vision-token-count sweep (isolate attention-dilution H3).

Render the SAME paper at several DPIs, run C0 (end-to-end review over page images)
at each, and score. Higher DPI = more vision tokens for identical content. If C0
reasoning quality degrades as token count rises (once pages are legible), that is
evidence for attention dilution (H3) rather than a pure substrate effect.

We capture the actual prompt_token_count per DPI so the x-axis is real vision-token
load, not just DPI. Content is fixed across the sweep, so any monotone trend isolates
the token-count variable.
"""
from __future__ import annotations
import argparse, json, os, sys, pathlib, subprocess, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mech_common as mc
from pilot_audio_review import REVIEW_PROMPT
from google.genai import types


def render(cell: str, dpi: int) -> list[str]:
    out = mc.MECH / f"dpi_{cell}_{dpi}"
    out.mkdir(parents=True, exist_ok=True)
    existing = sorted(out.glob("p*.png"))
    if existing:
        return [str(p) for p in existing]
    pdf = mc.pdf_path(cell)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(out / "p")], check=True)
    return [str(p) for p in sorted(out.glob("*.png"))]


def c0_with_usage(images: list[str]) -> tuple[str, int, int]:
    client = mc._client()
    parts: list = [REVIEW_PROMPT]
    for ip in images:
        parts.append(types.Part.from_bytes(data=pathlib.Path(ip).read_bytes(), mime_type="image/png"))
    t0 = time.time()
    resp = client.models.generate_content(
        model=mc.PRO, contents=parts,
        config=types.GenerateContentConfig(temperature=0.0, top_p=1.0, max_output_tokens=65_536),
    )
    ms = int((time.time() - t0) * 1000)
    ptok = getattr(resp.usage_metadata, "prompt_token_count", None)
    return (resp.text or "").strip(), ms, ptok


def run_e4(cell: str, dpis: list[int]) -> list[dict]:
    rd, transcript, reference, probes = mc.load_cell(cell)
    rows = []
    for dpi in dpis:
        label = f"E4_{dpi}dpi"
        rev_path = rd / f"review_{label}.txt"
        imgs = render(cell, dpi)
        if rev_path.exists():
            review = rev_path.read_text()
            ptok = None
            print(f"  [{cell}/{label}] reuse review ({len(review.split())}w, {len(imgs)} imgs)", flush=True)
        else:
            review, ms, ptok = c0_with_usage(imgs)
            rev_path.write_text(review)
            print(f"  [{cell}/{label}] {len(imgs)} imgs, prompt_tokens={ptok} -> {len(review.split())}w ({ms/1000:.0f}s)", flush=True)
        if not review.strip():
            rows.append({"cell": cell, "dpi": dpi, "error": "empty (likely payload too large)", "prompt_tokens": ptok})
            continue
        sc = mc.score_and_record(review, reference, probes, label, rd)
        rows.append({"cell": cell, "dpi": dpi, "prompt_tokens": ptok, "n_images": len(imgs),
                     "review_words": len(review.split()), **sc})
        print(f"  => {cell} @{dpi}dpi: {sc['n_unsupported']}h/{sc['coverage']:.2f}cov (tokens={ptok})", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True)
    ap.add_argument("--dpis", default="96,200,300")
    args = ap.parse_args()
    dpis = [int(x) for x in args.dpis.split(",")]
    results = []
    for c in args.cells.split(","):
        try:
            results += run_e4(c, dpis)
        except Exception as e:
            print(f"  [{c}/E4] FAILED: {type(e).__name__}: {str(e)[:200]}", flush=True)
    out = mc.MECH / "e4_summary.json"
    prev = json.loads(out.read_text()) if out.exists() else []
    keys = {(r["cell"], r["dpi"]) for r in results}
    prev = [p for p in prev if (p.get("cell"), p.get("dpi")) not in keys]
    out.write_text(json.dumps(prev + results, indent=2))
    print(f"[wrote] {out}", flush=True)
    # also include original 200dpi C0 from the main run for reference
    for c in args.cells.split(","):
        b = mc.existing_c0_c1(mc.run_dir(c))
        print(f"  [orig 200dpi C0 {c}] {b['C0']['n_unsupported']}h/{b['C0']['coverage']}cov", flush=True)


if __name__ == "__main__":
    main()
