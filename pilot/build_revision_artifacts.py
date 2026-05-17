"""Combine multi-judge medians and multi-seed envelopes into the figure data
JSON and a refreshed cross-cell aggregate.

Produces:
  - paper/figures/phase3_data.json (updated, with per-cell judge medians
    on high-count cells and multi-seed envelopes on the four headline cells)
  - research_log/revision_aggregate.json (everything in one place for the
    paper to cite)
"""
from __future__ import annotations

import json
import pathlib
import statistics


REPO = pathlib.Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"
FIG = REPO / "paper/figures"
LOG = REPO / "research_log"


# Per high-count cell: which cells have multi-judge data and use the median
# in the headline aggregate.
HIGH_COUNT_OVERRIDES = {
    # Cell key (matching paper/figures/phase3_data.json "cell" field)
    # -> (label_prefix_for_C0_C1 if both, OR None to indicate skip)
    "SP-5100 Shock": {
        "C0": "C0",     # review_C0.txt (Gemini)
        "C1": "C1",
        # Claude C1 entry exists too
        "C1_claude": "C1_claude",
    },
    "Heat Pipes": {
        "C0": "C0",
        "C1": "C1",
        "C0_claude": "C0_claude",
        "C1_claude": "C1_claude",
    },
    "arXiv Megagauss": {
        "C0": "C0",
        "C1": "C1",
        "C1_claude": "C1_claude",
    },
    "arXiv Fairness AI": {
        "C0": "C0",
        "C1": "C1",
        "C1_claude": "C1_claude",
    },
}


def collect_judge_median(rd: pathlib.Path, label_prefix: str) -> tuple[int, list[int]]:
    """Return (median, counts list) across all judge_halluc_<prefix>*.json that
    re-judge the same review file."""
    files = []
    base = rd / f"judge_halluc_{label_prefix}.json"
    if base.exists():
        files.append(base)
    for p in sorted(rd.glob(f"judge_halluc_{label_prefix}_rejudge*.json")):
        files.append(p)
    for p in sorted(rd.glob(f"judge_halluc_{label_prefix}_jrun*.json")):
        files.append(p)
    counts = []
    for f in files:
        try:
            d = json.loads(f.read_text())
            v = d.get("n_unsupported")
            if isinstance(v, int):
                counts.append(v)
        except Exception:
            pass
    if not counts:
        return None, []
    return int(statistics.median(counts)), counts


def update_phase3_data():
    p = FIG / "phase3_data.json"
    data = json.loads(p.read_text())
    for cell in data["cells"]:
        name = cell["cell"]
        if name not in HIGH_COUNT_OVERRIDES:
            continue
        rd = REPO / cell["run_dir"]
        overrides = HIGH_COUNT_OVERRIDES[name]
        for label, prefix in overrides.items():
            if label not in cell.get("scores", {}):
                continue
            med, counts = collect_judge_median(rd, prefix)
            if med is None or len(counts) < 2:
                continue
            cell["scores"][label]["n_unsupported_median"] = med
            cell["scores"][label]["n_unsupported_calls"] = counts
            cell["scores"][label]["n_unsupported_range"] = [min(counts), max(counts)]
    p.write_text(json.dumps(data, indent=2))
    print(f"[updated] {p}")


def collect_multi_seed_envelopes():
    targets = [
        ("audio-review-mit_6034_winston-1778857365", "MIT 6.034 Winston"),
        ("audio-review-sapolsky_genetics-1778859184", "Sapolsky Behavioral"),
        ("paper-review-19700025120-1777462513", "Heat Pipes Gemini"),
        ("paper-review-2605.13991-1778859221", "arXiv Perovskite"),
    ]
    rows = []
    for sub, name in targets:
        rd = RUNS / sub
        seeds, halluc, cov = [], [], []
        for seed in range(1, 6):
            jh = rd / f"judge_halluc_C1_ms_seed{seed}.json"
            jp = rd / f"judge_probes_C1_ms_seed{seed}.json"
            if not (jh.exists() and jp.exists()):
                continue
            h = json.loads(jh.read_text()).get("n_unsupported")
            d = json.loads(jp.read_text())
            ncov = d.get("n_covered")
            npr = d.get("n_probes", 50)
            if h is None or ncov is None:
                continue
            seeds.append(seed)
            halluc.append(h)
            cov.append(ncov / max(1, npr))
        if not seeds:
            continue
        bp = rd / "summary.json"
        b_h = b_cov = None
        if bp.exists():
            c1 = json.loads(bp.read_text()).get("scores", {}).get("C1", {})
            b_h = c1.get("n_unsupported")
            b_cov = c1.get("probe_coverage")
        rows.append({
            "cell": name,
            "run_dir": sub,
            "n": len(seeds),
            "seeds": seeds,
            "halluc": halluc,
            "cov": [round(c, 4) for c in cov],
            "halluc_mean": round(statistics.mean(halluc), 2),
            "halluc_stdev": round(statistics.stdev(halluc), 2) if len(halluc) > 1 else 0.0,
            "cov_mean": round(statistics.mean(cov), 4),
            "cov_stdev": round(statistics.stdev(cov), 4) if len(cov) > 1 else 0.0,
            "baseline_C1_halluc": b_h,
            "baseline_C1_cov": b_cov,
        })
    return rows


def collect_iter():
    targets = [
        ("paper-review-19700025120-1777462513", "Heat Pipes Claude",     "C1_iter_claude", "C1_claude", "claude"),
        ("paper-review-19700025120-1777462513", "Heat Pipes Gemini",     "C1_iter_gemini", "C1",        "gemini"),
        ("paper-review-19690013408-1777471789", "Natural Vibration",     "C1_iter_gemini", "C1",        "gemini"),
        ("paper-review-2605.09852-1778859219",  "arXiv Fairness AI Gemini", "C1_iter_gemini", "C1",      "gemini"),
        ("paper-review-2605.09852-1778859219",  "arXiv Fairness AI Claude", "C1_iter_claude", "C1_claude","claude"),
        ("paper-review-19720022550-1778857333", "SP-5100 Claude",         "C1_iter_claude", "C1_claude", "claude"),
        ("paper-review-2605.11379-1778859223",  "arXiv Megagauss Claude", "C1_iter_claude", "C1_claude", "claude"),
    ]
    rows = []
    for sub, name, iter_lab, base_lab, vendor in targets:
        rd = RUNS / sub
        bj = rd / f"judge_halluc_{base_lab}.json"
        bp = rd / f"judge_probes_{base_lab}.json"
        ij = rd / f"judge_halluc_{iter_lab}.json"
        ip = rd / f"judge_probes_{iter_lab}.json"
        if not (ij.exists() and ip.exists()):
            continue
        bh = json.loads(bj.read_text()).get("n_unsupported") if bj.exists() else None
        bpd = json.loads(bp.read_text()) if bp.exists() else None
        bcov = bpd.get("n_covered") / max(1, bpd.get("n_probes", 1)) if bpd else None
        ih = json.loads(ij.read_text()).get("n_unsupported")
        ipd = json.loads(ip.read_text())
        icov = ipd.get("n_covered") / max(1, ipd.get("n_probes", 1))
        # Claims filter info
        fpath = rd / f"claims_filtered_{iter_lab}.json"
        n_total = n_supp = n_rej = None
        if fpath.exists():
            d = json.loads(fpath.read_text())
            n_total = d.get("n_total")
            n_supp = d.get("n_supported")
            n_rej = d.get("n_rejected")
        rows.append({
            "cell": name,
            "vendor": vendor,
            "run_dir": sub,
            "baseline_C1_halluc": bh,
            "baseline_C1_cov": round(bcov, 4) if bcov is not None else None,
            "iter_halluc": ih,
            "iter_cov": round(icov, 4),
            "delta_halluc": (ih - bh) if (ih is not None and bh is not None) else None,
            "delta_cov": round(icov - bcov, 4) if bcov is not None else None,
            "n_claims_total": n_total,
            "n_claims_supported": n_supp,
            "n_claims_rejected": n_rej,
        })
    return rows


def collect_probe_circularity():
    """All cells with probe_circularity_summary.json."""
    rows = []
    for rd in sorted(RUNS.iterdir()):
        f = rd / "probe_circularity_summary.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        rows.append({
            "cell_run_dir": rd.name,
            "n_probes_gemini": d.get("n_probes_gemini_extracted"),
            "n_probes_claude": d.get("n_probes_claude_extracted"),
            "orig_delta_cov":       round(d.get("original_gpt_delta_cov", 0), 4),
            "claudepr_gpt_delta":   round(d.get("claudeprobes_gpt_delta_cov", 0), 4),
            "claudepr_claude_delta":round(d.get("claudeprobes_claude_delta_cov", 0), 4),
        })
    return rows


def collect_reference_bias():
    rows = []
    for rd in sorted(RUNS.iterdir()):
        f = rd / "reference_bias_summary.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        rows.append({
            "cell_run_dir": rd.name,
            "ref_kind": d.get("ref_kind"),
            "n_probes_alt": d.get("n_probes_alt"),
            "original": d.get("original"),
            "altref_gpt5": d.get("altref_gpt5"),
            "altref_claude": d.get("altref_claude"),
        })
    return rows


def main():
    update_phase3_data()
    aggregate = {
        "multi_seed_envelopes": collect_multi_seed_envelopes(),
        "iterative_refinement": collect_iter(),
        "probe_circularity_all_cells": collect_probe_circularity(),
        "reference_bias_all_cells": collect_reference_bias(),
    }
    op = LOG / "revision_aggregate.json"
    op.write_text(json.dumps(aggregate, indent=2))
    print(f"[saved] {op}")
    # Print compact summary
    print("\n=== Multi-seed envelopes ===")
    for r in aggregate["multi_seed_envelopes"]:
        print(f"  {r['cell']:25s} n={r['n']} h={r['halluc']} mean={r['halluc_mean']}±{r['halluc_stdev']}  cov={r['cov']} mean={r['cov_mean']}±{r['cov_stdev']}  base={r['baseline_C1_halluc']}h/{r['baseline_C1_cov']}")
    print("\n=== Iterative refinement ===")
    for r in aggregate["iterative_refinement"]:
        bh = r['baseline_C1_halluc']; bcov = r['baseline_C1_cov']
        if bh is None:
            print(f"  {r['cell']:25s} {r['vendor']:7s}  iter {r['iter_halluc']}h/{r['iter_cov']}  claims {r['n_claims_supported']}/{r['n_claims_total']}")
        else:
            print(f"  {r['cell']:25s} {r['vendor']:7s}  base {bh}h/{bcov} -> iter {r['iter_halluc']}h/{r['iter_cov']}  Δh={r['delta_halluc']:+d} Δcov={r['delta_cov']:+.3f}  claims {r['n_claims_supported']}/{r['n_claims_total']}")
    print("\n=== Probe-circularity ===")
    for r in aggregate["probe_circularity_all_cells"]:
        print(f"  {r['cell_run_dir']:55s} orig {r['orig_delta_cov']:+.3f}  cl-pr/gpt {r['claudepr_gpt_delta']:+.3f}  cl-pr/cl {r['claudepr_claude_delta']:+.3f}")
    print("\n=== Reference bias ===")
    for r in aggregate["reference_bias_all_cells"]:
        o = r['original']; a = r['altref_gpt5']
        print(f"  {r['cell_run_dir']:55s} ref={r['ref_kind']}  orig Δh={o['delta_halluc']:+d} Δcov={o['delta_cov']:+.3f}   alt-gpt Δh={a['delta_halluc']:+d} Δcov={a['delta_cov']:+.3f}")


if __name__ == "__main__":
    main()
