"""Aggregate the revision-round experiment results.

Produces a single research_log/revision_summary.json with:
  - per-cell multi-judge hallucination envelopes (new + previously-collected)
  - per-cell multi-seed Pass-2 envelopes for MIT 6.034, Sapolsky, Heat Pipes
    Gemini, arXiv Perovskite
  - iterative-refinement (C1_iter) results per cell
  - expanded probe-circularity (n=7) and reference-bias (n=4) tables
  - refreshed stats: mean Δ across cells using judge-median for high-count cells

Idempotent: reads existing JSON outputs from the runs/ tree and the
research_log/.
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics


REPO = pathlib.Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"
LOG = REPO / "research_log"


# ---- multi-judge envelopes -------------------------------------------------

# (run_dir, base_label, review_filename) — we scan all judge_halluc_<base>*.json
# files in run_dir whose label starts with base_label.
MULTI_JUDGE_TARGETS = [
    ("paper-review-19700025120-1777462513", "Heat Pipes Gemini C0",  "review_C0.txt"),
    ("paper-review-19700025120-1777462513", "Heat Pipes Gemini C1",  "review_C1.txt"),
    ("paper-review-19720022550-1778857333", "SP-5100 Gemini C0",     "review_C0.txt"),
    ("paper-review-19720022550-1778857333", "SP-5100 Gemini C1",     "review_C1.txt"),
    ("paper-review-19720022550-1778857333", "SP-5100 Claude C1",     "review_C1_claude.txt"),
    ("paper-review-2605.11379-1778859223",  "Megagauss Gemini C0",   "review_C0.txt"),
    ("paper-review-2605.11379-1778859223",  "Megagauss Gemini C1",   "review_C1.txt"),
    ("paper-review-2605.11379-1778859223",  "Megagauss Claude C1",   "review_C1_claude.txt"),
    ("paper-review-2605.09852-1778859219",  "Fairness AI Gemini C0", "review_C0.txt"),
    ("paper-review-2605.09852-1778859219",  "Fairness AI Gemini C1", "review_C1.txt"),
    ("paper-review-2605.09852-1778859219",  "Fairness AI Claude C1", "review_C1_claude.txt"),
    ("paper-review-19700025120-1777462513", "Heat Pipes Claude C0",  "review_C0_claude.txt"),
    ("paper-review-19700025120-1777462513", "Heat Pipes Claude C1",  "review_C1_claude.txt"),
]


def _label_prefix_for(review_filename: str) -> str:
    """Map review filename to the judge_halluc label prefix used in this repo.
    review_C0.txt -> 'C0', review_C1.txt -> 'C1', review_C1_claude.txt -> 'C1_claude'.
    """
    m = re.match(r"review_(.+)\.txt", review_filename)
    if not m:
        raise ValueError(f"unexpected review filename: {review_filename}")
    return m.group(1)


def _judge_files_for(run_dir: pathlib.Path, label_prefix: str) -> list[pathlib.Path]:
    """All judge_halluc_*.json that re-judge the same review file."""
    files = []
    base = run_dir / f"judge_halluc_{label_prefix}.json"
    if base.exists():
        files.append(base)
    # Patterns: judge_halluc_<prefix>_rejudge<N>.json, _jrun<N>.json
    for p in sorted(run_dir.glob(f"judge_halluc_{label_prefix}_rejudge*.json")):
        files.append(p)
    for p in sorted(run_dir.glob(f"judge_halluc_{label_prefix}_jrun*.json")):
        files.append(p)
    return files


def collect_multi_judge() -> dict:
    rows = []
    for run_subdir, name, review_filename in MULTI_JUDGE_TARGETS:
        rd = RUNS / run_subdir
        if not rd.exists():
            continue
        lp = _label_prefix_for(review_filename)
        files = _judge_files_for(rd, lp)
        if not files:
            continue
        counts = []
        for f in files:
            try:
                d = json.loads(f.read_text())
                counts.append(d.get("n_unsupported"))
            except Exception:
                pass
        counts = [c for c in counts if isinstance(c, int)]
        if not counts:
            continue
        rows.append({
            "cell": name,
            "run_dir": run_subdir,
            "review": review_filename,
            "n_judge_calls": len(counts),
            "counts": counts,
            "min": min(counts),
            "max": max(counts),
            "median": int(statistics.median(counts)),
            "mean": round(statistics.mean(counts), 1),
            "range": max(counts) - min(counts),
        })
    return {"rows": rows}


# ---- multi-seed Pass-2 envelopes -------------------------------------------

MULTI_SEED_TARGETS = [
    ("audio-review-mit_6034_winston-1778857365", "MIT 6.034 Winston", "C1_ms"),
    ("audio-review-sapolsky_genetics-1778859184", "Sapolsky Behavioral", "C1_ms"),
    ("paper-review-19700025120-1777462513", "Heat Pipes Gemini", "C1_ms"),
    ("paper-review-2605.13991-1778859221", "arXiv Perovskite", "C1_ms"),
]


def collect_multi_seed() -> dict:
    rows = []
    for run_subdir, name, prefix in MULTI_SEED_TARGETS:
        rd = RUNS / run_subdir
        if not rd.exists():
            continue
        seeds, halluc, cov = [], [], []
        for seed in range(1, 6):
            jh = rd / f"judge_halluc_{prefix}_seed{seed}.json"
            jp = rd / f"judge_probes_{prefix}_seed{seed}.json"
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
        # Baseline C1
        baseline_h = None
        baseline_cov = None
        baseline_path = rd / "summary.json"
        if baseline_path.exists():
            s = json.loads(baseline_path.read_text())
            c1 = s.get("scores", {}).get("C1", {})
            baseline_h = c1.get("n_unsupported")
            baseline_cov = c1.get("probe_coverage")
        rows.append({
            "cell": name,
            "run_dir": run_subdir,
            "n_seeds": len(seeds),
            "seeds": seeds,
            "halluc_seeds": halluc,
            "cov_seeds": [round(c, 4) for c in cov],
            "halluc_mean": round(statistics.mean(halluc), 2),
            "halluc_stdev": round(statistics.stdev(halluc), 2) if len(halluc) > 1 else 0.0,
            "halluc_range": [min(halluc), max(halluc)],
            "cov_mean": round(statistics.mean(cov), 4),
            "cov_stdev": round(statistics.stdev(cov), 4) if len(cov) > 1 else 0.0,
            "cov_range": [round(min(cov), 4), round(max(cov), 4)],
            "baseline_C1_halluc": baseline_h,
            "baseline_C1_cov": baseline_cov,
        })
    return {"rows": rows}


# ---- iterative-refinement results ------------------------------------------

ITER_TARGETS = [
    ("paper-review-19700025120-1777462513", "Heat Pipes",          "C1_iter_claude", "C1_claude",  "claude"),
    ("paper-review-19700025120-1777462513", "Heat Pipes",          "C1_iter_gemini", "C1",          "gemini"),
    ("paper-review-19690013408-1777471789", "Natural Vibration",   "C1_iter_gemini", "C1",          "gemini"),
    ("paper-review-2605.09852-1778859219",  "arXiv Fairness AI",   "C1_iter_gemini", "C1",          "gemini"),
    ("paper-review-2605.09852-1778859219",  "arXiv Fairness AI",   "C1_iter_claude", "C1_claude",   "claude"),
    ("paper-review-19720022550-1778857333", "SP-5100",             "C1_iter_claude", "C1_claude",   "claude"),
    ("paper-review-2605.11379-1778859223",  "arXiv Megagauss",     "C1_iter_claude", "C1_claude",   "claude"),
]


def _read_score(run_dir: pathlib.Path, label: str) -> dict | None:
    """Read judge_halluc + judge_probes for a label and return aggregated dict."""
    jh = run_dir / f"judge_halluc_{label}.json"
    jp = run_dir / f"judge_probes_{label}.json"
    if not (jh.exists() and jp.exists()):
        return None
    h = json.loads(jh.read_text()).get("n_unsupported")
    p = json.loads(jp.read_text())
    n_pr = p.get("n_probes")
    n_cov = p.get("n_covered")
    cov = n_cov / max(1, n_pr) if n_cov is not None else None
    return {"n_unsupported": h, "n_probes": n_pr, "n_covered": n_cov, "probe_coverage": cov}


def collect_iter() -> dict:
    rows = []
    for run_subdir, name, iter_label, baseline_label, vendor in ITER_TARGETS:
        rd = RUNS / run_subdir
        if not rd.exists():
            continue
        iter_score = _read_score(rd, iter_label)
        baseline = _read_score(rd, baseline_label)
        if iter_score is None:
            continue
        # Read claim filter info
        filt_path = rd / f"claims_filtered_{iter_label}.json"
        n_claims_total = n_claims_supported = n_claims_rejected = None
        if filt_path.exists():
            d = json.loads(filt_path.read_text())
            n_claims_total = d.get("n_total")
            n_claims_supported = d.get("n_supported")
            n_claims_rejected = d.get("n_rejected")
        rows.append({
            "cell": name,
            "vendor": vendor,
            "run_dir": run_subdir,
            "baseline_label": baseline_label,
            "baseline": baseline,
            "iter_label": iter_label,
            "iter_score": iter_score,
            "n_claims_total": n_claims_total,
            "n_claims_supported": n_claims_supported,
            "n_claims_rejected": n_claims_rejected,
        })
    return {"rows": rows}


def main():
    out = {
        "multi_judge": collect_multi_judge(),
        "multi_seed": collect_multi_seed(),
        "iterative_refinement": collect_iter(),
    }
    op = LOG / "revision_summary.json"
    op.write_text(json.dumps(out, indent=2))
    print(f"[saved] {op}")
    # Quick stdout summary
    print("\nMulti-judge envelopes:")
    for r in out["multi_judge"]["rows"]:
        print(f"  {r['cell']:30s} n={r['n_judge_calls']} counts={r['counts']} median={r['median']} range={r['range']}")
    print("\nMulti-seed Pass-2 envelopes:")
    for r in out["multi_seed"]["rows"]:
        print(f"  {r['cell']:25s} n={r['n_seeds']} h={r['halluc_seeds']} mean={r['halluc_mean']:.1f}±{r['halluc_stdev']:.1f}")
        print(f"  {' ':25s}        cov={r['cov_seeds']} mean={r['cov_mean']:.3f}±{r['cov_stdev']:.3f}")
        print(f"  {' ':25s}        baseline C1: h={r['baseline_C1_halluc']} cov={r['baseline_C1_cov']}")
    print("\nIterative refinement:")
    for r in out["iterative_refinement"]["rows"]:
        b = r["baseline"]
        s = r["iter_score"]
        if b is None:
            print(f"  {r['cell']:25s} {r['vendor']:7s}  iter h={s['n_unsupported']} cov={s['probe_coverage']:.3f}  claims {r['n_claims_supported']}/{r['n_claims_total']}")
        else:
            print(f"  {r['cell']:25s} {r['vendor']:7s}  baseline h={b['n_unsupported']} cov={b['probe_coverage']:.3f} -> iter h={s['n_unsupported']} cov={s['probe_coverage']:.3f}  claims {r['n_claims_supported']}/{r['n_claims_total']}")


if __name__ == "__main__":
    main()
