"""E5 — native-text control (papers).

Feed the paper's *native digital text* (pdftotext) to a single text-only review
call (C0_text), and compare to:
  - C0  (reason over page images, end-to-end)
  - C1  (reason over the model's own OCR transcript)

If C0_text ~= C1 >> C0(images), the image RENDERING was the bottleneck, not the
pass count or OCR quality => clean support for the text-substrate account (H1),
and a direct test of the boundary claim that text-native sources need no cascade.

Only meaningful for born-digital PDFs (clean text layer). NASA scans have an
OCR'd text layer of uncertain quality; we run E5 on the arxiv (born-digital)
cells and report the text-layer word count for transparency.
"""
from __future__ import annotations
import argparse, json, sys, pathlib, subprocess, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mech_common as mc
from pilot_paper_review import pass2_review_prompt  # paper Pass-2 wrapper (<document>...)


def pdftotext(pdf: pathlib.Path) -> str:
    return subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout


def run_e5(cell: str) -> dict:
    rd, transcript, reference, probes = mc.load_cell(cell)
    info = mc.REGISTRY[cell]
    native = pdftotext(mc.pdf_path(cell))
    rev_path = rd / "review_E5.txt"
    if rev_path.exists():
        review = rev_path.read_text()
        print(f"  [{cell}/E5] reuse review ({len(review.split())}w)", flush=True)
    else:
        prompt = pass2_review_prompt(native)
        review, ms = mc.gemini_call(prompt)  # text-only, single call
        rev_path.write_text(review)
        print(f"  [{cell}/E5] native_text={len(native.split())}w -> review {len(review.split())}w ({ms/1000:.0f}s)", flush=True)
    sc = mc.score_and_record(review, reference, probes, "E5", rd)
    return {"cell": cell, "exp": "E5", "regime": info["regime"], "born_digital": info["born_digital"],
            "native_text_words": len(native.split()), "review_words": len(review.split()),
            **sc, "baseline": mc.existing_c0_c1(rd)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True, help="comma-separated paper cell keys")
    args = ap.parse_args()
    results = []
    for c in args.cells.split(","):
        t0 = time.time()
        try:
            r = run_e5(c)
            b = r["baseline"]
            print(f"  => {c}: E5(native-text) {r['n_unsupported']}h/{r['coverage']:.2f}cov | "
                  f"C0(img) {b['C0']['n_unsupported']}h/{b['C0']['coverage']} "
                  f"C1(self-OCR) {b['C1']['n_unsupported']}h/{b['C1']['coverage']} ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            r = {"cell": c, "exp": "E5", "error": f"{type(e).__name__}: {str(e)[:200]}"}
            print(f"  [{c}/E5] FAILED: {r['error']}", flush=True)
        results.append(r)
    out = mc.MECH / "e5_summary.json"
    prev = json.loads(out.read_text()) if out.exists() else []
    prev = [p for p in prev if p["cell"] not in {r["cell"] for r in results}]
    out.write_text(json.dumps(prev + results, indent=2))
    print(f"[wrote] {out}", flush=True)


if __name__ == "__main__":
    main()
