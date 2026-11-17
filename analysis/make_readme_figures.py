#!/usr/bin/env python3
"""Create repository graphics from the recorded Phase 1 experiment; no simulation changes."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/assets"
INK, MUTED, TEAL, AMBER = "#142c38", "#536b78", "#007f82", "#b65b29"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = np.genfromtxt(ROOT/"results/phase1/baseline/history.csv", delimiter=",", names=True)
    report = json.loads((ROOT/"results/phase1/validation.json").read_text())
    t = data["time"].reshape(-1, 4)[:, 0]
    d = data["conductivity"].reshape(-1, 4)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": "#ced9de",
                         "xtick.color": MUTED, "ytick.color": MUTED,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "physarum-phase1"})

    # Hero is a code-native vector graphic. The decorative graph is explicitly schematic.
    (OUT/"banner.svg").write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="440" viewBox="0 0 1600 440" role="img" aria-labelledby="title desc">
<title id="title">Physarum Networks</title>
<desc id="desc">A C++20 research baseline for flow-dependent network adaptation. Four-node schematic with a reinforced short route and a faint longer route.</desc>
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#102d3b"/><stop offset="1" stop-color="#071a25"/></linearGradient></defs>
<rect width="1600" height="440" rx="20" fill="url(#bg)"/>
<g fill="none" stroke="#244958" stroke-width="1" opacity=".45">
<path d="M950 0V440M1050 0V440M1150 0V440M1250 0V440M1350 0V440M1450 0V440M900 90H1600M900 190H1600M900 290H1600M900 390H1600"/>
</g>
<g font-family="Arial,Helvetica,sans-serif">
<text x="76" y="78" fill="#8fd8cf" font-size="19" letter-spacing="4">BIOLOGICALLY INSPIRED NETWORK DESIGN</text>
<text x="70" y="177" fill="#f4f8f9" font-size="78" font-weight="700" letter-spacing="-2">Physarum Networks</text>
<text x="76" y="234" fill="#c1d3da" font-size="28">Flow. Reinforcement. Adaptation.</text>
<text x="76" y="292" fill="#91aebc" font-size="21">A reproducible C++20 research baseline.</text>
<rect x="76" y="337" width="340" height="42" rx="21" fill="#173e49"/>
<text x="101" y="365" fill="#9de0d4" font-size="18">PHASE 1 · VALIDATED FIXTURE</text>
<g stroke-linecap="round" fill="none">
<path d="M1040 220L1220 95L1460 220" stroke="#31505c" stroke-width="16"/>
<path d="M1040 220L1220 350L1460 220" stroke="#61717a" stroke-width="3" stroke-dasharray="7 9"/>
<path d="M1040 220L1220 95L1460 220" stroke="#76d1c2" stroke-width="10"/>
</g>
<g fill="#102d3b" stroke="#e3f1f3" stroke-width="3"><circle cx="1040" cy="220" r="20"/><circle cx="1220" cy="95" r="16"/><circle cx="1460" cy="220" r="20"/><circle cx="1220" cy="350" r="16"/></g>
<g fill="#e3f1f3" font-size="17" text-anchor="middle"><text x="1040" y="267">source</text><text x="1460" y="267">sink</text></g>
<text x="1250" y="410" text-anchor="middle" fill="#91aebc" font-size="16">Four-node schematic · geometry not to scale</text>
</g></svg>''', encoding="utf-8")

    fig, axes = plt.subplots(1, 4, figsize=(14, 4.4))
    fig.patch.set_facecolor("#f7fafb")
    fig.suptitle("The shorter route becomes dominant", x=.045, ha="left",
                 y=.97, fontsize=19, fontweight="bold", color=INK)
    xy = np.array([[0, 0], [1, .85], [1, -.85], [2, 0]])
    edges = [(0, 1), (1, 3), (0, 2), (2, 3)]
    for ax, target in zip(axes, [0, 2, 6, 30]):
        i = int(np.argmin(abs(t-target)))
        ax.set_aspect("equal")
        ax.set(xlim=(-.35, 2.35), ylim=(-1.65, 1.65))
        ax.axis("off")
        ax.text(.5, .99, f"t = {t[i]:g}", ha="center", va="top", transform=ax.transAxes,
                fontsize=16, fontweight="bold")
        for k, (u, v) in enumerate(edges):
            coords = xy[[u, v]]
            # A fixed pale outline makes all original edges visible; only the inner width encodes D.
            ax.plot(*coords.T, lw=1.5, color="#ccd8de", zorder=1, solid_capstyle="round")
            if d[i, k] > 1e-10:  # rendering resolution only; raw D is neither changed nor deleted
                ax.plot(*coords.T, lw=12*d[i, k], color=TEAL if k<2 else AMBER,
                        zorder=2, solid_capstyle="round")
        for j, (x, y) in enumerate(xy):
            ax.add_patch(Circle((x, y), .105, facecolor=INK, edgecolor="white", lw=1.5, zorder=3))
            ax.text(x, y, str(j), ha="center", va="center", color="white", fontsize=10, zorder=4)
        ax.text(1, 1.18, f"Short route  D = {d[i, 0]:.3f}", ha="center", fontsize=10, color=TEAL)
        long_label = f"{d[i, 2]:.2e}" if d[i, 2]<.001 else f"{d[i, 2]:.3f}"
        ax.text(1, -1.24, f"Long route  D = {long_label}", ha="center", fontsize=10, color=AMBER)
    fig.text(.045, .075, "Short route L = 2  ·  Long route L = 4  ·  Fixed source 0 → sink 3  ·  I₀ = 2  ·  γ = 1.8", fontsize=10, color=MUTED)
    fig.text(.045, .025, "Measured CSV states. Geometry is schematic. Width encodes D; pale outlines retain every edge. No model pruning.", fontsize=9, color=MUTED)
    fig.subplots_adjust(left=.025, right=.985, top=.82, bottom=.18, wspace=.05)
    fig.savefig(OUT/"network-evolution.png", dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    fig.suptitle("Phase 1 | measured behaviour and numerical validation", fontsize=16, fontweight="bold")
    ax = axes[0]
    ax.plot(t, d[:, 0], color=TEAL, lw=2.7, label="Short route · length 2")
    ax.plot(t, d[:, 2], color=AMBER, lw=2.7, label="Long route · length 4")
    ax.axhline(report["single_route_equilibrium_conductivity"], color="#94a6b0", lw=1.2, ls="--")
    ax.set(xlabel="Time (arbitrary model units)", ylabel="Edge conductivity D", ylim=(-.025, .84))
    ax.set_title("Flow-dependent reinforcement", loc="left", fontsize=13, pad=12)
    ax.legend(frameon=False, loc="center right", fontsize=10)
    ax.grid(alpha=.16)
    ax.text(.36, .08, "Paired edges overlap by symmetry.\nPositive conductivities are retained.",
            transform=ax.transAxes, fontsize=9, color=MUTED)
    ax = axes[1]
    study = report["timestep_study"]
    x = np.array([r["dt"] for r in study]); y = np.array([r["error_at_t4"] for r in study])
    ax.loglog(x, y, "o-", color="#315a82", lw=2.3, ms=6, label="Measured error at t = 4")
    ax.loglog(x, y[0]*x/x[0], "--", color="#94a6b0", label="First-order reference slope")
    ax.set(xlabel="Euler time step Δt", ylabel="Maximum absolute error in D")
    ax.set_xticks(x, labels=[f"{value:g}" for value in x])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_title("Time-step refinement", loc="left", fontsize=13, pad=12)
    ax.grid(which="both", alpha=.16)
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    ax.text(.04, .94, "Compared with Δt = 0.000625.\nThe reference has finite numerical error.",
            transform=ax.transAxes, va="top", fontsize=9, color=MUTED)
    fig.savefig(OUT/"validation.png", dpi=180, facecolor="white")
    plt.close(fig)
    # The figures report existing results; their provenance is explicit and portable.
    (OUT/"README.md").write_text(
        "# Repository figures\n\nRebuild with `.venv/bin/python analysis/make_readme_figures.py`.\n\n"
        "`banner.svg` is an illustrative, code-native schematic, not a biological image or an experimental result. "
        "`network-evolution.png` samples the recorded baseline history at t=0, 2, 6 and 30. "
        "`validation.png` plots that history and the measured time-step study.\n\n"
        "Inputs: `results/phase1/baseline/history.csv` and `results/phase1/validation.json`. "
        "Snapshot inner widths are proportional to conductivity, with no inner stroke rendered below D=1e-10; "
        "pale outlines show every edge regardless of conductivity. This is only a rendering convention. "
        "Raw conductivities and simulation dynamics are unchanged. Geometry is not to scale.\n")
    print(f"Wrote repository figures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
