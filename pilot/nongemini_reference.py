"""Non-Gemini reference experiment (paper item #3).

For each (source, reference-generator) we:
  1. Re-transcribe (audio) or re-OCR (paper) with a non-Gemini engine,
     producing reference_alt.txt.
  2. Extract probes from reference_alt.txt with Claude Opus 4.7
     (avoids GPT-bias re-entering through probe extraction).
  3. Re-score the EXISTING review_C0.txt and review_C1.txt against
     reference_alt + Claude-extracted probes, with both judges
     (GPT-5.4 and Claude).
  4. Compare ΔC1-C0 numbers to the original Gemini-reference numbers.

Outputs (per run-dir):
  - reference_alt.txt
  - probes_alt.json
  - judge_halluc_C0_altref_gpt5.json / _claude.json
  - judge_halluc_C1_altref_gpt5.json / _claude.json
  - judge_probes_C0_altref_gpt5.json / _claude.json
  - judge_probes_C1_altref_gpt5.json / _claude.json
  - reference_bias_summary.json

Usage:
  # Audio: Whisper-base via faster-whisper
  python3 pilot/nongemini_reference.py audio \
      --audio data/longform_audio/3blue1brown_attention_16k.mp3 \
      --run-dir runs/audio-review-3b1b_attention-1778857367 \
      --whisper-model base

  # Paper: EasyOCR
  python3 pilot/nongemini_reference.py paper \
      --run-dir runs/paper-review-19720009221-1777458461 \
      --item-id 19720009221
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from pilot_audio_review import (
    HALLUCINATION_PROMPT,
    PROBE_CHECK_PROMPT,
    PROBE_EXTRACTION_PROMPT,
    call_gpt5_judge,
    parse_json,
)
from inter_judge_claude import call_claude_judge


def transcribe_whisper(audio_path: pathlib.Path, model_size: str = "base") -> str:
    from faster_whisper import WhisperModel
    print(f"  [whisper] loading {model_size} (cpu, int8)...", flush=True)
    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=4)
    print(f"  [whisper] transcribing {audio_path.name}...", flush=True)
    t0 = time.time()
    segments, info = model.transcribe(str(audio_path), beam_size=1, vad_filter=False)
    pieces = []
    for seg in segments:
        pieces.append(seg.text.strip())
    elapsed = time.time() - t0
    text = " ".join(p for p in pieces if p)
    print(f"  [whisper] {len(text.split())} words in {elapsed:.0f}s (lang={info.language})", flush=True)
    return text


def ocr_easyocr(image_paths: list[pathlib.Path]) -> str:
    import easyocr
    print(f"  [easyocr] loading reader (en, cpu)...", flush=True)
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    pieces = []
    t0 = time.time()
    for i, ip in enumerate(image_paths, 1):
        t_page = time.time()
        results = reader.readtext(str(ip), detail=0, paragraph=True)
        page_text = "\n".join(results)
        pieces.append(f"=== page {i} ===\n{page_text}")
        print(f"  [easyocr] page {i}/{len(image_paths)}: {len(page_text.split())} words ({time.time()-t_page:.1f}s)", flush=True)
    text = "\n\n".join(pieces)
    print(f"  [easyocr] total {len(text.split())} words in {time.time()-t0:.0f}s", flush=True)
    return text


def extract_probes_claude(reference: str, out_path: pathlib.Path) -> list[dict]:
    if out_path.exists():
        d = json.loads(out_path.read_text())
        return d.get("probes", [])
    prompt = PROBE_EXTRACTION_PROMPT.replace("{transcript}", reference[:120_000])
    print(f"  [probes_alt] extracting via Claude...", flush=True)
    text, ms = call_claude_judge(prompt, max_tokens=16_384)
    probes = parse_json(text).get("probes", [])
    out_path.write_text(json.dumps({
        "probes": probes,
        "extractor": "claude-opus-4-7",
        "elapsed_ms": ms,
    }, indent=2))
    print(f"  [probes_alt] {len(probes)} probes ({ms/1000:.1f}s)", flush=True)
    return probes


def judge_halluc(review: str, reference: str, judge: str, out_path: pathlib.Path, label: str) -> int:
    if out_path.exists():
        return json.loads(out_path.read_text()).get("n_unsupported", -1)
    prompt = HALLUCINATION_PROMPT.replace("{transcript}", reference[:120_000]).replace("{review}", review)
    if judge == "gpt5":
        text, ms = call_gpt5_judge(prompt)
    else:
        text, ms = call_claude_judge(prompt, max_tokens=16_384)
    data = parse_json(text)
    unsupported = data.get("unsupported_claims", [])
    n = len(unsupported)
    out_path.write_text(json.dumps({
        "label": label, "judge": judge, "n_unsupported": n,
        "unsupported_claims": unsupported, "elapsed_ms": ms,
    }, indent=2))
    print(f"  [{label}/{judge}/halluc] n={n} ({ms/1000:.1f}s)", flush=True)
    return n


def judge_probes(review: str, probes: list[dict], judge: str, out_path: pathlib.Path, label: str) -> tuple[int, int]:
    if out_path.exists():
        d = json.loads(out_path.read_text())
        return d.get("n_covered", 0), d.get("n_probes", len(probes))
    prompt = PROBE_CHECK_PROMPT.replace("{probes_json}", json.dumps(probes, indent=2)).replace("{review}", review)
    if judge == "gpt5":
        text, ms = call_gpt5_judge(prompt)
    else:
        text, ms = call_claude_judge(prompt, max_tokens=16_384)
    data = parse_json(text)
    results = data.get("results", [])
    n_cov = sum(1 for r in results if r.get("status") == "COVERED")
    n_pr = len(results)
    out_path.write_text(json.dumps({
        "label": label, "judge": judge, "n_probes": n_pr,
        "n_covered": n_cov, "coverage": n_cov / max(1, n_pr),
        "results": results, "elapsed_ms": ms,
    }, indent=2))
    print(f"  [{label}/{judge}/probes] {n_cov}/{n_pr} cov={n_cov/max(1,n_pr):.3f} ({ms/1000:.1f}s)", flush=True)
    return n_cov, n_pr


def run_one(run_dir: pathlib.Path, reference_alt: str, ref_kind: str) -> dict:
    print(f"\n=== {run_dir.name} (ref={ref_kind}) ===", flush=True)
    (run_dir / "reference_alt.txt").write_text(reference_alt)
    probes_alt = extract_probes_claude(reference_alt, run_dir / "probes_alt.json")

    review_c0 = (run_dir / "review_C0.txt").read_text()
    review_c1 = (run_dir / "review_C1.txt").read_text()

    # All 8 combos: 2 conditions × 2 judges × 2 axes
    h_c0_g = judge_halluc(review_c0, reference_alt, "gpt5",
                          run_dir / "judge_halluc_C0_altref_gpt5.json", "C0")
    h_c1_g = judge_halluc(review_c1, reference_alt, "gpt5",
                          run_dir / "judge_halluc_C1_altref_gpt5.json", "C1")
    h_c0_c = judge_halluc(review_c0, reference_alt, "claude",
                          run_dir / "judge_halluc_C0_altref_claude.json", "C0")
    h_c1_c = judge_halluc(review_c1, reference_alt, "claude",
                          run_dir / "judge_halluc_C1_altref_claude.json", "C1")

    p_c0_g = judge_probes(review_c0, probes_alt, "gpt5",
                          run_dir / "judge_probes_C0_altref_gpt5.json", "C0")
    p_c1_g = judge_probes(review_c1, probes_alt, "gpt5",
                          run_dir / "judge_probes_C1_altref_gpt5.json", "C1")
    p_c0_c = judge_probes(review_c0, probes_alt, "claude",
                          run_dir / "judge_probes_C0_altref_claude.json", "C0")
    p_c1_c = judge_probes(review_c1, probes_alt, "claude",
                          run_dir / "judge_probes_C1_altref_claude.json", "C1")

    # Original (Gemini-reference) numbers from summary.json
    summ = json.loads((run_dir / "summary.json").read_text())
    orig_c0 = summ["scores"]["C0"]
    orig_c1 = summ["scores"]["C1"]

    result = {
        "run_dir": str(run_dir),
        "ref_kind": ref_kind,
        "n_probes_alt": len(probes_alt),
        "n_probes_original_gemini": json.loads((run_dir / "probes.json").read_text()).get("probes", []).__len__(),
        "original": {
            "C0_halluc": orig_c0["n_unsupported"], "C1_halluc": orig_c1["n_unsupported"],
            "C0_cov": orig_c0["probe_coverage"], "C1_cov": orig_c1["probe_coverage"],
            "delta_halluc": orig_c1["n_unsupported"] - orig_c0["n_unsupported"],
            "delta_cov": orig_c1["probe_coverage"] - orig_c0["probe_coverage"],
        },
        "altref_gpt5": {
            "C0_halluc": h_c0_g, "C1_halluc": h_c1_g,
            "C0_cov": p_c0_g[0] / max(1, p_c0_g[1]),
            "C1_cov": p_c1_g[0] / max(1, p_c1_g[1]),
            "delta_halluc": h_c1_g - h_c0_g,
            "delta_cov": (p_c1_g[0] / max(1, p_c1_g[1])) - (p_c0_g[0] / max(1, p_c0_g[1])),
        },
        "altref_claude": {
            "C0_halluc": h_c0_c, "C1_halluc": h_c1_c,
            "C0_cov": p_c0_c[0] / max(1, p_c0_c[1]),
            "C1_cov": p_c1_c[0] / max(1, p_c1_c[1]),
            "delta_halluc": h_c1_c - h_c0_c,
            "delta_cov": (p_c1_c[0] / max(1, p_c1_c[1])) - (p_c0_c[0] / max(1, p_c0_c[1])),
        },
    }
    (run_dir / "reference_bias_summary.json").write_text(json.dumps(result, indent=2))

    print(f"\n  === reference-bias on {run_dir.name} ===")
    print(f"    Δhalluc orig          : {result['original']['delta_halluc']:+d}")
    print(f"    Δhalluc altref/GPT    : {result['altref_gpt5']['delta_halluc']:+d}")
    print(f"    Δhalluc altref/Claude : {result['altref_claude']['delta_halluc']:+d}")
    print(f"    Δcov    orig          : {result['original']['delta_cov']:+.3f}")
    print(f"    Δcov    altref/GPT    : {result['altref_gpt5']['delta_cov']:+.3f}")
    print(f"    Δcov    altref/Claude : {result['altref_claude']['delta_cov']:+.3f}")
    return result


def cmd_audio(args):
    audio = pathlib.Path(args.audio)
    rd = pathlib.Path(args.run_dir)
    alt_path = rd / "reference_alt.txt"
    if alt_path.exists():
        ref = alt_path.read_text()
        print(f"  [whisper] reusing {alt_path.name}", flush=True)
    else:
        ref = transcribe_whisper(audio, args.whisper_model)
    return run_one(rd, ref, f"whisper-{args.whisper_model}")


def cmd_paper(args):
    rd = pathlib.Path(args.run_dir)
    sample = pathlib.Path("data/longform_pdf/scanned/pilot_sample.jsonl")
    items = [json.loads(l) for l in sample.open()]
    item = next((it for it in items if it["item_id"] == args.item_id), None)
    if item is None:
        raise SystemExit(f"item {args.item_id} not in {sample}")
    image_paths = [pathlib.Path(p) for p in item["image_paths"]]
    alt_path = rd / "reference_alt.txt"
    if alt_path.exists():
        ref = alt_path.read_text()
        print(f"  [easyocr] reusing {alt_path.name}", flush=True)
    else:
        ref = ocr_easyocr(image_paths)
    return run_one(rd, ref, "easyocr")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_a = sub.add_parser("audio")
    ap_a.add_argument("--audio", required=True)
    ap_a.add_argument("--run-dir", required=True)
    ap_a.add_argument("--whisper-model", default="base")
    ap_a.set_defaults(func=cmd_audio)

    ap_p = sub.add_parser("paper")
    ap_p.add_argument("--run-dir", required=True)
    ap_p.add_argument("--item-id", required=True)
    ap_p.set_defaults(func=cmd_paper)

    args = ap.parse_args()
    result = args.func(args)
    print(f"\n[done]", flush=True)


if __name__ == "__main__":
    main()
