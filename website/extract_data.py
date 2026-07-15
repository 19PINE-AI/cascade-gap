#!/usr/bin/env python3
"""Extract real run artifacts from runs/ into a single JSON consumed by the website.

Everything numeric here is read from the released run artifacts; the few
paper-level constants (citation density, aggregate stats) mirror
paper/main.tex Table `tab:all_cells` and the appendix tables.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "runs")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "data", "paperData.json")

# dir, id, short title, modality, kind, length-label, source words scale, cite/1k (from tex), group
CELLS = [
    ("audio-review-karpathy_sogpt-1777458038", "karpathy", "Karpathy: State of GPT", "audio", "review", "42 min", 0.00, "audio"),
    ("audio-meeting_minutes-karpathy_sogpt-1777468873", "karpathy_minutes", "Karpathy (meeting minutes)", "audio", "minutes", "42 min", 0.00, "audio"),
    ("audio-meeting_minutes-ietf_snac-1777518337", "snac_minutes", "IETF SNAC WG (meeting minutes)", "audio", "minutes", "60 min", 0.00, "audio"),
    ("audio-review-3b1b_attention-1778857367", "3b1b", "3Blue1Brown: Attention", "audio", "review", "26 min", 0.00, "audio"),
    ("audio-review-veritasium_math-1778857368", "veritasium", "Veritasium: Strange Math", "audio", "review", "32 min", 0.00, "audio"),
    ("audio-review-mit_6034_winston-1778857365", "mit", "MIT 6.034 Lecture 1 (Winston)", "audio", "review", "47 min", 0.00, "audio"),
    ("audio-review-neurips_black_in_ai-1778859191", "neurips", "NeurIPS Black in AI panel", "audio", "review", "31 min", 0.00, "audio"),
    ("audio-review-doudna_crispr-1778859188", "doudna", "Doudna: CRISPR Basics", "audio", "review", "48 min", 0.00, "audio"),
    ("audio-review-stanford_decarb-1778859192", "decarb", "Stanford: Decarbonized Power", "audio", "review", "72 min", 0.00, "audio"),
    ("audio-review-harvard_moot_court-1778859186", "harvard", "Harvard Ames Moot Court", "audio", "review", "82 min", 0.00, "audio"),
    ("audio-review-sapolsky_genetics-1778859184", "sapolsky", "Sapolsky: Behavioral Genetics", "audio", "review", "85 min", 0.00, "audio"),
    ("paper-review-19720009221-1777458461", "wagging_tail", "Wagging Tail Vibration Absorber", "paper", "review", "9 pp", 1.42, "nasa"),
    ("paper-review-19680000724-1777468706", "env_test", "Environmental Test & Reliability", "paper", "review", "18 pp", 0.00, "nasa"),
    ("paper-review-19690008405-1777468708", "dynamic_response", "Dynamic Response Analysis", "paper", "review", "41 pp", 1.19, "nasa"),
    ("paper-review-19690013408-1777471789", "natural_vibration", "Natural Vibration Modal Analysis", "paper", "review", "42 pp", 6.33, "nasa"),
    ("paper-review-19700023812-1777471791", "thermal", "Thermal Analysis of Spacecraft", "paper", "review", "66 pp", 0.36, "nasa"),
    ("paper-review-19700025120-1777462513", "heat_pipes", "Heat Pipes for Thermal Control", "paper", "review", "104 pp", 2.80, "nasa"),
    ("paper-review-19720022550-1778857333", "sp5100", "SP-5100 Shock & Vibration Survey", "paper", "review", "176 pp", 4.00, "nasa"),
    ("paper-review-2605.09852-1778859219", "fairness", "arXiv: Fairness of Explanations in AI", "paper", "review", "53 pp", 0.03, "arxiv"),
    ("paper-review-2605.11379-1778859223", "megagauss", "arXiv: Megagauss Physics", "paper", "review", "75 pp", 9.46, "arxiv"),
    ("paper-review-2605.13991-1778859221", "perovskite", "arXiv: Perovskite Tandem PV", "paper", "review", "80 pp", 0.15, "arxiv"),
]

NOTES = {
    "karpathy": "The paper's running example. 19 of 51 probes dropped end-to-end — all 19 present verbatim in the model's own transcript.",
    "harvard": "Largest coverage gain in the suite: +50pp. Multi-speaker legal argumentation where the end-to-end baseline is weakest.",
    "3b1b": "Cleanest faithfulness win: 11 unsupported claims down to 0.",
    "neurips": "Counter-cell: C0 already at 0.92 coverage — no headroom, so decomposition has nothing to recover.",
    "wagging_tail": "Counter-cell at high baseline (~0.80): within the ±0.04 noise floor.",
    "natural_vibration": "Mode-B Gemini cell (cite/1k = 6.33). Flips Pareto-positive under quote-grounded refinement C1-iter (7.8→3.6 halluc, 0.54→0.66 cov at n=5).",
    "heat_pipes": "The failure-mode showcase: Gemini is dominantly Mode A (22k-word transcript squeezed ~11× into a 2k-word review; chunked Pass-2 lifts 0.78→0.94). Claude is dominantly Mode B (4→20 halluc, bibliographic expansions).",
    "sp5100": "Longest source (176 pp, 47k words). Modes A+B compound; hallucination counts here carry ±25 judge-side spread (medians reported).",
    "fairness": "Mode A cell (−10pp): 53pp dense arXiv survey; author–year citations (~6/1k words) evade the numeric cite/1k regex shown here.",
    "perovskite": "Worst single-seed regression (−16pp) — but it shrinks to −6pp, inside the noise floor, under n=5 multi-seed re-runs.",
    "megagauss": "High-baseline-hallucination physics review; Modes A+B compound. Counts are medians over judge re-runs.",
    "karpathy_minutes": "Structured meeting-minutes re-prompt: atomic-fact probes depress absolute coverage for both configs; the cascade direction is unchanged.",
    "snac_minutes": "Meeting-minutes re-prompt on a 60-min IETF working-group interim call.",
}

FAILURE_MODE = {
    "natural_vibration": "B", "heat_pipes": "A+B", "sp5100": "A+B",
    "fairness": "A", "megagauss": "A+B", "perovskite": "A",
}

def read(path, limit=None):
    with open(path, encoding="utf-8", errors="replace") as f:
        t = f.read()
    return t if limit is None else t[:limit]

def jload(path):
    with open(path) as f:
        return json.load(f)

def words(t):
    return len(t.split())

def probe_map(run, label):
    p = os.path.join(run, f"judge_probes_{label}.json")
    if not os.path.exists(p):
        return {}
    d = jload(p)
    return {r["id"]: {"status": r["status"], "evidence": (r.get("evidence") or "")[:400]} for r in d["results"]}

def halluc_list(run, label, cap=60):
    p = os.path.join(run, f"judge_halluc_{label}.json")
    if not os.path.exists(p):
        return None
    d = jload(p)
    return [{"claim": c["claim"][:600], "reason": (c.get("reason") or "")[:600]}
            for c in d.get("unsupported_claims", [])[:cap]]

def main():
    e3 = {r["run_dir"]: r for r in jload(os.path.join(RUNS, "mechanism", "e3_summary.json"))}
    cells = []
    for dirname, cid, short, modality, kind, length, cite, group in CELLS:
        run = os.path.join(RUNS, dirname)
        s = jload(os.path.join(run, "summary.json"))
        sc = s["scores"]
        probes_src = jload(os.path.join(run, "probes.json"))["probes"]
        c0p, c1p = probe_map(run, "C0"), probe_map(run, "C1")
        probes = []
        for pr in probes_src:
            pid = pr["id"]
            probes.append({
                "id": pid, "fact": pr["fact"],
                "c0": c0p.get(pid, {}).get("status", "?"),
                "c0ev": c0p.get(pid, {}).get("evidence", ""),
                "c1": c1p.get(pid, {}).get("status", "?"),
                "c1ev": c1p.get(pid, {}).get("evidence", ""),
            })
        rev0 = read(os.path.join(run, "review_C0.txt"))
        rev1 = read(os.path.join(run, "review_C1.txt"))
        tr_path = os.path.join(run, "transcript_C1_pass1.txt")
        tr = read(tr_path) if os.path.exists(tr_path) else ""
        ref = read(os.path.join(run, "reference_transcript.txt"))

        def score(k):
            if k not in sc: return None
            v = sc[k]
            return {"h": v["n_unsupported"], "cov": round(v["probe_coverage"], 3),
                    "covered": v["n_covered"], "n": v["n_probes"]}

        extra = {}
        for key, lbl in [("C0_claude", "claude_c0"), ("C1_claude", "claude_c1"),
                         ("C0_xvendor", "mimo_c0"), ("C1_xvendor", "mimo_c1"),
                         ("C0_mimo", "mimo_c0"), ("C1_mimo", "mimo_c1"),
                         ("C0_flash25", "flash_c0"), ("C1_flash25", "flash_c1"),
                         ("C1c", "gemini_c1c"), ("C1c_concat", "gemini_c1c_concat"),
                         ("C1_iter_gemini", "gemini_c1iter"), ("C1_iter_claude", "claude_c1iter")]:
            v = score(key)
            if v and lbl not in extra:
                extra[lbl] = v

        e3row = e3.get(dirname)
        cell = {
            "id": cid, "dir": dirname, "title": s.get("title", short), "short": short,
            "modality": modality, "kind": kind, "length": length, "group": group,
            "citePer1k": cite,
            "note": NOTES.get(cid, ""),
            "failureMode": FAILURE_MODE.get(cid),
            "nProbes": s.get("n_probes"),
            "refWords": s.get("reference_word_count") or words(ref),
            "transcriptWords": s.get("transcript_C1_pass1_word_count") or (words(tr) if tr else None),
            "c0Words": s.get("review_C0_word_count") or words(rev0),
            "c1Words": s.get("review_C1_word_count") or words(rev1),
            "pass1Cov": round(e3row["pass1_cov"], 3) if e3row else None,
            "c0MissedPerceivable": e3row["c0_missed_perceivable"] if e3row else None,
            "c0Missed": e3row["n_c0_missed"] if e3row else None,
            "c0": score("C0"), "c1": score("C1"),
            "extra": extra,
            "probes": probes,
            "hallucC0": halluc_list(run, "C0") or [],
            "hallucC1": halluc_list(run, "C1") or [],
            "reviewC0": rev0,
            "reviewC1": rev1,
            "transcriptExcerpt": tr[:2600],
            "referenceExcerpt": ref[:1800],
        }
        cells.append(cell)

    # Mixed-model pipelines (3 audio cells) — real summary_mix.json artifacts
    mixed = []
    for dirname in ["audio-review-3b1b_attention-1778857367",
                    "audio-review-karpathy_sogpt-1777458038",
                    "audio-review-mit_6034_winston-1778857365"]:
        p = os.path.join(RUNS, dirname, "summary_mix.json")
        if not os.path.exists(p): continue
        d = jload(p)
        row = {"dir": dirname, "pass1Words": d.get("pass1_words"), "synth": {}}
        for model, judged in d.get("synth", {}).items():
            g = judged.get("gpt5_judge", {})
            row["synth"][model] = {"h": g.get("n_unsupported"), "cov": g.get("coverage")}
            if "claude_judge" in judged:
                cj = judged["claude_judge"]
                row["synth"][model]["claudeJudge"] = {"h": cj.get("n_unsupported"), "cov": cj.get("coverage")}
        # excerpts of the actual mixed reviews
        for m, fn in [("claude", "review_mix_claude.txt"), ("gpt54", "review_mix_gpt54.txt"), ("gemini", "review_mix_gemini.txt")]:
            fp = os.path.join(RUNS, dirname, fn)
            if os.path.exists(fp) and m in row["synth"]:
                row["synth"][m]["excerpt"] = read(fp, 1500)
        mixed.append(row)

    out = {"cells": cells, "mixed": mixed}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, ensure_ascii=False)
    size = os.path.getsize(OUT) / 1e6
    print(f"wrote {OUT} ({size:.2f} MB), {len(cells)} cells, {len(mixed)} mixed rows")
    # sanity: aggregate deltas match the paper
    dcov = sum(c["c1"]["cov"] - c["c0"]["cov"] for c in cells) / len(cells)
    dh = sum(c["c1"]["h"] - c["c0"]["h"] for c in cells) / len(cells)
    covwins = sum(1 for c in cells if c["c1"]["cov"] > c["c0"]["cov"])
    hwins = sum(1 for c in cells if c["c1"]["h"] < c["c0"]["h"])
    print(f"mean dCov={dcov:+.3f} (paper +0.118) meanDh={dh:+.2f} (paper -3.86) covWins={covwins}/21 (16) hWins={hwins}/21 (18)")

if __name__ == "__main__":
    main()
