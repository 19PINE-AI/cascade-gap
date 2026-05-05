"""Extract Phase-3 data from runs/ into a flat JSON for figure generation."""
import json, pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent.parent

cells = []

# Audio review (Karpathy)
karpathy_review_run = sorted((REPO / "runs").glob("audio-review-karpathy_sogpt-*"))
if karpathy_review_run:
    s = json.loads((karpathy_review_run[-1] / "summary.json").read_text())
    cells.append({
        "cell": "Karpathy review",
        "modality": "audio",
        "task": "review",
        "speakers": 1,
        "source_words": s.get("reference_word_count", 8406),
        "scores": s.get("scores", {}),
        "C0_words": s.get("review_C0_word_count"),
        "C1_words": s.get("review_C1_word_count"),
    })

# Audio meeting minutes
for run_glob, name, src_words in [
    ("audio-meeting_minutes-karpathy_sogpt-*", "Karpathy mtg-min", 8406),
    ("audio-meeting_minutes-ietf_snac-*", "SNAC mtg-min", 9311),
]:
    run = sorted((REPO / "runs").glob(run_glob))
    if run:
        s = json.loads((run[-1] / "summary.json").read_text())
        speakers = 5 if "snac" in run_glob else 1
        cells.append({
            "cell": name,
            "modality": "audio",
            "task": "meeting_minutes",
            "speakers": speakers,
            "source_words": s.get("reference_word_count", src_words),
            "scores": s.get("scores", {}),
            "C0_words": s.get("review_C0_word_count"),
            "C1_words": s.get("review_C1_word_count"),
        })

# Papers
papers = [
    ("19720009221-1777458461", "Wagging Tail",     9,   3745),
    ("19680000724-1777468706", "Env Test",        18,   5891),
    ("19690008405-1777468708", "Dynamic Response", 41,  6891),
    ("19690013408-1777471789", "Natural Vibration", 42, 8824),
    ("19700023812-1777471791", "Thermal Analysis",  66, 11169),
    ("19700025120-1777462513", "Heat Pipes",       104, 22192),
]
for stem, name, pages, src_words in papers:
    run = REPO / "runs" / f"paper-review-{stem}"
    if not run.exists():
        continue
    s = json.loads((run / "summary.json").read_text())
    record = {
        "cell": name,
        "modality": "paper",
        "task": "review",
        "page_count": pages,
        "source_words": s.get("reference_word_count", src_words),
        "scores": s.get("scores", {}),
        "C0_words": s.get("review_C0_word_count"),
        "C1_words": s.get("review_C1_word_count"),
        "C1_pass1_words": s.get("transcript_C1_pass1_word_count"),
    }
    # Cross-vendor word counts if present
    for k in (
        "review_C0_claude_word_count", "review_C1_claude_word_count",
        "review_C0_mimo_word_count", "review_C1_mimo_word_count",
        "review_C1_stripped_claude_word_count", "review_C1_stripped_word_count",
        "review_C1c_claude_word_count", "review_C1c_word_count",
        "review_C1c_concat_word_count", "review_C1c_claude_concat_word_count",
        "review_C1c_stripped_claude_word_count",
        "review_C1c_stripped_claude_concat_word_count",
        "transcript_C1_pass1_claude_word_count",
        "transcript_C1_pass1_mimo_word_count",
    ):
        if k in s:
            record[k] = s[k]
    cells.append(record)

# Inter-judge summary
inter = (REPO / "research_log" / "inter_judge_summary.json")
if inter.exists():
    inter_data = json.loads(inter.read_text())
else:
    inter_data = {}

out = {"cells": cells, "inter_judge": inter_data}
output_path = pathlib.Path(__file__).parent / "phase3_data.json"
output_path.write_text(json.dumps(out, indent=2, default=str))
print(f"Wrote {len(cells)} cells to {output_path}")
for c in cells:
    print(f"  {c['cell']:25s}  {list(c['scores'].keys())}")
