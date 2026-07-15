"""Generate mechanism-section figures from the E1-E6 summaries."""
from __future__ import annotations
import json, pathlib, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

MECH = pathlib.Path(__file__).resolve().parent.parent / "runs" / "mechanism"
FIG = pathlib.Path(__file__).resolve().parent.parent / "paper" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

def load(n):
    p = MECH / f"{n}_summary.json"
    return json.loads(p.read_text()) if p.exists() else None

# ---------- Fig A: E3 perceive-vs-surface ----------
e3 = load("e3")
if e3:
    e3s = sorted(e3, key=lambda r: r["c0_cov"])
    labels = [re.sub(r"_?\d+pp$", "", r["cell"]) for r in e3s]
    c0 = [r["c0_cov"] for r in e3s]; c1=[r["c1_cov"] for r in e3s]; p1=[r["pass1_cov"] for r in e3s]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(11,4.6))
    ax.bar(x-0.25, p1, 0.25, label="Pass-1 transcript (perception)", color="#2c7fb8")
    ax.bar(x, c1, 0.25, label="$C_1$ review (reason over text)", color="#7fcdbb")
    ax.bar(x+0.25, c0, 0.25, label="$C_0$ review (reason over modality)", color="#d95f0e")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=55, ha="right", fontsize=12)
    ax.set_ylabel("probe coverage", fontsize=15); ax.set_ylim(0,1.12)
    ax.tick_params(axis="y", labelsize=13)
    ax.legend(fontsize=13, loc="lower center", bbox_to_anchor=(0.5, 1.01),
              ncol=3, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG/"fig_mech_e3.pdf", bbox_inches="tight"); plt.close(fig)
    print("wrote fig_mech_e3.pdf")

# ---------- Fig B: E6 load sweep (7B, from V3 ladder; K up to 24) ----------
ladder = load("e6_ladder")
e6l = load("e6_load")
if ladder:
    rows = sorted((r for r in ladder if "7B" in r["model"]), key=lambda r: r["K"])
    Ks = [r["K"] for r in rows]
    fig, (a1,a2) = plt.subplots(1,2, figsize=(9,3.6))
    a1.plot(Ks,[r["text_acc"] for r in rows],"o-",color="#2c7fb8",label="text")
    a1.plot(Ks,[r["img_acc"] for r in rows],"s--",color="#d95f0e",label="image")
    a2.plot(Ks,[r["text_lp"] for r in rows],"o-",color="#2c7fb8",label="text")
    a2.plot(Ks,[r["img_lp"] for r in rows],"s--",color="#d95f0e",label="image")
    a1.set_xlabel("facts in context (K)"); a1.set_ylabel("answer top-1 accuracy"); a1.set_title("retrieval accuracy under load"); a1.set_ylim(0,1.05)
    a2.set_xlabel("facts in context (K)"); a2.set_ylabel("answer log-prob"); a2.set_title("answer confidence under load")
    a1.legend(); a2.legend()
    fig.tight_layout(); fig.savefig(FIG/"fig_mech_e6load.pdf"); plt.close(fig)
    print("wrote fig_mech_e6load.pdf (from ladder, K up to 24)")
elif e6l:
    by = {(r["K"],r["cond"]): r for r in e6l}
    Ks = sorted({r["K"] for r in e6l})
    fig, (a1,a2) = plt.subplots(1,2, figsize=(9,3.6))
    for cond,c in [("text","#2c7fb8"),("image","#d95f0e")]:
        a1.plot(Ks,[by[(K,cond)]["acc"] for K in Ks],"o-",color=c,label=cond)
        a2.plot(Ks,[by[(K,cond)]["mean_logprob"] for K in Ks],"o-",color=c,label=cond)
    a1.set_xlabel("facts in context (K)"); a1.set_ylabel("answer top-1 accuracy"); a1.set_title("retrieval accuracy under load")
    a2.set_xlabel("facts in context (K)"); a2.set_ylabel("answer log-prob"); a2.set_title("answer confidence under load")
    a1.legend(); a2.legend()
    fig.tight_layout(); fig.savefig(FIG/"fig_mech_e6load.pdf"); plt.close(fig)
    print("wrote fig_mech_e6load.pdf")

# ---------- Fig C: conditions (C0/C1/E1/E2/E5) ----------
def baseline_of(rs, cell):
    for r in rs or []:
        if r.get("cell")==cell and "baseline" in r: return r["baseline"]
    return None
e1=load("e1"); e2=load("e2"); e5=load("e5")
e1m={r["cell"]:r for r in (e1 or []) if "coverage" in r}
e2m={r["cell"]:r for r in (e2 or []) if "coverage" in r}
e5m={r["cell"]:r for r in (e5 or []) if "coverage" in r}
cells=["mit_6034","3b1b_attention","wagging_tail_9pp","natural_vib_42pp","thermal_66pp","heat_pipes_104pp","arxiv_fairness_53pp","arxiv_perovskite_80pp"]
present=[c for c in cells if e1m.get(c) or e2m.get(c) or e5m.get(c)]
if present:
    fig, ax = plt.subplots(figsize=(11,4))
    x=np.arange(len(present)); w=0.16
    def cov(getter):
        out=[]
        for c in present:
            v=getter(c); out.append(v if v is not None else np.nan)
        return out
    b=lambda c:(e1m.get(c) or e2m.get(c) or e5m.get(c) or {}).get("baseline",{})
    ax.bar(x-2*w,[b(c).get("C0",{}).get("coverage") or np.nan for c in present],w,label="$C_0$ image/audio",color="#d95f0e")
    ax.bar(x-w,[b(c).get("C1",{}).get("coverage") or np.nan for c in present],w,label="$C_1$ text",color="#7fcdbb")
    ax.bar(x,[ (e1m.get(c) or {}).get("coverage", np.nan) for c in present],w,label="$C_{1+}$ both (E1)",color="#2c7fb8")
    ax.bar(x+w,[ (e2m.get(c) or {}).get("coverage", np.nan) for c in present],w,label="single-call (E2)",color="#756bb1")
    ax.bar(x+2*w,[ (e5m.get(c) or {}).get("coverage", np.nan) for c in present],w,label="native-text (E5)",color="#31a354")
    ax.set_xticks(x); ax.set_xticklabels(present, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("probe coverage"); ax.set_ylim(0,1.05); ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5,1.18))
    fig.tight_layout(); fig.savefig(FIG/"fig_mech_conditions.pdf"); plt.close(fig)
    print("wrote fig_mech_conditions.pdf")

# ---------- Fig D: E4 DPI ----------
e4=load("e4")
if e4:
    cells4=sorted({r["cell"] for r in e4 if "coverage" in r})
    fig,(a1,a2)=plt.subplots(1,2,figsize=(9,3.6))
    for c in cells4:
        rs=sorted([r for r in e4 if r.get("cell")==c and "coverage" in r], key=lambda r:r["prompt_tokens"] or 0)
        tok=[r["prompt_tokens"] for r in rs]
        a1.plot(tok,[r["coverage"] for r in rs],"o-",label=c)
        a2.plot(tok,[r["n_unsupported"] for r in rs],"o-",label=c)
    a1.set_xlabel("prompt vision tokens"); a1.set_ylabel("coverage"); a1.set_title("coverage vs vision-token load")
    a2.set_xlabel("prompt vision tokens"); a2.set_ylabel("hallucinations"); a2.set_title("hallucinations vs vision-token load")
    a1.legend(fontsize=7); a2.legend(fontsize=7)
    fig.suptitle("E4: DPI / vision-token sweep at fixed content")
    fig.tight_layout(); fig.savefig(FIG/"fig_mech_e4.pdf"); plt.close(fig)
    print("wrote fig_mech_e4.pdf")
print("done")
