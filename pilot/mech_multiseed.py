"""V2 - multi-seed, powered replication of the mechanism conditions on all 21 cells.

Conditions (each at T=0.7, seeds 0..N-1):
  C1   : two-pass decomposition - Pass-2 text-only from the FIXED Pass-1 transcript.
  E1   : C1+ both - Pass-2 from transcript WITH the raw modality re-attached.
  E2   : single-call - transcribe-then-review in one response (modality attached).
Perception (Pass-1 transcript) is held fixed (reused), isolating synthesis variance.

Idempotent/resumable: each (cond, cell, seed) writes review_{cond}_s{seed}.txt and
judge_{halluc,probes}_{cond}_s{seed}.json into the run dir; existing files are skipped.
Loop order is seed-major so an interrupted run still yields a complete lower-n sweep.

Run: python3 pilot/mech_multiseed.py --seeds 5
Stats: python3 pilot/mech_multiseed_stats.py
"""
from __future__ import annotations
import argparse, json, sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mech_common as mc
from pilot_audio_review import (REVIEW_PROMPT, MEETING_MINUTES_PROMPT, score_review,
                                pass2_review_prompt as audio_pass2)
from pilot_paper_review import pass2_review_prompt as paper_pass2
from mech_e1e2 import e1_prompt, e2_prompt

REPO = mc.REPO
AUD = REPO / "data" / "longform_audio"
PDF = REPO / "data" / "longform_pdf" / "scanned"

# Full 21-cell registry: run_dir -> (label, modality, asset, task, item_id)
CELLS = {
 "audio-review-3b1b_attention-1778857367":  ("3b1b","audio","3blue1brown_attention_32k.mp3","review",None),
 "audio-review-doudna_crispr-1778859188":   ("doudna","audio","doudna_crispr_basics_32k.mp3","review",None),
 "audio-review-harvard_moot_court-1778859186":("harvard","audio","harvard_ames_moot_court_32k.mp3","review",None),
 "audio-review-karpathy_sogpt-1777458038":  ("karpathy","audio","karpathy_sogpt_32k.mp3","review",None),
 "audio-review-mit_6034_winston-1778857365":("mit6034","audio","mit_6034_winston_intro_32k.mp3","review",None),
 "audio-review-neurips_black_in_ai-1778859191":("neurips","audio","neurips_black_in_ai_panel_32k.mp3","review",None),
 "audio-review-sapolsky_genetics-1778859184":("sapolsky","audio","sapolsky_behavioral_genetics_32k.mp3","review",None),
 "audio-review-stanford_decarb-1778859192": ("stanford","audio","stanford_decarbonized_grid_32k.mp3","review",None),
 "audio-review-veritasium_math-1778857368": ("veritasium","audio","veritasium_strange_math_32k.mp3","review",None),
 "audio-meeting_minutes-ietf_snac-1777518337":("snac_min","audio","ietf_snac_2026-04-16.mp3","meeting_minutes",None),
 "audio-meeting_minutes-karpathy_sogpt-1777468873":("karpathy_min","audio","karpathy_sogpt_32k.mp3","meeting_minutes",None),
 "paper-review-19680000724-1777468706": ("env_test","paper",None,"review","19680000724"),
 "paper-review-19690008405-1777468708": ("dyn_resp","paper",None,"review","19690008405"),
 "paper-review-19690013408-1777471789": ("nat_vib","paper",None,"review","19690013408"),
 "paper-review-19700023812-1777471791": ("thermal","paper",None,"review","19700023812"),
 "paper-review-19700025120-1777462513": ("heat_pipes","paper",None,"review","19700025120"),
 "paper-review-19720009221-1777458461": ("wagging","paper",None,"review","19720009221"),
 "paper-review-19720022550-1778857333": ("sp5100","paper",None,"review","19720022550"),
 "paper-review-2605.09852-1778859219":  ("fairness","paper",None,"review","2605.09852"),
 "paper-review-2605.11379-1778859223":  ("megagauss","paper",None,"review","2605.11379"),
 "paper-review-2605.13991-1778859221":  ("perovskite","paper",None,"review","2605.13991"),
}


def asset_kwargs(modality, asset, item):
    if modality == "audio":
        p = AUD / asset
        return {"audio": str(p)} if p.exists() else None
    imgs = sorted((PDF / f"rendered_{item}").glob("*.png"))
    return {"images": [str(x) for x in imgs]} if imgs else None


def task_prompt(task):
    return MEETING_MINUTES_PROMPT if task == "meeting_minutes" else REVIEW_PROMPT


def build_prompt(cond, modality, task, transcript):
    tp = task_prompt(task)
    if cond == "C1":
        return (audio_pass2(transcript, tp) if modality == "audio" else paper_pass2(transcript)), {}
    if cond == "E1":
        return e1_prompt(transcript, modality), "MODALITY"
    if cond == "E2":
        return e2_prompt(modality), "MODALITY"
    raise ValueError(cond)


def run_one(rd, label, modality, asset, task, item, cond, seed, reference, probes, transcript):
    tag = f"{cond}_s{seed}"
    rev_path = rd / f"review_{tag}.txt"
    jp = rd / f"judge_probes_{tag}.json"
    if jp.exists() and rev_path.exists():
        d = json.loads(jp.read_text())
        return {"cell": label, "cond": cond, "seed": seed, "coverage": round(d.get("coverage", 0), 3),
                "n_covered": d.get("n_covered"), "n_probes": d.get("n_probes"),
                "n_unsupported": _h(rd, tag), "cached": True}
    prompt, mflag = build_prompt(cond, modality, task, transcript)
    kw = {}
    if mflag == "MODALITY":
        ak = asset_kwargs(modality, asset, item)
        if ak is None:
            return {"cell": label, "cond": cond, "seed": seed, "error": "asset missing"}
        kw = ak
    if rev_path.exists():
        review = rev_path.read_text()
    else:
        raw, _ = mc.gemini_call(prompt, temperature=0.7, seed=seed, **kw)
        if cond == "E2":
            review = raw.split("=== REVIEW ===", 1)[1].strip() if "=== REVIEW ===" in raw else ""
            (rd / f"raw_{tag}.txt").write_text(raw)
        else:
            review = raw
        rev_path.write_text(review)
    if not review.strip():
        return {"cell": label, "cond": cond, "seed": seed, "error": "no review (budget/format)",
                "review_words": 0}
    s = score_review(review, reference, probes, tag, rd)
    return {"cell": label, "cond": cond, "seed": seed, "coverage": round(s.probe_coverage, 3),
            "n_covered": s.n_covered, "n_probes": s.n_probes, "n_unsupported": s.n_unsupported,
            "review_words": len(review.split())}


def _h(rd, tag):
    p = rd / f"judge_halluc_{tag}.json"
    return json.loads(p.read_text()).get("n_unsupported") if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--conds", default="C1,E1,E2")
    args = ap.parse_args()
    conds = args.conds.split(",")
    out = mc.MECH / "multiseed_summary.json"
    results = json.loads(out.read_text()) if out.exists() else []
    seen = {(r["cell"], r["cond"], r["seed"]) for r in results if "coverage" in r}

    for seed in range(args.seeds):
        for rd_name, (label, modality, asset, task, item) in CELLS.items():
            rd = REPO / "runs" / rd_name
            if not rd.exists():
                continue
            reference = (rd / "reference_transcript.txt").read_text()
            probes = json.loads((rd / "probes.json").read_text()).get("probes", [])
            transcript = (rd / "transcript_C1_pass1.txt").read_text()
            for cond in conds:
                if (label, cond, seed) in seen:
                    continue
                t0 = time.time()
                try:
                    r = run_one(rd, label, modality, asset, task, item, cond, seed,
                                reference, probes, transcript)
                except Exception as e:
                    r = {"cell": label, "cond": cond, "seed": seed, "error": f"{type(e).__name__}: {str(e)[:150]}"}
                results.append(r)
                out.write_text(json.dumps(results, indent=2))  # checkpoint every item
                msg = (f"{r.get('n_unsupported','?')}h/{r.get('coverage','?')}" if "coverage" in r
                       else r.get("error", "?"))
                print(f"[seed {seed}] {label:12} {cond:3} -> {msg} ({time.time()-t0:.0f}s)", flush=True)
    print(f"[done] {len([r for r in results if 'coverage' in r])} scored cells; wrote {out}", flush=True)


if __name__ == "__main__":
    main()
