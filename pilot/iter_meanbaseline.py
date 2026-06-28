"""n=5 multi-seed rerun of plain-C1 and C1_iter on the 7 iterative-refinement
cells, so the iter table reports mean baselines (not single high-end seeds).

For each cell, for seed in 1..5 (T=0.7):
  - plain C1 : Pass-2 review from the cell's own Pass-1 transcript -> judge
  - C1_iter  : extract claims+quotes -> faithfulness filter -> rewrite -> judge
Gemini calls are seeded (temperature=0.7, seed=k). Claude has no seed/temp knob
(deprecated) so its 5 reruns vary by sampling nature, matching how the paper's
other Claude multi-seed envelopes were produced.

Outputs runs/mechanism/iter_meanbaseline_summary.json incrementally (resumable:
a (label) whose judge_*.json already exists is reloaded, not re-run).

Usage:
  python3 pilot/iter_meanbaseline.py            # all cells, seeds 1-5
  python3 pilot/iter_meanbaseline.py --cells natural_vibration_gemini --seeds 1
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from pilot_audio_review import score_review
from pilot_paper_review import pass2_review_prompt
from multi_seed_runner import call_gemini_seeded
from iterative_refinement import (
    CLAIM_EXTRACTION_PROMPT,
    FINAL_REWRITE_PROMPT,
    call_text_only,
    normalize,
    parse_claims_json,
    quote_in_transcript,
)

GEMINI_MODEL = "gemini-3.1-pro-preview"
CLAUDE_MODEL = "claude-opus-4-7"
TEMPERATURE = 0.7

# name -> (run_dir basename glob id, vendor, pass1 transcript file)
CELLS = {
    "natural_vibration_gemini": ("19690013408", "gemini", "transcript_C1_pass1.txt"),
    "heat_pipes_gemini":        ("19700025120", "gemini", "transcript_C1_pass1.txt"),
    "heat_pipes_claude":        ("19700025120", "claude", "transcript_C1_pass1_claude.txt"),
    "fairness_ai_gemini":       ("2605.09852",  "gemini", "transcript_C1_pass1.txt"),
    "fairness_ai_claude":       ("2605.09852",  "claude", "transcript_C1_pass1_claude.txt"),
    "sp5100_claude":            ("19720022550", "claude", "transcript_C1_pass1_claude.txt"),
    "megagauss_claude":         ("2605.11379",  "claude", "transcript_C1_pass1_claude.txt"),
}

OUT = ROOT / "runs" / "mechanism" / "iter_meanbaseline_summary.json"
_lock = threading.Lock()
_results: dict = {}


def run_dir_for(cell_id: str) -> pathlib.Path:
    matches = sorted((ROOT / "runs").glob(f"paper-review-{cell_id}-*"))
    if not matches:
        raise SystemExit(f"no run-dir for {cell_id}")
    return matches[0]


def generate(prompt: str, vendor: str, seed: int) -> str:
    if vendor == "gemini":
        text, _ = call_gemini_seeded(prompt, GEMINI_MODEL, TEMPERATURE, seed)
        return text
    text, _ = call_text_only(prompt, "claude", CLAUDE_MODEL)
    return text


def score_or_reuse(review: str, ref: str, probes: list, label: str, rd: pathlib.Path):
    """Reuse existing judgment if present (resumable); else judge."""
    hp = rd / f"judge_halluc_{label}.json"
    pp = rd / f"judge_probes_{label}.json"
    if hp.exists() and pp.exists():
        h = json.loads(hp.read_text())["n_unsupported"]
        p = json.loads(pp.read_text())
        return h, p["n_covered"] / max(1, p["n_probes"])
    s = score_review(review, ref, probes, label, rd)
    return s.n_unsupported, s.probe_coverage


def run_plain_c1(cell: str, seed: int, rd: pathlib.Path, vendor: str,
                 transcript: str, ref: str, probes: list):
    label = f"{cell}_C1_mb{seed}"
    rpath = rd / f"review_{label}.txt"
    review = rpath.read_text() if rpath.exists() else None
    if review is None:
        review = generate(pass2_review_prompt(transcript), vendor, seed)
        rpath.write_text(review)
    h, cov = score_or_reuse(review, ref, probes, label, rd)
    return {"halluc": h, "cov": cov, "words": len(review.split())}


def run_c1_iter(cell: str, seed: int, rd: pathlib.Path, vendor: str,
                transcript: str, ref: str, probes: list):
    label = f"{cell}_iter_mb{seed}"
    rpath = rd / f"review_{label}.txt"
    review = rpath.read_text() if rpath.exists() else None
    n_total = n_supported = None
    if review is None:
        raw = generate(CLAIM_EXTRACTION_PROMPT.format(transcript=transcript), vendor, seed)
        claims = parse_claims_json(raw)
        if not claims:
            raise RuntimeError(f"{label}: no claims parsed")
        tnorm = normalize(transcript)
        supported = [c for c in claims if quote_in_transcript((c.get("quote") or "").strip(), tnorm)[0]]
        n_total, n_supported = len(claims), len(supported)
        claims_block = "\n".join(f"- {c['claim_text']}" for c in supported)
        review = generate(FINAL_REWRITE_PROMPT.format(claims_block=claims_block), vendor, seed)
        rpath.write_text(review)
        (rd / f"claims_{label}.json").write_text(json.dumps(
            {"n_total": n_total, "n_supported": n_supported}, indent=2))
    h, cov = score_or_reuse(review, ref, probes, label, rd)
    out = {"halluc": h, "cov": cov, "words": len(review.split())}
    if n_total is not None:
        out["n_claims"] = n_total
        out["n_supported"] = n_supported
    return out


def task(cell: str, seed: int):
    cell_id, vendor, tfile = CELLS[cell]
    rd = run_dir_for(cell_id)
    transcript = (rd / tfile).read_text()
    ref = (rd / "reference_transcript.txt").read_text()
    probes = json.loads((rd / "probes.json").read_text()).get("probes", [])
    c1 = run_plain_c1(cell, seed, rd, vendor, transcript, ref, probes)
    it = run_c1_iter(cell, seed, rd, vendor, transcript, ref, probes)
    with _lock:
        _results.setdefault(cell, {}).setdefault("seeds", {})[str(seed)] = {"C1": c1, "iter": it}
        OUT.write_text(json.dumps(_results, indent=2))
    print(f"[done] {cell} seed{seed}: C1={c1['halluc']}h/{c1['cov']:.2f}  "
          f"iter={it['halluc']}h/{it['cov']:.2f}", flush=True)


def aggregate():
    for cell, d in _results.items():
        seeds = d.get("seeds", {})
        for cond in ("C1", "iter"):
            hs = [seeds[s][cond]["halluc"] for s in seeds]
            cs = [seeds[s][cond]["cov"] for s in seeds]
            if not hs:
                continue
            d.setdefault("agg", {})[cond] = {
                "n": len(hs),
                "halluc_mean": round(statistics.mean(hs), 2),
                "halluc_sd": round(statistics.pstdev(hs), 2) if len(hs) > 1 else 0.0,
                "halluc_vals": hs,
                "cov_mean": round(statistics.mean(cs), 3),
                "cov_sd": round(statistics.pstdev(cs), 3) if len(cs) > 1 else 0.0,
                "cov_vals": [round(c, 3) for c in cs],
            }
        if "agg" in d and "C1" in d["agg"] and "iter" in d["agg"]:
            a = d["agg"]
            d["agg"]["delta_halluc"] = round(a["iter"]["halluc_mean"] - a["C1"]["halluc_mean"], 2)
            d["agg"]["delta_cov"] = round(a["iter"]["cov_mean"] - a["C1"]["cov_mean"], 3)
    with _lock:
        OUT.write_text(json.dumps(_results, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", nargs="*", default=list(CELLS))
    ap.add_argument("--seeds", nargs="*", type=int, default=[1, 2, 3, 4, 5])
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    if OUT.exists():
        _results.update(json.loads(OUT.read_text()))

    jobs = [(c, s) for c in args.cells for s in args.seeds]
    print(f"[start] {len(jobs)} (cell,seed) tasks, {args.workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(task, c, s): (c, s) for c, s in jobs}
        for f in as_completed(futs):
            c, s = futs[f]
            try:
                f.result()
            except Exception:
                print(f"[ERROR] {c} seed{s}:\n{traceback.format_exc()}", flush=True)
    aggregate()
    print(f"[aggregate] written to {OUT}", flush=True)
    for cell, d in _results.items():
        a = d.get("agg", {})
        if "C1" in a and "iter" in a:
            print(f"  {cell:28s} C1 {a['C1']['halluc_mean']:5.1f}h/{a['C1']['cov_mean']:.2f}  "
                  f"iter {a['iter']['halluc_mean']:5.1f}h/{a['iter']['cov_mean']:.2f}  "
                  f"dH={a['delta_halluc']:+.1f} dC={a['delta_cov']:+.3f}", flush=True)


if __name__ == "__main__":
    main()
