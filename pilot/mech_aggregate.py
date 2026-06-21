"""Aggregate all mechanistic experiments (E1-E6) into one comparison view."""
from __future__ import annotations
import json, pathlib, statistics as st
MECH = pathlib.Path(__file__).resolve().parent.parent / "runs" / "mechanism"

def load(name):
    p = MECH / f"{name}_summary.json"
    return json.loads(p.read_text()) if p.exists() else []

e1 = {r["cell"]: r for r in load("e1") if "coverage" in r}
e2 = {r["cell"]: r for r in load("e2")}
e5 = {r["cell"]: r for r in load("e5") if "coverage" in r}
e3 = {r["cell"]: r for r in load("e3")}
e4 = load("e4")
e6 = load("e6")

cells = ["mit_6034","3b1b_attention","wagging_tail_9pp","natural_vib_42pp",
         "thermal_66pp","heat_pipes_104pp","arxiv_fairness_53pp","arxiv_perovskite_80pp"]

def fmt(d):
    if not d: return "   -      "
    if "error" in d and "coverage" not in d: return f"ERR".ljust(10)
    return f"{d['n_unsupported']:>2}h/{d['coverage']:.2f}".ljust(10)

print("\n================ UNIFIED MECHANISM TABLE (hallucinations h / probe-coverage) ================")
print(f"{'cell':22} {'C0(img)':10} {'C1(text)':10} {'E1(both)':10} {'E2(1call)':10} {'E5(native)':10}")
for c in cells:
    b = (e1.get(c) or e2.get(c) or e5.get(c) or {}).get("baseline", {})
    c0 = b.get("C0",{}); c1=b.get("C1",{})
    c0s = f"{c0.get('n_unsupported')}h/{c0.get('coverage')}".ljust(10) if c0 else "-".ljust(10)
    c1s = f"{c1.get('n_unsupported')}h/{c1.get('coverage')}".ljust(10) if c1 else "-".ljust(10)
    print(f"{c:22} {c0s} {c1s} {fmt(e1.get(c))} {fmt(e2.get(c))} {fmt(e5.get(c))}")

# E2 errors (single-call truncation)
print("\nE2 single-call notes:")
for c in cells:
    r=e2.get(c)
    if r and "error" in r and "coverage" not in r:
        print(f"  {c}: {r['error']} (raw {r.get('raw_words','?')}w)")

print("\n================ E3 perceive-vs-surface (all 21 cells) ================")
if e3:
    tm=sum(r['n_c0_missed'] for r in e3.values()); tp=sum(r['c0_missed_perceivable'] for r in e3.values())
    print(f"mean Pass-1 transcript cov={st.mean(r['pass1_cov'] for r in e3.values()):.3f}  "
          f"C0 cov={st.mean(r['c0_cov'] for r in e3.values()):.3f}  C1 cov={st.mean(r['c1_cov'] for r in e3.values()):.3f}")
    print(f"POOLED rescue: {tp}/{tm} = {tp/tm:.1%} of C0-dropped probes are present in the model's own transcript")

print("\n================ E4 DPI / vision-token sweep ================")
print(f"{'cell':22} {'dpi':>5} {'tokens':>8} {'halluc':>6} {'cov':>5}")
for r in sorted(e4, key=lambda x:(x.get('cell',''),x.get('dpi',0))):
    if "coverage" in r:
        print(f"{r['cell']:22} {r['dpi']:5} {str(r.get('prompt_tokens')):>8} {r['n_unsupported']:6} {r['coverage']:5.2f}")
    else:
        print(f"{r['cell']:22} {r['dpi']:5} {str(r.get('prompt_tokens')):>8}   {r.get('error','?')}")

print("\n================ E6 activation-level logit-lens ================")
if e6:
    a = e6["aggregate"] if isinstance(e6, dict) else None
    a = e6.get("aggregate") if isinstance(e6, dict) else None
    if a:
        for k,v in a.items(): print(f"  {k}: {v}")
print()
