"""New body figures for the reorganized paper.

Generates:
  fig_headline.pdf            (Fig 1: results showcase, page 1)
  fig_substrate_frontier.pdf  (E8/E9 behavioral substrate null on frontier models)
  fig_e2_collapse.pdf         (E2 single-call collapse + E1 dot plot)
  fig_xmodel_grid.pdf         (cross-model generality 2x2 grid)

Data: phase3_data.json, runs/mechanism/e8_*.json, e9_*.json, plus published
per-cell numbers for the Claude-within / 2.5-Flash / mixed-pipeline arms
(same values as the appendix tables).
"""
import json, pathlib
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = json.loads((HERE / "phase3_data.json").read_text())

mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9.5,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 200,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

# Palette (validated: CVD-safe adjacency, shape/label secondary encoding).
C_GEMINI = "#1f77b4"
C_CLAUDE = "#d62728"
C_MIMO   = "#e69f00"
C_GPT    = "#9467bd"
C_C0     = "#8c8c8c"   # end-to-end baseline: deliberately recessive gray
C_WIN    = "#1f77b4"
C_LOSS   = "#d62728"
GRID     = dict(color="#dddddd", lw=0.6, zorder=0)


def _cell(name):
    for c in DATA["cells"]:
        if c["cell"] == name:
            return c
    raise KeyError(name)


AUDIO_ORDER = ["Karpathy mtg-min", "SNAC mtg-min", "Harvard Moot Court",
               "Sapolsky Behavioral", "Karpathy review", "Doudna CRISPR",
               "Stanford Decarb", "MIT 6.034 Winston", "Veritasium Math",
               "3B1B Attention", "NeurIPS BinAI panel"]
PAPER_ORDER = ["arXiv Fairness AI", "SP-5100 Shock", "Dynamic Response",
               "Natural Vibration", "arXiv Megagauss", "Thermal Analysis",
               "Heat Pipes", "Wagging Tail", "Env Test", "arXiv Perovskite"]
NICE = {"Karpathy review": "Karpathy review",
        "Karpathy mtg-min": "Karpathy minutes",
        "SNAC mtg-min": "IETF SNAC minutes",
        "3B1B Attention": "3B1B Attention",
        "NeurIPS BinAI panel": "NeurIPS panel",
        "MIT 6.034 Winston": "MIT 6.034",
        "Sapolsky Behavioral": "Sapolsky genetics",
        "Stanford Decarb": "Stanford decarb.",
        "Doudna CRISPR": "Doudna CRISPR",
        "Veritasium Math": "Veritasium math",
        "Harvard Moot Court": "Harvard moot court",
        "Wagging Tail": "Wagging Tail 9pp",
        "Env Test": "Env Test 18pp",
        "Dynamic Response": "Dynamic Resp. 41pp",
        "Natural Vibration": "Natural Vibr. 42pp",
        "Thermal Analysis": "Thermal 66pp",
        "Heat Pipes": "Heat Pipes 104pp",
        "SP-5100 Shock": "SP-5100 176pp",
        "arXiv Fairness AI": "arXiv Fairness 53pp",
        "arXiv Megagauss": "arXiv Megagauss 75pp",
        "arXiv Perovskite": "arXiv Perovskite 80pp"}


# ============================================================
# Fig 1 (page 1): very simple results showcase across models
# ============================================================
def fig_simple_showcase():
    mpl.rcParams.update({"font.size": 8, "xtick.labelsize": 7,
                         "ytick.labelsize": 7, "axes.labelsize": 8,
                         "axes.titlesize": 8.5, "legend.fontsize": 6.5})
    # per-arm per-cell deltas (C1 - C0); mixed arms are vs Gemini C0
    gem = [(c["scores"]["C1"]["probe_coverage"] - c["scores"]["C0"]["probe_coverage"],
            c["scores"]["C1"]["n_unsupported"] - c["scores"]["C0"]["n_unsupported"])
           for c in DATA["cells"]]
    arms = [
        ("Gemini 3.1 Pro — 21 cells (audio+paper)", C_GEMINI, "o",
         [d[0] for d in gem], [d[1] for d in gem]),
        ("Gemini 2.5 Flash — 5 audio", C_GEMINI, "s",
         [+0.020, -0.021, -0.020, +0.125, +0.020], [-4, +1, +6, -3, -7]),
        ("Claude Opus 4.7 — 6 papers", C_CLAUDE, "o",
         [+0.021, 0.000, -0.040, -0.064, +0.080, 0.000], [-3, -1, -1, -1, -7, +16]),
        ("gpt-audio → Claude — 3 audio", C_CLAUDE, "^",
         [+0.12, +0.35, +0.13], [-9, -7, -14]),
        ("gpt-audio → GPT-5.4 — 3 audio", C_GPT, "^",
         [+0.12, +0.37, +0.13], [-8, -7, -8]),
        ("gpt-audio → Gemini — 3 audio", C_GEMINI, "^",
         [+0.12, +0.27, +0.08], [-6, -8, -12]),
    ]
    fig, (axc, axh) = plt.subplots(1, 2, figsize=(7.0, 2.15), sharey=True)
    rng = np.random.default_rng(11)
    yy = np.arange(len(arms))[::-1]
    for y, (label, col, mk, dcov, dh) in zip(yy, arms):
        jc = (rng.random(len(dcov)) - 0.5) * 0.30
        jh = (rng.random(len(dh)) - 0.5) * 0.30
        axc.scatter(dcov, y + jc, s=16, marker=mk, facecolor=col,
                    edgecolor="white", linewidth=0.4, zorder=3, alpha=0.9)
        axh.scatter(dh, y + jh, s=16, marker=mk, facecolor=col,
                    edgecolor="white", linewidth=0.4, zorder=3, alpha=0.9)
    for ax in (axc, axh):
        ax.axvline(0, color="#999999", lw=0.8)
        ax.grid(axis="x", **GRID)
        ax.set_ylim(-0.7, len(arms) - 0.3)
    axc.set_yticks(yy)
    axc.set_yticklabels([a[0] for a in arms], fontsize=7)
    axc.set_xlabel("$\\Delta$ probe coverage (right of 0 = decomposition better)")
    axh.set_xlabel("$\\Delta$ unsupported claims (left of 0 = better)")
    axc.set_xlim(-0.22, 0.55)
    axh.set_xlim(-16.5, 17.5)
    axc.set_title("(a) Coverage gain, each dot = one review cell", loc="left")
    axh.set_title("(b) Hallucination change", loc="left")
    axh.annotate("Mode B (§5)", xy=(16, yy[2]), xytext=(8.5, yy[2] + 1.0),
                 fontsize=6.5, color="#555555",
                 arrowprops=dict(arrowstyle="-", color="#888888", lw=0.6))
    fig.subplots_adjust(wspace=0.06)
    fig.savefig(HERE / "fig1_showcase.pdf")
    plt.close(fig)
    print("[fig1_showcase] saved")


# ============================================================
# 21-cell dumbbell detail (now the Section-4 results figure)
# ============================================================
def fig_headline():
    mpl.rcParams.update({"font.size": 8, "xtick.labelsize": 7,
                         "ytick.labelsize": 7, "axes.labelsize": 8,
                         "axes.titlesize": 8.5, "legend.fontsize": 6.5})
    fig, (axc, axh) = plt.subplots(1, 2, figsize=(7.0, 3.3))
    fig.subplots_adjust(wspace=0.05)

    cells = AUDIO_ORDER + PAPER_ORDER
    n = len(cells)
    ys = np.arange(n)[::-1]

    for ax, key, better_low in ((axc, "probe_coverage", False),
                                (axh, "n_unsupported", True)):
        for y, name in zip(ys, cells):
            s = _cell(name)["scores"]
            v0, v1 = s["C0"][key], s["C1"][key]
            improved = (v1 < v0) if better_low else (v1 > v0)
            same = abs(v1 - v0) < (1e-9 if not better_low else 0.5)
            col = "#bbbbbb" if same else (C_WIN if improved else C_LOSS)
            ax.plot([v0, v1], [y, y], color=col, lw=1.3, alpha=0.85, zorder=2)
            ax.scatter([v0], [y], s=17, facecolor="white", edgecolor=C_C0,
                       linewidth=1.1, zorder=3)
            ax.scatter([v1], [y], s=17, facecolor=C_GEMINI, edgecolor=C_GEMINI,
                       zorder=4)
        ax.set_ylim(-0.8, n - 0.2)
        ax.grid(axis="x", **GRID)
        # group separator between audio and paper blocks
        ysep = ys[len(AUDIO_ORDER) - 1] - 0.5
        ax.axhline(ysep, color="#999999", lw=0.7, ls=(0, (4, 3)))

    axc.set_yticks(ys)
    labels = [NICE[c] for c in cells]
    axc.set_yticklabels(labels)
    # bold the running example
    for tick, name in zip(axc.get_yticklabels(), cells):
        if name == "Karpathy review":
            tick.set_fontweight("bold")
    axh.set_yticks(ys)
    axh.set_yticklabels([])
    axc.set_xlabel("probe coverage (higher is better)")
    axh.set_xlabel("unsupported claims (lower is better)")
    axc.set_xlim(0.05, 1.03)
    axh.set_xlim(-1.5, 50)

    # group labels
    for ax in (axc, axh):
        x0 = ax.get_xlim()[0]
    axc.text(0.06, ys[0] + 0.65, "Audio (11 cells)", fontsize=7, style="italic",
             color="#555555", va="bottom")
    axc.text(0.06, ys[len(AUDIO_ORDER)] + 0.65, "Papers (10 cells)", fontsize=7,
             style="italic", color="#555555", va="bottom")

    # running-example marker (bold label carries it; small tag beside the row)
    yk = ys[cells.index("Karpathy review")]
    axc.text(0.06, yk, "§2", fontsize=6.5, color="#555555", va="center")

    # legend (shared)
    h0 = plt.Line2D([], [], marker="o", ls="", markerfacecolor="white",
                    markeredgecolor=C_C0, markersize=4.5,
                    label="end-to-end ($C_0$)")
    h1 = plt.Line2D([], [], marker="o", ls="", color=C_GEMINI, markersize=4.5,
                    label="two-pass ($C_1$)")
    hw = plt.Line2D([], [], color=C_WIN, lw=1.3, label="$C_1$ better")
    hl = plt.Line2D([], [], color=C_LOSS, lw=1.3, label="$C_1$ worse")
    axh.legend(handles=[h0, h1, hw, hl], loc="lower right", frameon=False,
               handlelength=1.4, borderaxespad=0.2)

    axc.set_title("(a) Coverage, all 21 Gemini 3.1 Pro cells", loc="left")
    axh.set_title("(b) Hallucinations, same cells", loc="left")

    fig.savefig(HERE / "fig_headline.pdf")
    plt.close(fig)
    print("[fig_headline] saved")


# ============================================================
# E8/E9 frontier behavioral substrate probes
# ============================================================
def fig_substrate_frontier():
    mpl.rcParams.update({"font.size": 8, "xtick.labelsize": 7,
                         "ytick.labelsize": 7, "axes.labelsize": 8,
                         "axes.titlesize": 8.5, "legend.fontsize": 6.5})
    e8g = json.loads((ROOT / "runs/mechanism/e8_frontier_substrate_gemini.json").read_text())
    e8c = json.loads((ROOT / "runs/mechanism/e8_frontier_substrate_claude.json").read_text())
    e9g = json.loads((ROOT / "runs/mechanism/e9_multihop_gemini_sum6.json").read_text())
    e9c = json.loads((ROOT / "runs/mechanism/e9_multihop_claude_sum6.json").read_text())

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.0))
    conds = [("text_acc", "text", C_GEMINI, "o", "-"),
             ("image_acc", "legible image", C_GPT, "s", "--"),
             ("image_degraded_acc", "degraded image (control)", "#8c8c8c", "x", ":")]

    for ax, e8, name in ((axes[0], e8g, "Gemini 3.1 Pro"),
                         (axes[1], e8c, "Claude Opus 4.7")):
        Ks = [r["K"] for r in e8["per_K"]]
        for key, lab, col, mk, ls in conds:
            vals = [r[key] for r in e8["per_K"]]
            off = {"text_acc": 0.012, "image_acc": -0.012}.get(key, 0.0)
            ax.plot(Ks, np.array(vals) + off, marker=mk, ms=3.5, lw=1.3, ls=ls,
                    color=col, label=lab, markerfacecolor="none" if mk != "x" else col)
        ax.set_ylim(-0.05, 1.10)
        ax.set_xticks(Ks)
        ax.set_xlabel("facts packed in context $K$")
        ax.set_title(f"E8 retrieval: {name}", loc="left")
        ax.grid(axis="y", **GRID)
    axes[0].set_ylabel("accuracy")
    axes[0].legend(loc="lower right", frameon=False, fontsize=6,
                   bbox_to_anchor=(1.0, 0.42))
    axes[0].text(24, 0.88, "text = legible image at every $K$", fontsize=6.5,
                 ha="center", color="#333333")
    axes[1].set_yticklabels([])

    # E9 grouped bars
    ax = axes[2]

    def pooled(e9, key):
        vals = [r[key] for r in e9["per_K"]]
        return float(np.mean(vals))

    models = [("Gemini 3.1 Pro", e9g), ("Claude Opus 4.7", e9c)]
    width = 0.26
    xs = np.arange(len(models))
    for i, (key, lab, col, mk, ls) in enumerate(conds):
        vals = [pooled(e9, key) for _, e9 in models]
        b = ax.bar(xs + (i - 1) * width, vals, width * 0.92, color=col,
                   edgecolor="white", linewidth=0.8, zorder=3)
        for rect, v in zip(b, vals):
            ax.text(rect.get_x() + rect.get_width() / 2, v + 0.02, f"{v:.2f}",
                    ha="center", fontsize=6, color="#333333")
    ax.set_xticks(xs)
    ax.set_xticklabels([m for m, _ in models], fontsize=8)
    ax.set_ylim(0, 1.12)
    ax.set_yticklabels([])
    ax.set_title("E9 multi-hop (sum of 6 facts)", loc="left")
    ax.grid(axis="y", **GRID)
    ax.annotate("image $>$ text\nwith headroom", xy=(1.0 + 0.26 * 0, 1.01),
                xytext=(0.30, 0.44), fontsize=6.5, color="#333333",
                arrowprops=dict(arrowstyle="-", color="#888888", lw=0.7,
                                shrinkB=2))

    fig.subplots_adjust(wspace=0.12)
    fig.savefig(HERE / "fig_substrate_frontier.pdf")
    plt.close(fig)
    print("[fig_substrate_frontier] saved")


# ============================================================
# E2/E1: single-call collapse dot plot (8-cell grid + n=5 aggregate note)
# ============================================================
def fig_e2_collapse():
    # (cell, C0, C1, C1plus, single_call)  None = not run, "budget" = no review
    rows = [
        ("MIT 6.034 (audio)",      0.77, 0.98, None,  "budget"),
        ("3B1B Attention (audio)", 0.88, 0.96, 1.00,  0.80),
        ("Wagging Tail 9pp",       0.80, 0.78, 0.78,  0.63),
        ("Natural Vibr. 42pp",     0.66, 0.49, 0.79,  "budget"),
        ("Thermal 66pp",           0.68, 0.84, 0.68,  0.40),
        ("Heat Pipes 104pp",       0.72, 0.78, 0.66,  "budget"),
        ("arXiv Fairness 53pp",    0.50, 0.40, 0.38,  0.24),
        ("arXiv Perovskite 80pp",  0.90, 0.74, 0.84,  0.80),
    ]
    mpl.rcParams.update({"font.size": 9, "xtick.labelsize": 8,
                         "ytick.labelsize": 8, "axes.labelsize": 9,
                         "axes.titlesize": 9.5, "legend.fontsize": 8})
    fig, ax = plt.subplots(figsize=(6.0, 2.7))
    ys = np.arange(len(rows))[::-1]
    for y, (name, c0, c1, c1p, sc) in zip(ys, rows):
        ax.plot([0.02, 1.02], [y, y], color="#eeeeee", lw=5, zorder=0,
                solid_capstyle="round")
        ax.scatter([c0], [y], s=42, facecolor="white", edgecolor=C_C0,
                   linewidth=1.3, zorder=3)
        ax.scatter([c1], [y], s=46, facecolor=C_GEMINI, edgecolor=C_GEMINI, zorder=4)
        if c1p is not None:
            ax.scatter([c1p], [y], s=42, facecolor="none", edgecolor=C_GPT,
                       marker="D", linewidth=1.4, zorder=3)
        if sc == "budget":
            ax.text(0.035, y, "× no review (budget exhausted)",
                    fontsize=7, color=C_LOSS, va="center")
        else:
            ax.scatter([sc], [y], s=42, facecolor=C_LOSS, edgecolor=C_LOSS,
                       marker="s", zorder=4)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xlim(0.0, 1.04)
    ax.set_xlabel("probe coverage")
    ax.grid(axis="x", **GRID)

    handles = [
        plt.Line2D([], [], marker="o", ls="", markerfacecolor="white",
                   markeredgecolor=C_C0, markersize=6, label="$C_0$ end-to-end"),
        plt.Line2D([], [], marker="o", ls="", color=C_GEMINI, markersize=6,
                   label="$C_1$ two-pass"),
        plt.Line2D([], [], marker="D", ls="", markerfacecolor="none",
                   markeredgecolor=C_GPT, markersize=6,
                   label="$C_{1+}$ transcript+modality (E1)"),
        plt.Line2D([], [], marker="s", ls="", color=C_LOSS, markersize=6,
                   label="single call: transcribe then review (E2)"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, -0.28),
              frameon=False, ncol=2, fontsize=7.5)
    fig.savefig(HERE / "fig_e2_collapse.pdf")
    plt.close(fig)
    print("[fig_e2_collapse] saved")


# ============================================================
# Cross-model generality 2x2 grid
# ============================================================
def fig_xmodel_grid():
    mpl.rcParams.update({"font.size": 8, "xtick.labelsize": 7,
                         "ytick.labelsize": 7, "axes.labelsize": 8,
                         "axes.titlesize": 8.5, "legend.fontsize": 6.5})
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.6))
    fig.subplots_adjust(hspace=0.68, wspace=0.30)

    # ---- (a) Thermal 66pp: all three vendors improve ----
    ax = axes[0, 0]
    th = _cell("Thermal Analysis")["scores"]
    vendors = [("Gemini 3.1 Pro", "C0", "C1", C_GEMINI),
               ("Claude Opus 4.7", "C0_claude", "C1_claude", C_CLAUDE),
               ("Mimo v2-omni", "C0_mimo", "C1_mimo", C_MIMO)]
    xs = np.arange(len(vendors))
    w = 0.32
    for i, (name, k0, k1, col) in enumerate(vendors):
        c0, c1 = th[k0]["probe_coverage"], th[k1]["probe_coverage"]
        h0, h1 = th[k0]["n_unsupported"], th[k1]["n_unsupported"]
        ax.bar(i - w / 2, c0, w * 0.92, facecolor="white", edgecolor=col,
               linewidth=1.3, zorder=3)
        ax.bar(i + w / 2, c1, w * 0.92, facecolor=col, edgecolor="white",
               linewidth=0.8, zorder=3)
        ax.text(i - w / 2, c0 + 0.02, f"{h0}h", ha="center", fontsize=7,
                color="#333333")
        ax.text(i + w / 2, c1 + 0.02, f"{h1}h", ha="center", fontsize=7,
                color="#333333")
    ax.set_xticks(xs)
    ax.set_xticklabels([v[0] for v in vendors], fontsize=8)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("probe coverage")
    ax.grid(axis="y", **GRID)
    ax.set_title("(a) Thermal 66pp: every vendor improves\n(open = $C_0$, filled = $C_1$; "
                 "labels = hallucinations)", loc="left", fontsize=8.5)

    # ---- (b) within-Claude, 6 NASA papers: hallucination dumbbells ----
    ax = axes[0, 1]
    cw = [("Wagging Tail 9pp", 5, 2), ("Env Test 18pp", 3, 2),
          ("Dynamic Resp. 41pp", 2, 1), ("Natural Vibr. 42pp", 5, 4),
          ("Thermal 66pp", 11, 4), ("Heat Pipes 104pp", 4, 20)]
    ys = np.arange(len(cw))[::-1]
    for y, (name, h0, h1) in zip(ys, cw):
        col = C_WIN if h1 < h0 else C_LOSS
        ax.plot([h0, h1], [y, y], color=col, lw=1.6, zorder=2)
        ax.scatter([h0], [y], s=38, facecolor="white", edgecolor=C_C0,
                   linewidth=1.3, zorder=3)
        ax.scatter([h1], [y], s=40, facecolor=C_CLAUDE, edgecolor=C_CLAUDE, zorder=4)
    ax.set_yticks(ys)
    ax.set_yticklabels([c[0] for c in cw], fontsize=8)
    ax.set_xlabel("unsupported claims")
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.grid(axis="x", **GRID)
    ax.annotate("Mode B (§5)", xy=(20, ys[-1]), xytext=(14.5, ys[-1] + 1.1),
                fontsize=7.5, color=C_LOSS,
                arrowprops=dict(arrowstyle="-", color=C_LOSS, lw=0.7))
    ax.set_title("(b) Within Claude Opus 4.7: fewer hallucinations\non 5/6 papers "
                 "(open = $C_0$, filled = $C_1$)", loc="left", fontsize=8.5)

    # ---- (c) Gemini 2.5 Flash audio: headroom-gated ----
    ax = axes[1, 0]
    fl = [("3B1B", 0.900, 0.020), ("NeurIPS", 0.980, -0.021),
          ("Karpathy", 0.922, -0.020), ("MIT", 0.833, 0.125),
          ("Harvard", 0.600, 0.020)]
    pro = []
    for c in DATA["cells"]:
        if c.get("modality") == "audio" and "C0" in c["scores"] and "C1" in c["scores"]:
            pro.append((c["scores"]["C0"]["probe_coverage"],
                        c["scores"]["C1"]["probe_coverage"] -
                        c["scores"]["C0"]["probe_coverage"]))
    ax.scatter([p[0] for p in pro], [p[1] for p in pro], s=26, facecolor="none",
               edgecolor=C_GEMINI, linewidth=1.1, label="3.1 Pro (11 audio cells)")
    ax.scatter([f[1] for f in fl], [f[2] for f in fl], s=42, facecolor=C_GEMINI,
               edgecolor="white", linewidth=0.6, marker="s",
               label="2.5 Flash (5 cells)")
    for name, x, y in fl:
        if name in ("MIT", "Harvard", "Karpathy"):
            ax.annotate(name, (x, y), textcoords="offset points", xytext=(5, 3),
                        fontsize=7, color="#333333")
    ax.axhline(0, color="#999999", lw=0.8)
    ax.set_xlabel("end-to-end baseline $C_0$ coverage")
    ax.set_ylabel("$\\Delta_{\\rm cov}$ ($C_1 - C_0$)")
    ax.grid(axis="y", **GRID)
    ax.legend(loc="upper right", frameon=False, fontsize=7)
    ax.set_title("(c) Audio, two Gemini models: gain tracks\nheadroom, not model "
                 "identity", loc="left", fontsize=8.5)

    # ---- (d) mixed pipelines vs Gemini end-to-end ----
    ax = axes[1, 1]
    cellsm = ["3B1B", "Karpathy", "MIT 6.034"]
    series = [("Gemini $C_0$ (end-to-end)", C_C0,   [0.88, 0.63, 0.77], [11, 13, 17]),
              ("→ Claude Pass-2",       C_CLAUDE, [1.00, 0.98, 0.90], [2, 6, 3]),
              ("→ GPT-5.4 Pass-2",      C_GPT,    [1.00, 1.00, 0.90], [3, 6, 9]),
              ("→ Gemini Pass-2",       C_GEMINI, [1.00, 0.90, 0.85], [5, 5, 5])]
    xs = np.arange(len(cellsm))
    w = 0.19
    for i, (lab, col, covs, hs) in enumerate(series):
        pos = xs + (i - 1.5) * w
        fc = "white" if i == 0 else col
        ec = col if i == 0 else "white"
        ax.bar(pos, covs, w * 0.9, facecolor=fc, edgecolor=ec,
               linewidth=1.1 if i == 0 else 0.7, zorder=3,
               label=lab)
        for x, v, h in zip(pos, covs, hs):
            ax.text(x, v + 0.02, f"{h}h", ha="center", fontsize=6.5, color="#333333")
    ax.set_xticks(xs)
    ax.set_xticklabels(cellsm, fontsize=8)
    ax.set_ylim(0, 1.19)
    ax.set_ylabel("probe coverage")
    ax.grid(axis="y", **GRID)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), frameon=False,
              fontsize=7, ncol=2)
    ax.set_title("(d) gpt-audio transcript unlocks text-only models:\nevery pipeline "
                 "beats end-to-end (labels = hallucinations)", loc="left", fontsize=8.5)

    fig.savefig(HERE / "fig_xmodel_grid.pdf")
    plt.close(fig)
    print("[fig_xmodel_grid] saved")


if __name__ == "__main__":
    fig_simple_showcase()
    fig_headline()
    fig_substrate_frontier()
    fig_e2_collapse()
    fig_xmodel_grid()
