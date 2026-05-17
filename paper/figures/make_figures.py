"""Generate NeurIPS-style figures for the cascade-gap paper."""
import json, pathlib
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
DATA = json.loads((HERE / "phase3_data.json").read_text())

# NeurIPS-style settings: 9pt fonts, single-column 5.5in width, b/w-friendly.
mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
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

# Color palette (b/w-friendly with marker shape variation)
C_GEMINI = "#1f77b4"   # blue
C_CLAUDE = "#d62728"   # red
C_MIMO   = "#2ca02c"   # green
C_GPT    = "#9467bd"   # purple


def _cell(name):
    for c in DATA["cells"]:
        if c["cell"] == name:
            return c
    raise KeyError(name)


# ============================================================
# Figure 1: Inverse correlation between C0 baseline coverage
# and cascade coverage gain (Δ_cov), across the 9 Phase-3 Gemini cells.
# Includes the Natural Vibration counter-cell.
# ============================================================
def fig1_inverse_correlation():
    """Cascade coverage gain vs baseline. n=21 cells, colored by modality.
    Adds OLS regression line + bootstrap 95% CI band on slope.
    """
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    audio_cells, paper_cells = [], []
    for c in DATA["cells"]:
        s = c["scores"]
        if "C0" not in s or "C1" not in s:
            continue
        c0 = s["C0"]["probe_coverage"]
        c1 = s["C1"]["probe_coverage"]
        entry = (c["cell"], c0, c1, c1 - c0)
        if c.get("modality") == "audio":
            audio_cells.append(entry)
        else:
            paper_cells.append(entry)

    audio_c0 = np.array([c[1] for c in audio_cells])
    audio_d  = np.array([c[3] for c in audio_cells])
    paper_c0 = np.array([c[1] for c in paper_cells])
    paper_d  = np.array([c[3] for c in paper_cells])

    # OLS regression on all cells
    x = np.concatenate([audio_c0, paper_c0])
    y = np.concatenate([audio_d, paper_d])
    r = np.corrcoef(x, y)[0, 1]
    slope, intercept = np.polyfit(x, y, 1)
    xs = np.linspace(0.10, 1.0, 80)
    ys = slope * xs + intercept

    # Bootstrap CI band on the regression line
    rng = np.random.default_rng(42)
    boot_lines = []
    for _ in range(2000):
        idx = rng.integers(0, len(x), len(x))
        sl, ic = np.polyfit(x[idx], y[idx], 1)
        boot_lines.append(sl * xs + ic)
    boot_lines = np.array(boot_lines)
    lo = np.percentile(boot_lines, 2.5, axis=0)
    hi = np.percentile(boot_lines, 97.5, axis=0)

    ax.fill_between(xs, lo, hi, color="#cccccc", alpha=0.5, zorder=1, label="95% bootstrap CI")
    ax.plot(xs, ys, color="#555555", linewidth=1.0, zorder=2,
            label=f"OLS: $\\Delta_{{cov}}={slope:+.2f}\\,C_0{intercept:+.2f}$\n   $r={r:.2f}$")

    # Points
    ax.scatter(audio_c0, audio_d, s=42, color=C_GEMINI, marker="o",
               edgecolor="black", linewidth=0.4, zorder=3, label=f"audio (n={len(audio_cells)})")
    ax.scatter(paper_c0, paper_d, s=42, color=C_CLAUDE, marker="s",
               edgecolor="black", linewidth=0.4, zorder=3, label=f"paper (n={len(paper_cells)})")

    # Annotations only on negative-cascade outliers
    outlier_offsets = {
        "Natural Vibration": (-0.18, -0.005),
        "Wagging Tail": (-0.16, -0.005),
        "arXiv Fairness AI": (0.012, 0.0),
        "arXiv Perovskite": (-0.22, 0.005),
        "Heat Pipes": (0.012, -0.020),
        "Karpathy review": (0.012, 0.0),
        "Harvard Moot Court": (0.012, 0.0),
        "3B1B Attention": (-0.22, -0.005),
    }
    for cells in (audio_cells, paper_cells):
        for name, c0, c1, delta in cells:
            if name in outlier_offsets:
                dx, dy = outlier_offsets[name]
                ax.text(c0 + dx, delta + dy, name, fontsize=6.0,
                        color="#222222", va="center")

    ax.axhline(0, color="#888888", linewidth=0.5, linestyle="--")
    ax.set_xlabel(r"$C_0$ probe coverage (end-to-end baseline)")
    ax.set_ylabel(r"$\Delta_{\rm cov}=C_1-C_0$")
    ax.set_title(f"Cascade coverage gain vs. $C_0$ baseline (n={len(audio_cells) + len(paper_cells)} Gemini cells)")
    ax.set_xlim(0.10, 1.0)
    ax.set_ylim(-0.22, 0.55)
    ax.grid(alpha=0.25, linewidth=0.4)
    ax.legend(loc="upper right", fontsize=7, frameon=False)

    fig.savefig(HERE / "fig1_inverse_correlation.pdf")
    plt.close(fig)
    print("[fig1] saved")


# ============================================================
# Figure 2: Cross-vendor on the moderate-length paper (Thermal Analysis 66pp)
# Bar chart with C0 (lighter) vs C1 (darker) per vendor.
# ============================================================
def fig2_cross_vendor_thermal():
    fig, ax = plt.subplots(figsize=(3.2, 2.4))
    therm = _cell("Thermal Analysis")
    s = therm["scores"]

    vendors = ["Gemini", "Claude", "Mimo"]
    c0_keys = ["C0", "C0_claude", "C0_mimo"]
    c1_keys = ["C1", "C1_claude", "C1_mimo"]
    colors = [C_GEMINI, C_CLAUDE, C_MIMO]

    x = np.arange(3)
    width = 0.35

    c0_covs = [s[k]["probe_coverage"] for k in c0_keys]
    c1_covs = [s[k]["probe_coverage"] for k in c1_keys]

    ax.bar(x - width/2, c0_covs, width, color="white", edgecolor=colors,
           linewidth=1.6, label=r"$C_0$ (end-to-end)", hatch="//")
    ax.bar(x + width/2, c1_covs, width, color=colors,
           label=r"$C_1$ (cascade)")

    # Numeric labels above bars
    for xi, v in zip(x - width/2, c0_covs):
        ax.text(xi, v + 0.015, f"{v:.2f}", ha="center", fontsize=6.5)
    for xi, v in zip(x + width/2, c1_covs):
        ax.text(xi, v + 0.015, f"{v:.2f}", ha="center", fontsize=6.5)

    ax.set_xticks(x)
    ax.set_xticklabels(vendors)
    ax.set_ylabel("Probe coverage")
    ax.set_ylim(0, 1.10)
    ax.set_title(r"$C_0$ vs $C_1$ on Thermal Analysis (66pp), 3 vendors")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(alpha=0.25, axis="y", linewidth=0.4)

    fig.savefig(HERE / "fig2_xvendor_thermal.pdf")
    plt.close(fig)
    print("[fig2] saved")


# ============================================================
# Figure 3: Heat Pipes 104pp Pareto frontier across vendors and variants.
# Shows the failure-mode taxonomy: Mode A (Gemini), Mode B (Claude), Mode A+B (Mimo).
# ============================================================
def fig3_heatpipes_pareto():
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    hp = _cell("Heat Pipes")
    s = hp["scores"]

    points = [
        # (label, halluc, cov, vendor, marker, fillstyle)
        ("$C_0$",        s["C0"]["n_unsupported"],        s["C0"]["probe_coverage"],        "Gemini", "o", "none"),
        ("$C_1$",        s["C1"]["n_unsupported"],        s["C1"]["probe_coverage"],        "Gemini", "o", "full"),
        ("$C_{1c}$",     s["C1c"]["n_unsupported"],       s["C1c"]["probe_coverage"],       "Gemini", "s", "full"),
        ("$C_{1c}^{\\rm concat}$", s["C1c_concat"]["n_unsupported"], s["C1c_concat"]["probe_coverage"], "Gemini", "D", "full"),
        ("$C_0$",        s["C0_claude"]["n_unsupported"], s["C0_claude"]["probe_coverage"], "Claude", "o", "none"),
        ("$C_1$",        s["C1_claude"]["n_unsupported"], s["C1_claude"]["probe_coverage"], "Claude", "o", "full"),
        ("$C_1^{\\rm strip}$", s["C1_stripped_claude"]["n_unsupported"], s["C1_stripped_claude"]["probe_coverage"], "Claude", "v", "full"),
        ("$C_{1c}$",     s["C1c_claude"]["n_unsupported"], s["C1c_claude"]["probe_coverage"], "Claude", "s", "full"),
        ("$C_0$",        s["C0_mimo"]["n_unsupported"],    s["C0_mimo"]["probe_coverage"],    "Mimo",   "o", "none"),
        ("$C_1$",        s["C1_mimo"]["n_unsupported"],    s["C1_mimo"]["probe_coverage"],    "Mimo",   "o", "full"),
    ]
    color_for = {"Gemini": C_GEMINI, "Claude": C_CLAUDE, "Mimo": C_MIMO}

    # Plot points
    seen_labels = set()
    for label, h, cov, vendor, marker, fill in points:
        leg = f"{vendor}" if vendor not in seen_labels else None
        seen_labels.add(vendor)
        ax.scatter([cov], [h], marker=marker, s=70,
                   facecolor=("white" if fill == "none" else color_for[vendor]),
                   edgecolor=color_for[vendor], linewidth=1.4,
                   label=leg, zorder=3)

    # Annotations
    annot_offsets = {
        # (label, vendor, halluc): (dx, dy)
        ("$C_0$", "Gemini"):     (-0.06, -1.0),
        ("$C_1$", "Gemini"):     (-0.05,  0.7),
        ("$C_{1c}$", "Gemini"):  (-0.10, -0.5),
        ("$C_{1c}^{\\rm concat}$", "Gemini"): (0.005, -0.7),
        ("$C_0$", "Claude"):     (0.006, 0.0),
        ("$C_1$", "Claude"):     (-0.05, 0.9),
        ("$C_1^{\\rm strip}$", "Claude"): (-0.10, 1.0),
        ("$C_{1c}$", "Claude"):  (0.006, 0.4),
        ("$C_0$", "Mimo"):       (0.006, 0.0),
        ("$C_1$", "Mimo"):       (0.006, 0.0),
    }
    for label, h, cov, vendor, marker, fill in points:
        dx, dy = annot_offsets.get((label, vendor), (0.006, 0.4))
        ax.annotate(label, (cov, h), xytext=(cov + dx, h + dy),
                    fontsize=6.5, color=color_for[vendor])

    ax.set_xlabel("Probe coverage  (higher is better →)")
    ax.set_ylabel("Hallucinations  (← lower is better)")
    ax.invert_yaxis()
    ax.set_xlim(0.20, 1.0)
    ax.set_ylim(24, -1)
    ax.set_title("Heat Pipes 104pp: cascade variants × 3 vendors")
    ax.legend(loc="lower left", frameon=False, title="Vendor")
    ax.grid(alpha=0.25, linewidth=0.4)

    fig.savefig(HERE / "fig3_heatpipes_pareto.pdf")
    plt.close(fig)
    print("[fig3] saved")


# ============================================================
# Figure 4: Failure-mode bar chart — show the two distinct
# failure modes across the relevant cells.
# ============================================================
def fig4_failure_modes():
    fig, axes = plt.subplots(1, 2, figsize=(6.0, 2.4), sharey=False)

    # Left panel: Mode A on Heat Pipes (Gemini variants showing chunked-Pass-2 fix)
    hp = _cell("Heat Pipes")["scores"]
    variants = ["C0", "C1", "C1c", "C1c_concat"]
    labels = ["$C_0$", "$C_1$", "$C_{1c}$", "$C_{1c}^{\\rm concat}$"]
    halluc = [hp[k]["n_unsupported"] for k in variants]
    cov    = [hp[k]["probe_coverage"]  for k in variants]

    ax = axes[0]
    x = np.arange(len(variants))
    width = 0.36
    ax.bar(x - width/2, halluc, width, color=C_GEMINI, label="Halluc.")
    ax2 = ax.twinx()
    ax2.bar(x + width/2, cov, width, color="lightgray", edgecolor=C_GEMINI, label="Coverage")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Hallucinations")
    ax.set_ylim(0, max(halluc) + 4)
    ax2.set_ylabel("Coverage")
    ax2.set_ylim(0, 1.05)
    ax.spines["top"].set_visible(False); ax2.spines["top"].set_visible(False)
    ax.set_title("Mode A: compression bottleneck\n(Gemini, Heat Pipes 104pp)")

    # Right panel: Mode B on Heat Pipes (Claude variants showing citation-strip fix)
    cp = _cell("Heat Pipes")["scores"]
    variants_c = ["C0_claude", "C1_claude", "C1_stripped_claude", "C1c_claude"]
    labels_c = ["$C_0$", "$C_1$", "$C_1^{\\rm strip}$", "$C_{1c}$"]
    halluc_c = [cp[k]["n_unsupported"] for k in variants_c]
    cov_c    = [cp[k]["probe_coverage"]  for k in variants_c]

    ax = axes[1]
    x = np.arange(len(variants_c))
    ax.bar(x - width/2, halluc_c, width, color=C_CLAUDE, label="Halluc.")
    ax3 = ax.twinx()
    ax3.bar(x + width/2, cov_c, width, color="lightgray", edgecolor=C_CLAUDE)
    ax.set_xticks(x)
    ax.set_xticklabels(labels_c, fontsize=8)
    ax.set_ylabel("Hallucinations")
    ax.set_ylim(0, max(halluc_c) + 4)
    ax3.set_ylabel("Coverage")
    ax3.set_ylim(0, 1.05)
    ax.spines["top"].set_visible(False); ax3.spines["top"].set_visible(False)
    ax.set_title("Mode B: training-prior leak\n(Claude, Heat Pipes 104pp)")

    fig.tight_layout()
    fig.savefig(HERE / "fig4_failure_modes.pdf")
    plt.close(fig)
    print("[fig4] saved")


def fig5_cost_pareto():
    """Cost-Pareto: per-cell API call count vs cascade coverage gain.
    Cascade requires N+1 calls for an N-page paper (N OCR + 1 Pass-2);
    end-to-end requires 1 call. The chunked variant requires N+K+1 calls
    (N OCR + K sub-summary + 1 merge). The figure shows that the
    coverage gain is bought with a roughly N-fold call-count multiplier.
    """
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    audio_pts, paper_pts = [], []
    for c in DATA["cells"]:
        s = c["scores"]
        if "C0" not in s or "C1" not in s:
            continue
        c0_cov = s["C0"]["probe_coverage"]
        c1_cov = s["C1"]["probe_coverage"]
        d_cov = c1_cov - c0_cov
        # Estimated C1 / C0 API-call count ratio.
        # Audio: ASR is 1 call per 30-min chunk; review is 1 call.
        # Paper: OCR is 1 call per page; review is 1 call.
        if c.get("modality") == "audio":
            src = c.get("source_words") or 1
            # 30-min chunk ≈ 4500 words at conversational speech rate
            n_chunks = max(1, round(src / 4500))
            c0_calls = 1
            c1_calls = n_chunks + 1
            audio_pts.append((c1_calls / c0_calls, d_cov, c["cell"], n_chunks))
        else:
            n_pages = c.get("page_count") or 1
            c0_calls = 1
            c1_calls = n_pages + 1
            paper_pts.append((c1_calls / c0_calls, d_cov, c["cell"], n_pages))

    audio_x = [p[0] for p in audio_pts]
    audio_y = [p[1] for p in audio_pts]
    paper_x = [p[0] for p in paper_pts]
    paper_y = [p[1] for p in paper_pts]

    ax.scatter(audio_x, audio_y, s=40, color=C_GEMINI, marker="o",
               edgecolor="black", linewidth=0.4, label=f"audio (n={len(audio_pts)})", zorder=3)
    ax.scatter(paper_x, paper_y, s=40, color=C_CLAUDE, marker="s",
               edgecolor="black", linewidth=0.4, label=f"paper (n={len(paper_pts)})", zorder=3)

    # Annotate outlier high-cost cells
    for pts in (paper_pts, audio_pts):
        for x, y, name, n in pts:
            if x >= 50 or abs(y) >= 0.30:
                ax.text(x * 1.06, y, name, fontsize=6.0, va="center")

    ax.axhline(0, color="#888888", linewidth=0.5, linestyle="--")
    ax.set_xscale("log")
    ax.set_xlabel(r"$C_1$ / $C_0$ API call-count ratio (log)")
    ax.set_ylabel(r"$\Delta_{\rm cov} = C_1 - C_0$")
    ax.set_title("Coverage gain vs.\\ cascade call-count cost (21 Gemini cells)")
    ax.grid(alpha=0.25, linewidth=0.4, which="both")
    ax.legend(loc="lower left", frameon=False, fontsize=8)

    fig.savefig(HERE / "fig5_cost_pareto.pdf")
    plt.close(fig)
    print("[fig5] saved")


# ============================================================
# Figure 0: Protocol schematic — C0 vs C1 boxes-and-arrows diagram.
# ============================================================
def fig0_protocol_schematic():
    # Single wide axis with two side-by-side diagrams.
    fig, ax = plt.subplots(figsize=(7.0, 2.6))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 7.5)
    ax.axis("off")

    def box(x, y, w, h, fc, ec, text, fontsize=8, textcolor="black"):
        ax.add_patch(plt.Rectangle((x, y), w, h, fc=fc, ec=ec, lw=1.2))
        ax.text(x + w/2, y + h/2, text, ha="center", va="center",
                fontsize=fontsize, color=textcolor)

    # ---- LEFT: C0 end-to-end ----
    ax.text(5.0, 7.0, r"$C_0$: end-to-end", ha="center", fontsize=10, fontweight="bold")
    box(0.3, 3.0, 2.4, 1.8, "#eef4fa", C_GEMINI, "audio /\npaper imgs", fontsize=8)
    box(3.7, 2.7, 2.8, 2.4, C_GEMINI, "black", "model\n(multimodal)", fontsize=8, textcolor="white")
    box(7.5, 3.0, 2.4, 1.8, "#fff4f4", C_CLAUDE, "review\narticle", fontsize=8)
    ax.annotate("", xy=(3.6, 3.9), xytext=(2.75, 3.9),
                arrowprops=dict(arrowstyle="->", color="black", lw=1.1))
    ax.annotate("", xy=(7.45, 3.9), xytext=(6.55, 3.9),
                arrowprops=dict(arrowstyle="->", color="black", lw=1.1))
    ax.text(5.0, 1.8, "1 call", ha="center", fontsize=8, color="#444444", style="italic")

    # Divider
    ax.plot([10.7, 10.7], [0.3, 6.7], color="#dddddd", linewidth=1.0)

    # ---- RIGHT: C1 cascade ----
    ax.text(16.5, 7.0, r"$C_1$: same-weights cascade (Pass-1 $\to$ Pass-2)",
            ha="center", fontsize=10, fontweight="bold")
    # Source on the left
    box(11.2, 3.0, 2.4, 1.8, "#eef4fa", C_GEMINI, "audio /\npaper imgs", fontsize=8)
    # Pass-1 model (top)
    box(14.7, 4.6, 2.6, 1.6, C_GEMINI, "black", "model Pass-1\n(ASR / OCR)", fontsize=7.5, textcolor="white")
    # Transcript box (middle, between top and bottom)
    box(18.4, 3.0, 2.0, 1.8, "#fffbee", "#cc8800", "text\ntranscript", fontsize=8)
    # Pass-2 model (bottom)
    box(14.7, 1.4, 2.6, 1.6, C_GEMINI, "black", "model Pass-2\n(text-only)", fontsize=7.5, textcolor="white")
    # Review (far right, below transcript)
    box(11.2, 0.5, 2.4, 1.8, "#fff4f4", C_CLAUDE, "review\narticle", fontsize=8)

    # Arrows
    # source -> Pass-1
    ax.annotate("", xy=(14.65, 5.4), xytext=(13.65, 4.5),
                arrowprops=dict(arrowstyle="->", color="black", lw=1.0))
    # Pass-1 -> transcript
    ax.annotate("", xy=(18.35, 4.0), xytext=(17.35, 5.0),
                arrowprops=dict(arrowstyle="->", color="black", lw=1.0))
    # transcript -> Pass-2
    ax.annotate("", xy=(17.35, 2.5), xytext=(18.35, 3.5),
                arrowprops=dict(arrowstyle="->", color="black", lw=1.0))
    # Pass-2 -> review
    ax.annotate("", xy=(13.65, 1.4), xytext=(14.65, 1.9),
                arrowprops=dict(arrowstyle="->", color="black", lw=1.0))
    # Cost label
    ax.text(16.5, 0.0, "$N+1$ calls  (page-chunked OCR / 30-min ASR chunks + 1 text Pass-2)",
            ha="center", fontsize=7.5, color="#444444", style="italic")

    fig.savefig(HERE / "fig0_protocol_schematic.pdf")
    plt.close(fig)
    print("[fig0] saved")


# ============================================================
# Figure 6: Multi-seed (n=5) envelopes for the 4 verification cells.
# Strip on NV (Gemini) + chunked-concat on 3 arXiv cells.
# ============================================================
def fig6_multiseed_envelopes():
    # Cell sources
    sources = [
        ("Natural Vibration / strip",
         "runs/paper-review-19690013408-1777471789/multi_seed_C1_stripped_ms.json",
         12, 0.809, 5, 0.489),   # orig_n1_h, orig_n1_cov, c1_base_h, c1_base_cov
        ("Fairness AI / chunked-concat",
         "runs/paper-review-2605.09852-1778859219/multi_seed_C1c_concat_ms.json",
         37, 0.520, 15, 0.400),
        ("Megagauss / chunked-concat",
         "runs/paper-review-2605.11379-1778859223/multi_seed_C1c_concat_ms.json",
         36, 0.740, 32, 0.680),
        ("Perovskite / chunked-concat",
         "runs/paper-review-2605.13991-1778859221/multi_seed_C1c_concat_ms.json",
         13, 0.820, 3, 0.740),
    ]

    fig, axes = plt.subplots(1, 4, figsize=(7.5, 2.2), sharey=False)
    for ax, (label, path, orig_h, orig_cov, c1h, c1c) in zip(axes, sources):
        runs = json.loads((HERE.parent.parent / path).read_text())["runs"]
        seeds = sorted(runs, key=lambda r: r["seed"])
        hs = [r["n_unsupported"] for r in seeds]
        cs = [r["probe_coverage"] for r in seeds]
        x_jitter = np.arange(1, 6) * 0.0  # not used; we plot in 2D (cov, halluc)

        # Twin-axis style: instead show as 2D (cov on x, halluc on y, inverted)
        ax.scatter(cs, hs, s=42, color=C_GEMINI, marker="o",
                   edgecolor="black", linewidth=0.4, zorder=3, label="n=5 seeds")
        # mean cross
        mc, mh = float(np.mean(cs)), float(np.mean(hs))
        ax.scatter([mc], [mh], s=120, marker="x", color="black",
                   linewidth=1.4, zorder=4, label="n=5 mean")
        # original n=1 marker
        ax.scatter([orig_cov], [orig_h], s=70, color=C_CLAUDE, marker="*",
                   edgecolor="black", linewidth=0.4, zorder=4, label=r"orig $n{=}1$ (T=0)")
        # baseline C1 marker
        ax.scatter([c1c], [c1h], s=50, color="white", marker="o",
                   edgecolor="#555555", linewidth=0.8, zorder=2, label=r"baseline $C_1$")

        ax.set_xlabel("cov  (→)", fontsize=8)
        ax.set_ylabel("halluc  (↓)", fontsize=8)
        ax.invert_yaxis()
        # Tight axis to include all points with margin
        all_h = hs + [orig_h, c1h]
        all_c = cs + [orig_cov, c1c]
        ax.set_xlim(min(all_c) - 0.05, max(all_c) + 0.05)
        ax.set_ylim(max(all_h) + 3, min(all_h) - 3)
        ax.set_title(label, fontsize=8)
        ax.grid(alpha=0.25, linewidth=0.4)

    # Single shared legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.07),
               ncol=4, frameon=False, fontsize=8)

    fig.tight_layout()
    fig.savefig(HERE / "fig6_multiseed_envelopes.pdf")
    plt.close(fig)
    print("[fig6] saved")


# ============================================================
# Figure 7: Three sources of stochasticity (Claude Pass-2, Gemini Pass-2,
# GPT-5.4 judge variance on the same review file).
# ============================================================
def fig7_stochasticity_decomp():
    # Data from the paper Section 3.5 stochasticity table:
    # Claude Pass-2 generation variance (different reviews, judged once each)
    claude_pass2 = {
        "Heat Pipes $C_1$":  [9, 11, 11, 15, 20],   # n=5 from previous verification
        "Heat Pipes $C_1^{strip}$": [5, 11, 13, 14, 14],
    }
    gemini_pass2 = {
        # Strip on Natural Vibration n=5 from this revision
        "NV strip $C_1$": [15, 11, 9, 8, 8],
    }
    judge_var = {
        # Same Claude SP-5100 C1 review, judged 4 times
        "SP-5100 Claude $C_1$": [47, 85, 85, 97],
        # Same Gemini SP-5100 C1 review, judged 3 times
        "SP-5100 Gemini $C_1$": [25, 45, 59],
        # Same Claude HP C1 review, judged 3 times
        "HP Claude $C_1$": [20, 20, 21],
    }

    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.3))

    def draw_panel(ax, data, color, title, ylabel="hallucinations", show_legend=True):
        labels = list(data.keys())
        x = np.arange(len(labels))
        for xi, name in zip(x, labels):
            vals = data[name]
            jitter = (np.arange(len(vals)) - (len(vals)-1)/2) * 0.05
            ax.scatter(np.full_like(vals, xi, dtype=float) + jitter, vals,
                       color=color, edgecolor="black", linewidth=0.4, s=42, zorder=3)
            ax.scatter([xi], [np.mean(vals)], color="black", marker="_", s=300, zorder=4)
            # Range bar
            ax.plot([xi, xi], [min(vals), max(vals)], color="#666666", linewidth=0.6, zorder=2)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7.5, rotation=20, ha="right")
        ax.set_ylabel(ylabel, fontsize=8)
        ax.set_title(title, fontsize=8.5)
        ax.grid(alpha=0.25, linewidth=0.4, axis="y")

    draw_panel(axes[0], claude_pass2, C_CLAUDE, "Claude Pass-2 (different reviews,\nsame prompt, n=5 seeds)")
    draw_panel(axes[1], gemini_pass2, C_GEMINI, "Gemini Pass-2 (different seeds,\nT=0.7, n=5)")
    draw_panel(axes[2], judge_var, C_GPT,
               "GPT-5.4 judge variance\n(same review re-judged)")

    fig.tight_layout()
    fig.savefig(HERE / "fig7_stochasticity.pdf")
    plt.close(fig)
    print("[fig7] saved")


# ============================================================
# Figure 8: Probe-circularity check (Claude-extracted probes on 3 cells).
# ============================================================
def fig8_probe_circularity():
    summary_path = HERE.parent.parent / "research_log" / "probe_circularity_summary.json"
    expanded_path = HERE.parent.parent / "research_log" / "probe_circularity_expanded.json"
    runs = json.loads(summary_path.read_text())["runs"]
    if expanded_path.exists():
        runs = runs + json.loads(expanded_path.read_text())["runs"]
    # Pick the human-readable names + ordering (audio first, then paper by length)
    rename = {
        "audio-review-karpathy_sogpt-1777458038":      "Karpathy\n(big win)",
        "audio-review-mit_6034_winston-1778857365":    "MIT 6.034\n(big win)",
        "paper-review-19700025120-1777462513":         "Heat Pipes\n(small +)",
        "paper-review-19690013408-1777471789":         "Nat. Vib.\n(Mode-B)",
        "paper-review-2605.09852-1778859219":          "Fair. AI\n(Mode-A)",
        "paper-review-2605.11379-1778859223":          "Megagauss\n(wash)",
        "paper-review-2605.13991-1778859221":          "Perovskite\n(near-noise)",
    }
    order = list(rename.keys())
    by_key = {r["run_dir"].split("/")[-1]: r for r in runs if r["run_dir"].split("/")[-1] in rename}
    cells = []
    for k in order:
        if k not in by_key:
            continue
        r = by_key[k]
        cells.append({
            "name": rename[k],
            "orig": r["original_gpt_delta_cov"],
            "claude_gpt": r["claudeprobes_gpt_delta_cov"],
            "claude_claude": r["claudeprobes_claude_delta_cov"],
        })

    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    x = np.arange(len(cells))
    width = 0.28
    orig = [c["orig"] for c in cells]
    cg   = [c["claude_gpt"] for c in cells]
    cc   = [c["claude_claude"] for c in cells]

    b1 = ax.bar(x - width, orig, width, color=C_GEMINI, label="orig (Gemini probes, GPT judge)")
    b2 = ax.bar(x,         cg,   width, color=C_GPT,    label="Claude probes, GPT judge")
    b3 = ax.bar(x + width, cc,   width, color=C_CLAUDE, label="Claude probes, Claude judge")

    # Labels above bars
    for bars in (b1, b2, b3):
        for rect in bars:
            v = rect.get_height()
            y = v + (0.012 if v >= 0 else -0.012)
            ax.text(rect.get_x() + rect.get_width()/2, y, f"{v:+.2f}",
                    ha="center", va="bottom" if v >= 0 else "top", fontsize=7)

    ax.axhline(0, color="#888888", linewidth=0.5, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels([c["name"] for c in cells], fontsize=7.5)
    ax.set_ylabel(r"$\Delta_{\rm cov} = C_1 - C_0$")
    ax.set_title(f"Probe-circularity check across {len(cells)} cells $\\times$ 2 judges (revised)")
    ax.set_ylim(min(orig + cg + cc) - 0.08, max(orig + cg + cc) + 0.14)
    ax.legend(loc="upper right", frameon=False, fontsize=7.5)
    ax.grid(alpha=0.25, linewidth=0.4, axis="y")

    fig.tight_layout()
    fig.savefig(HERE / "fig8_probe_circularity.pdf")
    plt.close(fig)
    print("[fig8] saved")


# ============================================================
# Figure 9: Reference-bias check (Whisper on 3B1B + EasyOCR on Wagging Tail).
# ============================================================
def fig9_reference_bias():
    repo = HERE.parent.parent
    # All available reference_bias_summary.json files (now 4 cells: 2 audio, 2 paper)
    paths = [
        ("3B1B (Whisper)",    repo / "runs/audio-review-3b1b_attention-1778857367/reference_bias_summary.json"),
        ("Karpathy (Whisper)",repo / "runs/audio-review-karpathy_sogpt-1777458038/reference_bias_summary.json"),
        ("Wagging Tail\n(EasyOCR)", repo / "runs/paper-review-19720009221-1777458461/reference_bias_summary.json"),
        ("Thermal Anl.\n(EasyOCR)", repo / "runs/paper-review-19700023812-1777471791/reference_bias_summary.json"),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(11.0, 2.8))
    for ax, (label, p) in zip(axes, paths):
        d = json.loads(p.read_text())
        cats = ["orig", "alt-ref\nGPT judge", "alt-ref\nClaude judge"]
        d_halluc = [d["original"]["delta_halluc"], d["altref_gpt5"]["delta_halluc"], d["altref_claude"]["delta_halluc"]]
        d_cov = [d["original"]["delta_cov"], d["altref_gpt5"]["delta_cov"], d["altref_claude"]["delta_cov"]]

        x = np.arange(len(cats))
        width = 0.36
        bars_h = ax.bar(x - width/2, d_halluc, width, color=C_GEMINI, label=r"$\Delta_{\rm halluc}$")
        ax2 = ax.twinx()
        bars_c = ax2.bar(x + width/2, d_cov, width, color=C_CLAUDE, alpha=0.85, label=r"$\Delta_{\rm cov}$")

        # Numeric labels
        for rect in bars_h:
            v = rect.get_height()
            ax.text(rect.get_x() + rect.get_width()/2,
                    v + (0.4 if v >= 0 else -0.4),
                    f"{int(v):+d}", ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=7, color=C_GEMINI)
        for rect in bars_c:
            v = rect.get_height()
            ax2.text(rect.get_x() + rect.get_width()/2,
                     v + (0.008 if v >= 0 else -0.008),
                     f"{v:+.2f}", ha="center",
                     va="bottom" if v >= 0 else "top", fontsize=7, color=C_CLAUDE)

        ax.axhline(0, color="#888888", linewidth=0.5, linestyle="--")
        ax.set_xticks(x)
        ax.set_xticklabels(cats, fontsize=7.5)
        ax.set_ylabel(r"$\Delta_{\rm halluc}$  ($\downarrow$=cascade wins)", fontsize=8, color=C_GEMINI)
        ax2.set_ylabel(r"$\Delta_{\rm cov}$  ($\uparrow$=cascade wins)", fontsize=8, color=C_CLAUDE)
        ax.set_title(label, fontsize=9)
        ax.spines["top"].set_visible(False); ax2.spines["top"].set_visible(False)
        ax.tick_params(axis="y", labelcolor=C_GEMINI)
        ax2.tick_params(axis="y", labelcolor=C_CLAUDE)
        ax.set_ylim(min(d_halluc) - 3, max(d_halluc) + 3)
        ax2.set_ylim(min(d_cov) - 0.04, max(d_cov) + 0.04)

    fig.subplots_adjust(wspace=0.55)
    fig.tight_layout()
    fig.savefig(HERE / "fig9_reference_bias.pdf")
    plt.close(fig)
    print("[fig9] saved")


# ============================================================
# Figure 10: Inter-judge scatter (GPT-5.4 vs Claude judge on hallucinations
# and on probe coverage, both axes simultaneously).
# ============================================================
def fig10_inter_judge_scatter():
    # Pull from inter_judge_summary_new12.json + the original inter_judge_summary.json
    repo = HERE.parent.parent
    summaries = []
    for p in [repo / "research_log/inter_judge_summary.json",
              repo / "research_log/inter_judge_summary_new12.json"]:
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        for run in d.get("runs", []):
            for label, conds in run.get("conditions", {}).items():
                g_h = conds.get("gpt5_unsupported")
                c_h = conds.get("claude_unsupported")
                g_c = conds.get("gpt5_covered")
                c_c = conds.get("claude_covered")
                if g_h is None or c_h is None:
                    continue
                summaries.append({
                    "label": label,
                    "gpt_h": g_h, "claude_h": c_h,
                    "gpt_c": g_c, "claude_c": c_c,
                })

    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.6))

    # ---- Halluc panel ----
    ax = axes[0]
    gpt_h  = np.array([s["gpt_h"]    for s in summaries])
    cla_h  = np.array([s["claude_h"] for s in summaries])
    mx = max(gpt_h.max(), cla_h.max()) + 5
    ax.plot([0, mx], [0, mx], color="#888888", linewidth=0.5, linestyle="--",
            label="judges agree")
    # Also draw a 0.71x line (Claude/GPT median ratio reported in paper)
    ax.plot([0, mx], [0, mx * 0.71], color="#888888", linewidth=0.5, linestyle=":",
            label=r"Claude $\approx 0.71\times$ GPT")
    ax.scatter(gpt_h, cla_h, s=20, color=C_GEMINI, edgecolor="black", linewidth=0.3, zorder=3)
    ax.set_xlim(0, mx); ax.set_ylim(0, mx)
    ax.set_xlabel("GPT-5.4 unsupported claims", fontsize=8)
    ax.set_ylabel("Claude unsupported claims", fontsize=8)
    ax.set_title(f"Hallucination counts (n={len(summaries)} cells × conditions)", fontsize=9)
    ax.legend(loc="lower right", frameon=False, fontsize=7)
    ax.grid(alpha=0.25, linewidth=0.4)

    # ---- Coverage panel ----
    ax = axes[1]
    gpt_c = np.array([s["gpt_c"]    for s in summaries if s["gpt_c"] is not None])
    cla_c = np.array([s["claude_c"] for s in summaries if s["claude_c"] is not None])
    mx = max(gpt_c.max(), cla_c.max()) + 3
    ax.plot([0, mx], [0, mx], color="#888888", linewidth=0.5, linestyle="--",
            label="judges agree")
    ax.scatter(gpt_c, cla_c, s=20, color=C_CLAUDE, edgecolor="black", linewidth=0.3, zorder=3)
    ax.set_xlim(0, mx); ax.set_ylim(0, mx)
    ax.set_xlabel("GPT-5.4 probes covered", fontsize=8)
    ax.set_ylabel("Claude probes covered", fontsize=8)
    ax.set_title("Coverage counts (judges much more aligned)", fontsize=9)
    ax.legend(loc="lower right", frameon=False, fontsize=7)
    ax.grid(alpha=0.25, linewidth=0.4)

    fig.tight_layout()
    fig.savefig(HERE / "fig10_inter_judge_scatter.pdf")
    plt.close(fig)
    print("[fig10] saved")


if __name__ == "__main__":
    fig0_protocol_schematic()
    fig1_inverse_correlation()
    fig2_cross_vendor_thermal()
    fig3_heatpipes_pareto()
    fig4_failure_modes()
    fig5_cost_pareto()
    fig6_multiseed_envelopes()
    fig7_stochasticity_decomp()
    fig8_probe_circularity()
    fig9_reference_bias()
    fig10_inter_judge_scatter()
    print("All figures generated.")
