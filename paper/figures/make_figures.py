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


if __name__ == "__main__":
    fig1_inverse_correlation()
    fig2_cross_vendor_thermal()
    fig3_heatpipes_pareto()
    fig4_failure_modes()
    print("All figures generated.")
