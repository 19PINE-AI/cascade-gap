"""Aggregate the mixed-model audio cascade probe (off-protocol, production
best-of-breed): independent gpt-audio Pass-1 transcript -> text-only Pass-2 by
Claude Opus 4.7 / GPT-5.4 / Gemini 3.1 Pro, scored on the shared Pro reference +
probes (GPT-5.4 judge; Claude-judge cross-check on the GPT-5.4-authored review).
Reports each mixed pipeline next to the Gemini end-to-end C0 baseline."""
from __future__ import annotations
import json, pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"

CELLS = [  # name, run glob, Gemini headline C0 (h/cov) for reference
    ("3B1B Attention", "audio-review-3b1b_attention-*",    (11, 0.880)),
    ("Karpathy",       "audio-review-karpathy_sogpt-*",     (13, 0.627)),
    ("MIT 6.034",      "audio-review-mit_6034_winston-*",   (17, 0.771)),
]


def main():
    rows = []
    for name, glob, c0 in CELLS:
        hits = sorted(RUNS.glob(glob))
        if not hits:
            print(f"[skip] {name}"); continue
        sm = hits[0] / "summary_mix.json"
        if not sm.exists():
            print(f"[skip] {name}: no summary_mix.json"); continue
        d = json.loads(sm.read_text())
        s = d["synth"]
        rows.append({"cell": name, "C0_gem": c0, "pass1_words": d.get("pass1_words"),
                     "claude": s.get("claude", {}).get("gpt5_judge"),
                     "gpt54": s.get("gpt54", {}).get("gpt5_judge"),
                     "gpt54_cj": s.get("gpt54", {}).get("claude_judge"),
                     "gemini": s.get("gemini", {}).get("gpt5_judge")})

    print(f"\n{'cell':16s} {'Gem C0':>10} | {'[gpt-audio->Claude]':>20} {'[->GPT-5.4]':>14} {'[->Gemini]':>12}")
    print(f"{'':16s} {'(e2e)':>10} | {'GPT5-judge':>20} {'GPT5/Claude-j':>14} {'GPT5-judge':>12}")
    for r in rows:
        c0 = f"{r['C0_gem'][0]}h/{r['C0_gem'][1]:.2f}"
        cl = f"{r['claude']['n_unsupported']}h/{r['claude']['coverage']:.2f}" if r['claude'] else "--"
        g = (f"{r['gpt54']['n_unsupported']}h/{r['gpt54']['coverage']:.2f}"
             + (f" ({r['gpt54_cj']['n_unsupported']}h/{r['gpt54_cj']['coverage']:.2f})" if r['gpt54_cj'] else "")) if r['gpt54'] else "--"
        gm = f"{r['gemini']['n_unsupported']}h/{r['gemini']['coverage']:.2f}" if r['gemini'] else "--"
        print(f"{r['cell']:16s} {c0:>10} | {cl:>20} {g:>20} {gm:>12}")

    # how often does the mixed pipeline beat Gemini end-to-end C0 on coverage?
    def cov(x): return x['coverage'] if x else None
    wins = {"claude": 0, "gpt54": 0, "gemini": 0}
    for r in rows:
        for k in wins:
            x = r[k]
            if x and x['coverage'] >= r['C0_gem'][1] - 0.001:
                wins[k] += 1
    summary = {"n_cells": len(rows), "pass1": "gpt-audio (independent, non-Google)",
               "cov_ge_geminiC0": wins, "rows": rows}
    print(f"\nMixed Pass-2 coverage >= Gemini C0 on: " +
          ", ".join(f"{k} {v}/{len(rows)}" for k, v in wins.items()))
    out = RUNS / "mechanism" / "mixed_cascade_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"[wrote] {out}")


if __name__ == "__main__":
    main()
