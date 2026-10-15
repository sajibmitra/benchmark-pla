#!/usr/bin/env python3
"""
Publication figures for Sec. 3: (a) regular memristor crossbar RPLA for F;
(b) memristor realization of UMG and UNG macros.

Colorful vector diagrams (AND / XOR regions, rail colors, LRS/HRS-tinted
crosspoints). Writes PDF + PNG next to other paper figures.

Outputs (under pypainter/images/):
  rpla_f_memristor_regular.pdf / .png
  rpla_f_memristor_umg_ung.pdf / .png

Run: python3 figure_memristor_rpla_f.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches
from matplotlib.patches import FancyBboxPatch

SCRIPT_DIR = Path(__file__).resolve().parent
OUT = SCRIPT_DIR / "images"
OUT.mkdir(parents=True, exist_ok=True)


def _memristor_symbol(
    ax,
    x: float,
    y: float,
    size: float = 0.12,
    *,
    face: str = "#f4d4a8",
    edge: str = "#5c4033",
    lw: float = 1.15,
) -> None:
    """Memristor glyph with filled body (bridge + bar) for a clearer, colorful look."""
    s = size
    ax.plot([x - s, x - s * 0.35], [y, y], color=edge, lw=lw, solid_capstyle="round")
    ax.plot([x + s * 0.35, x + s], [y, y], color=edge, lw=lw, solid_capstyle="round")
    rect = patches.Rectangle(
        (x - s * 0.35, y - s * 0.25),
        s * 0.7,
        s * 0.5,
        facecolor=face,
        edgecolor=edge,
        lw=lw,
        zorder=3,
    )
    ax.add_patch(rect)
    ax.plot([x, x], [y - s * 0.25, y - s * 0.45], color=edge, lw=lw, solid_capstyle="round")


def draw_regular_crossbar() -> None:
    fig, ax = plt.subplots(1, 1, figsize=(7.2, 4.0))
    fig.patch.set_alpha(0)
    # fig.patch.set_facecolor("#faf9f7")
    # ax.set_facecolor("#faf9f7")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_aspect("equal")

    # AND plane (memristor crossbar) — warm panel
    and_box = FancyBboxPatch(
        (0.45, 0.75),
        3.55,
        3.7,
        boxstyle="round,pad=0.03,rounding_size=0.18",
        facecolor="#ffe8dc",
        edgecolor="#c45c26",
        lw=1.6,
    )
    ax.add_patch(and_box)
    ax.text(
        2.4,
        4.78,
        "AND plane (memristor crossbar)",
        ha="center",
        fontsize=10.5,
        fontweight="bold",
        color="#7a2e0f",
    )

    rail_colors = ["#1f77b4", "#2ca02c", "#9467bd", "#7f7f7f"]
    xv = [1.0, 1.8, 2.6, 3.4]
    labels_v = [r"$a$", r"$b$", r"$c$", "anc."]
    for x, lab, rc in zip(xv, labels_v, rail_colors):
        ax.plot([x, x], [1.15, 3.85], color=rc, lw=2.0, alpha=0.9, solid_capstyle="round")
        ax.text(x, 0.92, lab, ha="center", fontsize=9.5, color=rc, fontweight="bold")

    # Horizontal rails — distinct hues per product row
    yh = [3.55, 3.05, 2.55, 2.05, 1.55]
    row_colors = plt.cm.viridis(np.linspace(0.15, 0.75, len(yh)))
    for i, (y, rc) in enumerate(zip(yh, row_colors)):
        ax.plot([0.88, 3.72], [y, y], color=rc, lw=1.35, alpha=0.92, solid_capstyle="round")
        ax.text(0.38, y, f"$P_{i+1}$", ha="right", va="center", fontsize=8.5, color=rc)

    # Crosspoints: alternate LRS (warm) / HRS (cool) tint
    for ri, x in enumerate(xv):
        for ci, y in enumerate(yh):
            warm = (ri + ci) % 2 == 0
            face = "#ffb347" if warm else "#87ceeb"
            edge = "#8b4513" if warm else "#1a5276"
            _memristor_symbol(ax, x, y, size=0.11, face=face, edge=edge)

    ax.text(
        2.4,
        0.32,
        r"LRS/HRS programmability $\rightarrow$ ESOP products for $F$",
        ha="center",
        fontsize=8.5,
        color="#5d4037",
    )

    # XOR plane — cool panel
    xor_box = FancyBboxPatch(
        (5.15, 0.75),
        4.55,
        3.7,
        boxstyle="round,pad=0.03,rounding_size=0.18",
        facecolor="#e3f2fd",
        edgecolor="#1565c0",
        lw=1.6,
    )
    ax.add_patch(xor_box)
    ax.text(
        7.25,
        4.78,
        "XOR plane (FG / pass paths)",
        ha="center",
        fontsize=10.5,
        fontweight="bold",
        color="#0d47a1",
    )

    px = [5.55, 6.35, 7.15, 7.95, 8.75]
    out_colors = plt.cm.plasma(np.linspace(0.2, 0.85, len(px)))
    for j, (x, fc) in enumerate(zip(px, out_colors)):
        ax.plot([x, x], [1.15, 3.85], color=fc, lw=2.0, alpha=0.88, solid_capstyle="round")
        ax.text(x, 0.92, f"$f_{j+1}$", ha="center", fontsize=9.5, color=fc, fontweight="bold")

    for yi, y in enumerate(yh):
        ax.plot([5.45, 9.15], [y, y], "-", lw=1.2, color="#283593", alpha=0.75)
        for xi, x in enumerate(px):
            warm = (xi + yi) % 2 == 0
            face = "#ffd54f" if warm else "#80cbc4"
            edge = "#5d4037" if warm else "#00695c"
            _memristor_symbol(ax, x, y, size=0.09, face=face, edge=edge)

    ax.annotate(
        "",
        xy=(4.05, 2.55),
        xytext=(4.92, 2.55),
        arrowprops=dict(arrowstyle="->", lw=1.8, color="#d84315"),
    )
    ax.text(4.52, 2.82, "products", ha="center", fontsize=8.5, color="#bf360c", fontweight="bold")

    fig.savefig(OUT / "rpla_f_memristor_regular.pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT / "rpla_f_memristor_regular.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def draw_umg_ung_memristor() -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.85))
    fig.patch.set_alpha(0)
    # fig.patch.set_facecolor("#faf9f7")
    for ax in (ax1, ax2):
        ax.set_facecolor("#faf9f7")
        ax.set_xlim(0, 5)
        ax.set_ylim(0, 4.35)
        ax.axis("off")
        ax.set_aspect("equal")

    def draw_cell(ax, title: str, subtitle: str, panel_face: str, panel_edge: str) -> None:
        box = FancyBboxPatch(
            (0.48, 0.48),
            4.14,
            3.58,
            boxstyle="round,pad=0.03,rounding_size=0.14",
            facecolor=panel_face,
            edgecolor=panel_edge,
            lw=1.55,
        )
        ax.add_patch(box)
        ax.text(2.5, 4.38, title, ha="center", fontsize=10.5, fontweight="bold", color=panel_edge)
        ax.text(2.5, 3.58, subtitle, ha="center", fontsize=7.8, style="italic", color="#424242")
        ax.add_patch(patches.Rectangle((0.6, 0.3), 0.25, 0.15, facecolor="#ffb347", edgecolor="#8b4513"))
        ax.text(0.9, 0.375, "LRS (ON)", fontsize=7, va="center")
    
        ax.add_patch(patches.Rectangle((0.6, 0.1), 0.25, 0.15, facecolor="#87ceeb", edgecolor="#1a5276"))
        ax.text(0.9, 0.175, "HRS (OFF)", fontsize=7, va="center")
        ys = [2.85, 2.08, 1.28]
        names_in = [r"$a$", r"$b$", r"$c$"]
        names_umg_out = [r"$p{=}a$", r"$q{=}b{\oplus}c$", r"$r$"]
        names_ung_out = [r"$p{=}a$", r"$q{=}b$", r"$r$"]
        in_colors = ["#1565c0", "#2e7d32", "#6a1b9a"]

        for y, lab, ic in zip(ys, names_in, in_colors):
            ax.plot([0.48, 1.12], [y, y], color=ic, lw=2.0, solid_capstyle="round")
            ax.text(0.32, y, lab, ha="right", va="center", fontsize=9.5, color=ic, fontweight="bold")

        xv_mesh = [1.55, 2.5, 3.45]
        mesh_colors = ["#8d6e63", "#5d4037", "#8d6e63"]
        for x, mc in zip(xv_mesh, mesh_colors):
            ax.plot([x, x], [1.02, 3.12], "-", lw=0.85, color=mc, alpha=0.9)

        for y in ys:
            ax.plot([1.12, 3.88], [y, y], color="#37474f", lw=1.05, alpha=0.85)

        for xi, x in enumerate(xv_mesh):
            for yi, y in enumerate(ys):
                warm = (xi + yi) % 2 == 0
                face = "#ffcc80" if warm else "#90caf9"
                edge = "#e65100" if warm else "#0d47a1"
                _memristor_symbol(ax, x, y, size=0.1, face=face, edge=edge)

        outs = names_umg_out if "UMG" in title else names_ung_out
        out_cols = ["#c62828", "#00695c", "#4a148c"] if "UMG" in title else ["#c62828", "#2e7d32", "#4a148c"]
        for y, lab, oc in zip(ys, outs, out_cols):
            ax.plot([3.88, 4.68], [y, y], color=oc, lw=2.0, solid_capstyle="round")
            ax.text(4.82, y, lab, ha="left", va="center", fontsize=8.2, color=oc)

    draw_cell(
        ax1,
        "Universal MUX Gate – reversible",
        r"$r = ab \oplus \overline{a}\,c$ — select/data via LRS/HRS",
        panel_face="#fff3e0",
        panel_edge="#ef6c00",
    )
    draw_cell(
        ax2,
        "Universal NOR Gate – reversible",
        r"$r = (a \vee b) \oplus c$ — XOR on third wire",
        panel_face="#e8f5e9",
        panel_edge="#2e7d32",
    )

    fig.suptitle(
        r"Memristor crosspoint realization of reversible macros (sample $F$ AND plane)",
        fontsize=10.5,
        y=0.93,
        color="#263238",
        fontweight="bold",
    )
    fig.savefig(OUT / "rpla_f_memristor_umg_ung.pdf", bbox_inches="tight", pad_inches=0.1)
    fig.savefig(OUT / "rpla_f_memristor_umg_ung.png", dpi=220, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)


def main() -> None:
    draw_regular_crossbar()
    draw_umg_ung_memristor()
    print("Wrote", OUT / "rpla_f_memristor_regular.pdf")
    print("Wrote", OUT / "rpla_f_memristor_umg_ung.pdf")


if __name__ == "__main__":
    main()
