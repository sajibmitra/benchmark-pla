#!/usr/bin/env python3
"""
Figure 15 (fig:final_critical_path): four realization classes vs MCNC benchmarks
for RPLA-level metrics — line traces (markers) matching Fig.~\\ref{fig:power_critical_path} style.

  (1) Non-reversible PLA — no RPLA QC/GB; GA uses classical two-level heuristic G_NR
  (2) Reversible PLA (PTL) — GA^dag, GB^dag, QC^dag from Table experimental_results
  (3) Reversible post-CMOS — illustrative scalings on QC/GB (memristor/CNTFET outlook)
  (4) Reversible quantum PLA — QC emphasis + logical GA/GB (Sec. 4)

Outputs: fig_metric_rpla_fourway.pdf, .png

Run: python3 figure_metric_rpla_level.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent

# (GA^dag, GA^S, GB^dag, AI^dag, QC^dag) from tab:experimental_results — same bench order as Fig. 14
BENCH: dict[str, tuple[int, int, int, int, int]] = {
    "5xp1": (150, 343, 82, 86, 494),
    "xor5": (35, 95, 24, 20, 115),
    "rd53": (79, 186, 49, 47, 267),
    "misex1": (45, 103, 20, 19, 113),
    "alu3": (180, 343, 120, 120, 660),
    "bw": (129, 341, 17, 41, 253),
    "sao2": (292, 555, 228, 222, 1180),
    "cordic": (4782, 19390, 3626, 3604, 19198),
    "pdc": (893, 4510, 459, 483, 2809),
    "apex3": (1772, 4704, 1181, 1177, 6444),
}

# Illustrative scalings (Sec. 3–4 planning, not sign-off)
SCALE_POST_QC = 0.97
SCALE_Q_QC = 1.03
SCALE_POST_GB = 0.94
SCALE_Q_GB = 1.02


def g_classical(ga_dag: int, ga_s: int) -> int:
    return max(8, int(0.38 * ga_s + 0.22 * ga_dag))


def main() -> None:
    names = list(BENCH.keys())
    # Series: NR, PLA, Post, Q
    qc_nr, qc_pla, qc_post, qc_q = [], [], [], []
    gb_nr, gb_pla, gb_post, gb_q = [], [], [], []

    for n in names:
        gd, gs, gb, _ai, qc = BENCH[n]
        gn = g_classical(gd, gs)
        qc_nr.append(0.0)
        qc_pla.append(float(qc))
        qc_post.append(float(qc) * SCALE_POST_QC)
        qc_q.append(float(qc) * SCALE_Q_QC)

        gb_nr.append(0.0)
        gb_pla.append(float(gb))
        gb_post.append(float(gb) * SCALE_POST_GB)
        gb_q.append(float(gb) * SCALE_Q_GB)

    x = np.arange(len(names))
    labels = (
        "Non-reversible PLA",
        "Reversible PLA (PTL)",
        "Reversible post-CMOS",
        "Reversible quantum PLA",
    )
    colors = ("#3d3d3d", "#2e6ba8", "#1f8a6a", "#6b3fa0")
    markers = ("o", "s", "^", "D")
    plot_kw = dict(lw=1.45, ms=4.5, alpha=0.95)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.8, 6.0), sharex=True)
    fig.suptitle(
        "RPLA resource metrics: quantum cost vs. garbage (line traces)",
        fontsize=9,
        y=1.01,
    )

    series_qc = (qc_nr, qc_pla, qc_post, qc_q)
    for lab, c, m, y in zip(labels, colors, markers, series_qc):
        ax1.plot(x, y, marker=m, label=lab, color=c, **plot_kw)

    ax1.set_ylabel("Quantum cost QC\n(NR = 0; proposed QC† for reversible)")
    ax1.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.92)
    ax1.grid(axis="y", alpha=0.3)
    ax1.set_title("Quantum cost (RPLA level)")

    series_gb = (gb_nr, gb_pla, gb_post, gb_q)
    for lab, c, m, y in zip(labels, colors, markers, series_gb):
        ax2.plot(x, y, marker=m, label=lab, color=c, **plot_kw)

    ax2.set_ylabel("Garbage outputs GB\n(NR = 0; proposed GB† for reversible)")
    ax2.set_xlabel("MCNC benchmark")
    ax2.set_xticks(x)
    ax2.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
    ax2.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.92)
    ax2.grid(axis="y", alpha=0.3)
    ax2.set_title("Garbage count (RPLA level)")

    fig.tight_layout()
    fig.subplots_adjust(top=0.93)
    fig.savefig(OUT / "fig_metric_rpla_fourway.pdf", bbox_inches="tight", pad_inches=0.08)
    fig.savefig(OUT / "fig_metric_rpla_fourway.png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("Wrote fig_metric_rpla_fourway.pdf")


if __name__ == "__main__":
    main()
