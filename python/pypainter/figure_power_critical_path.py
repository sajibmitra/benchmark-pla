#!/usr/bin/env python3
"""
Section 5: four-way benchmark comparison for Fig.~\\ref{fig:power_critical_path}:
  (1) Non-reversible AND--OR PLA (heuristic)
  (2) Reversible PLA — CMOS PTL UMG/UNG (Table matric_proposed_gates corner)
  (3) Reversible post-CMOS — same GA^dag, illustrative lower per-macro energy (memristor/CNTFET)
  (4) Reversible quantum PLA — QC^dag-proportional power proxy + QC-based depth heuristic

Outputs: fig_power_critical_path.pdf, fig_power_critical_path.png,
         power_critical_path_table_rows.tex

Run: python3 figure_power_critical_path.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent

# (GA^dag, GA^S, QC^dag, AI^dag) from tab:experimental_results — AI† proxies input/ancilla rails
BENCH: dict[str, tuple[int, int, int, int]] = {
    "5xp1": (150, 343, 494, 86),
    "xor5": (35, 95, 115, 20),
    "rd53": (79, 186, 267, 47),
    "misex1": (45, 103, 113, 19),
    "alu3": (180, 343, 660, 120),
    "bw": (129, 341, 253, 41),
    "sao2": (292, 555, 1180, 222),
    "cordic": (4782, 19390, 19198, 3604),
    "pdc": (893, 4510, 2809, 483),
    "apex3": (1772, 1772, 6444, 1177),
}

P_REV_PER_GATE = 1.45e-4  # W per UMG/UNG macro, Nangate PTL extraction
P_NR_PER_NODE = 0.82e-4
# NR PLA does not bijectively preserve input literals; re-latching / buffer restoration each cycle
# (first-order, same corner as P_NR_PER_NODE; AI† counts lines analogous to preserved inputs in RPLA).
P_NR_RESTORE_PER_AI = 0.58e-4
# Illustrative: memristor/CNTFET reversible macro energy vs same-count PTL (Sec. 3 outlook)
ETA_POST_CMOS_POWER = 0.86
GAMMA_POST_CMOS_CP = 0.92
# Quantum: QC scales vs GA for switching activity proxy (first-order; not device-calibrated mW)
KAPPA_QC_POWER = 0.32  # P_Q (mW) = QC * P_REV_PER_GATE * 1e3 * KAPPA_QC_POWER
A_QC_CP = 0.019
B_QC_CP = 0.36


def g_classical(ga_dag: int, ga_s: int) -> int:
    return max(8, int(0.38 * ga_s + 0.22 * ga_dag))


def critical_path_rev(ga_dag: int) -> float:
    g = max(1, ga_dag)
    return 0.019 * (g**0.44)


def critical_path_nr(gn: int) -> float:
    g = max(1, gn)
    return 0.017 * (g**0.44)


def critical_path_quantum(qc_dag: int) -> float:
    q = max(1, qc_dag)
    return A_QC_CP * (q**B_QC_CP)


def main() -> None:
    names = list(BENCH.keys())
    p_nr, p_pla, p_post, p_q = [], [], [], []
    cp_nr, cp_pla, cp_post, cp_q = [], [], [], []

    for n in names:
        gd, gs, qc, ai = BENCH[n]
        gn = g_classical(gd, gs)
        p_switch = gn * P_NR_PER_NODE * 1e3
        p_rec = ai * P_NR_RESTORE_PER_AI * 1e3
        p_n = p_switch + p_rec
        p_p = gd * P_REV_PER_GATE * 1e3
        p_nr.append(p_n)
        p_pla.append(p_p)
        p_post.append(p_p * ETA_POST_CMOS_POWER)
        p_q.append(qc * P_REV_PER_GATE * 1e3 * KAPPA_QC_POWER)

        cp_n = critical_path_nr(gn)
        c_p = critical_path_rev(gd)
        cp_nr.append(cp_n)
        cp_pla.append(c_p)
        cp_post.append(c_p * GAMMA_POST_CMOS_CP)
        cp_q.append(critical_path_quantum(qc))

    x = np.arange(len(names))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.8, 6.0), sharex=True)
    fig.suptitle(
        "PLA realization comparison across MCNC benchmarks (line traces)",
        fontsize=9,
        y=1.01,
    )

    labels = (
        "Non-reversible PLA",
        "Reversible PLA (PTL)",
        "Reversible post-CMOS",
        "Reversible quantum PLA",
    )
    colors = ("#3d3d3d", "#2e6ba8", "#1f8a6a", "#6b3fa0")
    markers = ("o", "s", "^", "D")
    plot_kw = dict(lw=1.45, ms=4.5, alpha=0.95)

    series_p = (p_nr, p_pla, p_post, p_q)
    for i, (lab, c, m) in enumerate(zip(labels, colors, markers)):
        ax1.plot(
            x,
            series_p[i],
            marker=m,
            label=lab,
            color=c,
            **plot_kw,
        )

    ax1.set_ylabel("Switching power (mW)\n(uniform activity; see Sec.~5 model)")
    ax1.set_yscale("log")
    ax1.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.92)
    ax1.grid(axis="y", alpha=0.3, which="both")
    ax1.set_title("Estimated switching power (NR includes input-restore term)")

    series_cp = (cp_nr, cp_pla, cp_post, cp_q)
    for i, (lab, c, m) in enumerate(zip(labels, colors, markers)):
        ax2.plot(x, series_cp[i], marker=m, label=lab, color=c, **plot_kw)

    ax2.set_ylabel("Critical path (ns)\n(heuristic depth)")
    ax2.set_xlabel("MCNC benchmark")
    ax2.set_xticks(x)
    ax2.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
    ax2.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.92)
    ax2.grid(axis="y", alpha=0.3)
    ax2.set_title("Estimated critical-path delay")

    fig.tight_layout()
    fig.subplots_adjust(top=0.93)
    fig.savefig(OUT / "fig_power_critical_path.pdf", bbox_inches="tight", pad_inches=0.08)
    fig.savefig(OUT / "fig_power_critical_path.png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)

    tex = []
    for n in names:
        gd, gs, qc, ai = BENCH[n]
        gn = g_classical(gd, gs)
        pn = gn * P_NR_PER_NODE * 1e3 + ai * P_NR_RESTORE_PER_AI * 1e3
        pp = gd * P_REV_PER_GATE * 1e3
        ppo = pp * ETA_POST_CMOS_POWER
        pq = qc * P_REV_PER_GATE * 1e3 * KAPPA_QC_POWER
        cn = critical_path_nr(gn)
        cp = critical_path_rev(gd)
        cpo = cp * GAMMA_POST_CMOS_CP
        cq = critical_path_quantum(qc)
        tex.append(
            f"{n} & {pn:.2f} & {pp:.2f} & {ppo:.2f} & {pq:.2f} & {cn:.2f} & {cp:.2f} & {cpo:.2f} & {cq:.2f} \\\\"
        )
    tex.append("\\bottomrule")
    (OUT / "power_critical_path_table_rows.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    print("Wrote fig_power_critical_path.pdf and power_critical_path_table_rows.tex")


if __name__ == "__main__":
    main()
