"""E3 (mechanistic): score the model's own Pass-1 transcript for probe coverage.

The Pass-1 transcript is the model-under-test's perception externalized as text.
Scoring it against the same probes used for C0/C1 reviews gives an *upper bound*
on what the model can capture from the raw modality. The informative contrast:

  - Pass-1 transcript coverage  ~= ceiling of perceivable content
  - C0 review coverage          = what survives end-to-end (perceive+reason+write)
  - C1 review coverage          = what survives reduce-to-text-then-reason

"Rescue rate" = of the probes C0 MISSED, the fraction present in the Pass-1
transcript. High rescue rate => the model PERCEIVED the content (could transcribe
it) but failed to SURFACE it when reasoning end-to-end => supports the
externalization/working-memory account (H2), not a perception failure.

Reuses the exact PROBE_CHECK_PROMPT + GPT-5.4 judge from pilot_audio_review.
Only the probe-coverage check is run on the transcript (the hallucination check
is meaningless for a verbatim transcript). Output: judge_probes_PASS1.json per
run dir, plus a combined runs/mechanism/e3_summary.json.

Note on circularity: reference and Pass-1 use the same model+prompt, so probes
(extracted from the reference) are near-guaranteed present in Pass-1. That is the
point: it establishes the content is capturable-as-text by this model. We report
the relationship transparently.
"""
from __future__ import annotations
import json, pathlib, sys, time, argparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pilot_audio_review import PROBE_CHECK_PROMPT, call_gpt5_judge, parse_json

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "runs" / "mechanism"
OUT.mkdir(parents=True, exist_ok=True)

# run_dir -> short cell label
CELLS = {
    "audio-review-3b1b_attention-1778857367": "3b1b_attention",
    "audio-review-doudna_crispr-1778859188": "doudna_crispr",
    "audio-review-harvard_moot_court-1778859186": "harvard_moot",
    "audio-review-karpathy_sogpt-1777458038": "karpathy",
    "audio-review-mit_6034_winston-1778857365": "mit_6034",
    "audio-review-neurips_black_in_ai-1778859191": "neurips_panel",
    "audio-review-sapolsky_genetics-1778859184": "sapolsky",
    "audio-review-stanford_decarb-1778859192": "stanford_decarb",
    "audio-review-veritasium_math-1778857368": "veritasium",
    "audio-meeting_minutes-ietf_snac-1777518337": "snac_minutes",
    "audio-meeting_minutes-karpathy_sogpt-1777468873": "karpathy_minutes",
    "paper-review-19680000724-1777468706": "env_test_18pp",
    "paper-review-19690008405-1777468708": "dyn_response_41pp",
    "paper-review-19690013408-1777471789": "natural_vib_42pp",
    "paper-review-19700023812-1777471791": "thermal_66pp",
    "paper-review-19700025120-1777462513": "heat_pipes_104pp",
    "paper-review-19720009221-1777458461": "wagging_tail_9pp",
    "paper-review-19720022550-1778857333": "sp5100_176pp",
    "paper-review-2605.09852-1778859219": "arxiv_fairness_53pp",
    "paper-review-2605.11379-1778859223": "arxiv_megagauss_75pp",
    "paper-review-2605.13991-1778859221": "arxiv_perovskite_80pp",
}


def score_transcript_coverage(transcript: str, probes: list[dict], out_path: pathlib.Path) -> dict:
    if out_path.exists():
        d = json.loads(out_path.read_text())
        return d
    pp = PROBE_CHECK_PROMPT.replace("{probes_json}", json.dumps(probes, indent=2)).replace("{review}", transcript)
    text, ms = call_gpt5_judge(pp)
    data = parse_json(text)
    results = data.get("results", [])
    n_cov = sum(1 for r in results if r.get("status") == "COVERED")
    out = {
        "label": "PASS1",
        "n_probes": len(results),
        "n_covered": n_cov,
        "coverage": n_cov / max(1, len(results)),
        "results": results,
    }
    out_path.write_text(json.dumps(out, indent=2))
    return out


def covered_ids(jp_path: pathlib.Path) -> set[str]:
    d = json.loads(jp_path.read_text())
    return {r["id"] for r in d.get("results", []) if r.get("status") == "COVERED"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma-separated run-dir names to limit to")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    summary = []
    for rd_name, label in CELLS.items():
        if only and rd_name not in only:
            continue
        rd = REPO / "runs" / rd_name
        if not rd.exists():
            print(f"[skip] {label}: no run dir", flush=True)
            continue
        transcript = (rd / "transcript_C1_pass1.txt").read_text()
        probes = json.loads((rd / "probes.json").read_text()).get("probes", [])
        t0 = time.time()
        p1 = score_transcript_coverage(transcript, probes, rd / "judge_probes_PASS1.json")
        p1_ids = {r["id"] for r in p1["results"] if r.get("status") == "COVERED"}
        all_ids = {r["id"] for r in p1["results"]}

        c0_ids = covered_ids(rd / "judge_probes_C0.json")
        c1_ids = covered_ids(rd / "judge_probes_C1.json")
        # align to the probe id set the PASS1 judge returned
        c0_ids &= all_ids
        c1_ids &= all_ids
        c0_missed = all_ids - c0_ids
        c1_missed = all_ids - c1_ids
        # rescue rate: of C0-missed probes, fraction present in Pass-1 transcript
        c0_missed_in_p1 = c0_missed & p1_ids
        c1_missed_in_p1 = c1_missed & p1_ids
        rescue_c0 = len(c0_missed_in_p1) / max(1, len(c0_missed))
        rescue_c1 = len(c1_missed_in_p1) / max(1, len(c1_missed))
        row = {
            "cell": label,
            "run_dir": rd_name,
            "n_probes": len(all_ids),
            "pass1_cov": round(len(p1_ids) / max(1, len(all_ids)), 3),
            "c0_cov": round(len(c0_ids) / max(1, len(all_ids)), 3),
            "c1_cov": round(len(c1_ids) / max(1, len(all_ids)), 3),
            "n_c0_missed": len(c0_missed),
            "c0_missed_perceivable": len(c0_missed_in_p1),
            "rescue_rate_c0": round(rescue_c0, 3),
            "n_c1_missed": len(c1_missed),
            "c1_missed_perceivable": len(c1_missed_in_p1),
            "rescue_rate_c1": round(rescue_c1, 3),
        }
        summary.append(row)
        print(f"[{label:22}] pass1={row['pass1_cov']:.2f} c0={row['c0_cov']:.2f} c1={row['c1_cov']:.2f} "
              f"| C0 missed {len(c0_missed)}, {len(c0_missed_in_p1)} perceivable (rescue {rescue_c0:.0%}) "
              f"({time.time()-t0:.0f}s)", flush=True)

    (OUT / "e3_summary.json").write_text(json.dumps(summary, indent=2))
    # aggregate
    if summary:
        import statistics as st
        def mean(k): return round(st.mean(r[k] for r in summary), 3)
        tot_missed = sum(r["n_c0_missed"] for r in summary)
        tot_perc = sum(r["c0_missed_perceivable"] for r in summary)
        print("\n=== E3 AGGREGATE ===", flush=True)
        print(f"cells: {len(summary)}", flush=True)
        print(f"mean pass1 transcript coverage: {mean('pass1_cov')}", flush=True)
        print(f"mean C0 review coverage:        {mean('c0_cov')}", flush=True)
        print(f"mean C1 review coverage:        {mean('c1_cov')}", flush=True)
        print(f"TOTAL C0-missed probes: {tot_missed}; of those present in Pass-1 transcript: "
              f"{tot_perc} ({tot_perc/max(1,tot_missed):.1%}) <- pooled rescue rate", flush=True)
        print(f"[wrote] {OUT/'e3_summary.json'}", flush=True)


if __name__ == "__main__":
    main()
