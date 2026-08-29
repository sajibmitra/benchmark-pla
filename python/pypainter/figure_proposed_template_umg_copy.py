#!/usr/bin/env python3
"""
Recreate Fig. proposed_templace_UMG using a separate filename.

Outputs (under pypainter/images/):
  proposed_template_umg_alt.pdf
  proposed_template_umg_alt.png

Run:
  python3 figure_proposed_template_umg_copy.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch

SCRIPT_DIR = Path(__file__).resolve().parent
OUT = SCRIPT_DIR / "images"
OUT.mkdir(parents=True, exist_ok=True)


def _gate(ax, x: float, y: float, w: float, h: float, title: str, expr: str, color: str) -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=color,
        edgecolor="#263238",
        lw=1.2,
    )
    ax.add_patch(box)

    y1 = y + h * 0.76
    y2 = y + h * 0.50
    y3 = y + h * 0.24

    for yy in (y1, y2, y3):
        ax.plot([x - 0.35, x], [yy, yy], color="#37474F", lw=1.2)
        ax.plot([x + w, x + w + 0.35], [yy, yy], color="#37474F", lw=1.2)

    ax.text(x - 0.43, y1, r"$a$", ha="right", va="center", fontsize=8)
    ax.text(x - 0.43, y2, r"$b$", ha="right", va="center", fontsize=8)
    ax.text(x - 0.43, y3, r"$c$", ha="right", va="center", fontsize=8)

    ax.text(x + w + 0.40, y1, r"$p$", ha="left", va="center", fontsize=8)
    ax.text(x + w + 0.40, y2, r"$q$", ha="left", va="center", fontsize=8)
    ax.text(x + w + 0.40, y3, r"$r$", ha="left", va="center", fontsize=8)

    # Small symbolic mark to indicate reversible-template behavior
    ax.add_patch(Circle((x + w * 0.26, y2), 0.04, fill=False, ec="#5D4037", lw=1.1))
    ax.plot([x + w * 0.32, x + w * 0.68], [y2, y2], color="#5D4037", lw=1.1)
    ax.plot([x + w * 0.50, x + w * 0.50], [y2, y3 + 0.02], color="#5D4037", lw=1.1)

    ax.text(x + w * 0.50, y + h + 0.14, title, ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.text(x + w * 0.50, y - 0.16, expr, ha="center", va="top", fontsize=8, color="#1B5E20")


def draw() -> None:
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.6))
    fig.patch.set_facecolor("#FAFAFA")

    labels = [r"$\alpha$", r"$\beta$", r"$\gamma$", r"$\alpha'$", r"$\beta'$", r"$\gamma'$"]
    exprs = [
        r"$r=ab$",
        r"$r=a\bar b$",
        r"$r=\bar a b$",
        r"$r=ab$ (swap)",
        r"$r=a\bar b$ (swap)",
        r"$r=\bar a b$ (swap)",
    ]
    colors = ["#E3F2FD", "#F3E5F5", "#E8F5E9", "#FFF3E0", "#FCE4EC", "#E0F2F1"]

    for ax, title, expr, color in zip(axes.ravel(), labels, exprs, colors):
        ax.set_xlim(0, 4)
        ax.set_ylim(0, 3)
        ax.axis("off")
        _gate(ax, x=1.1, y=0.9, w=1.8, h=1.2, title=title, expr=expr, color=color)

    fig.suptitle(
        r"Proposed templates of UMG: $\alpha$, $\beta$, $\gamma$ and swapping variants $\alpha'$, $\beta'$, $\gamma'$",
        fontsize=11,
        fontweight="bold",
        y=0.98,
    )

    fig.tight_layout(rect=[0.01, 0.02, 0.99, 0.95])
    fig.savefig(OUT / "proposed_template_umg_alt.pdf", bbox_inches="tight", pad_inches=0.05)
    fig.savefig(OUT / "proposed_template_umg_alt.png", dpi=300, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


if __name__ == "__main__":
    draw()
    print("Wrote", OUT / "proposed_template_umg_alt.pdf")
    print("Wrote", OUT / "proposed_template_umg_alt.png")
