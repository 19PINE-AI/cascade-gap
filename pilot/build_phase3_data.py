"""Rebuild phase3_data.json from all run-dir summaries.

Walks runs/* and consolidates scores, word counts, and metadata for all cells
into a single JSON structure suitable for the figures and stats scripts.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
OUT = ROOT / "paper" / "figures" / "phase3_data.json"


# Map run-dir name → display cell name + modality/task/metadata
NAME_OVERRIDES = {
    "audio-review-karpathy_sogpt": "Karpathy review",
    "audio-meeting_minutes-karpathy_sogpt": "Karpathy mtg-min",
    "audio-meeting_minutes-ietf_snac": "SNAC mtg-min",
    "audio-review-3b1b_attention": "3B1B Attention",
    "audio-review-veritasium_math": "Veritasium Math",
    "audio-review-mit_6034_winston": "MIT 6.034 Winston",
    "audio-review-neurips_black_in_ai": "NeurIPS BinAI panel",
    "audio-review-doudna_crispr": "Doudna CRISPR",
    "audio-review-stanford_decarb": "Stanford Decarb",
    "audio-review-harvard_moot_court": "Harvard Moot Court",
    "audio-review-sapolsky_genetics": "Sapolsky Behavioral",
    "paper-review-19720009221": "Wagging Tail",
    "paper-review-19680000724": "Env Test",
    "paper-review-19690008405": "Dynamic Response",
    "paper-review-19690013408": "Natural Vibration",
    "paper-review-19700023812": "Thermal Analysis",
    "paper-review-19700025120": "Heat Pipes",
    "paper-review-19720022550": "SP-5100 Shock",
    "paper-review-2605.09852": "arXiv Fairness AI",
    "paper-review-2605.13991": "arXiv Perovskite",
    "paper-review-2605.11379": "arXiv Megagauss",
}

PAGE_COUNTS = {
    "Wagging Tail": 9, "Env Test": 18, "Dynamic Response": 41,
    "Natural Vibration": 42, "Thermal Analysis": 66, "Heat Pipes": 104,
    "SP-5100 Shock": 176, "arXiv Fairness AI": 53,
    "arXiv Perovskite": 80, "arXiv Megagauss": 75,
}


def _cell_key(dirname: str) -> str | None:
    # strip timestamp suffix
    parts = dirname.rsplit("-", 1)
    base = parts[0]
    return NAME_OVERRIDES.get(base)


def _modality_task(dirname: str) -> tuple[str, str]:
    if dirname.startswith("audio-review"):
        return ("audio", "review")
    if dirname.startswith("audio-meeting_minutes"):
        return ("audio", "meeting_minutes")
    if dirname.startswith("paper-review"):
        return ("paper", "review")
    return ("?", "?")


def build():
    cells = []
    for d in sorted(RUNS.iterdir()):
        if not d.is_dir():
            continue
        cell_name = _cell_key(d.name)
        if cell_name is None:
            continue
        sp = d / "summary.json"
        if not sp.exists():
            continue
        s = json.loads(sp.read_text())
        modality, task = _modality_task(d.name)
        entry = {
            "cell": cell_name,
            "modality": modality,
            "task": task,
            "run_dir": str(d.relative_to(ROOT)),
        }
        if modality == "audio":
            entry["source_words"] = s.get("reference_word_count")
        else:
            entry["page_count"] = PAGE_COUNTS.get(cell_name)
            entry["source_words"] = s.get("reference_word_count") or s.get("pdftotext_word_count")
        entry["scores"] = s.get("scores", {})
        # word counts
        for k in s:
            if k.startswith("review_") or k.startswith("transcript_"):
                entry[k] = s[k]
        if "C0_words" not in entry and "review_C0_word_count" in s:
            entry["C0_words"] = s["review_C0_word_count"]
        if "C1_words" not in entry and "review_C1_word_count" in s:
            entry["C1_words"] = s["review_C1_word_count"]
        if "C1_pass1_words" not in entry and "transcript_C1_pass1_word_count" in s:
            entry["C1_pass1_words"] = s["transcript_C1_pass1_word_count"]
        cells.append(entry)

    return {"cells": cells}


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, indent=2))
    print(f"Wrote {OUT.relative_to(ROOT)} with {len(data['cells'])} cells")
    for c in data["cells"]:
        s = c["scores"]
        if "C0" in s and "C1" in s:
            c0 = s["C0"]
            c1 = s["C1"]
            print(f"  {c['cell']:25s}  C0 {c0['n_unsupported']:>3}h/{c0['probe_coverage']:.2f}  C1 {c1['n_unsupported']:>3}h/{c1['probe_coverage']:.2f}")
