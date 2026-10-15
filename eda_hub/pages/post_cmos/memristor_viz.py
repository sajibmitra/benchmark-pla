"""SVG plots for memristor ngspice characterization."""
from __future__ import annotations

import math
from typing import Sequence


def _xml_text(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _nice_bounds(vals: Sequence[float], *, pad_frac: float = 0.08) -> tuple[float, float]:
    if not vals:
        return 0.0, 1.0
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        span = abs(lo) * 0.1 + 1e-15
        return lo - span, hi + span
    span = hi - lo
    return lo - span * pad_frac, hi + span * pad_frac


def xy_plot_svg(
    x_vals: Sequence[float],
    y_vals: Sequence[float],
    *,
    title: str,
    x_label: str,
    y_label: str,
    stroke: str = "#06c",
) -> str:
    n = min(len(x_vals), len(y_vals))
    if n < 2:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 80">'
            f'<text x="8" y="40" font-size="13">{_xml_text(title)} — insufficient samples</text></svg>'
        )
    xs = list(x_vals[:n])
    ys = list(y_vals[:n])
    x0, x1 = _nice_bounds(xs)
    y0, y1 = _nice_bounds(ys)
    margin_l, margin_r, margin_t, margin_b = 58, 22, 28, 46
    chart_w, chart_h = 520, 260
    vw = chart_w + margin_l + margin_r
    vh = chart_h + margin_t + margin_b

    def sx(x: float) -> float:
        return margin_l + (x - x0) / (x1 - x0) * chart_w

    def sy(y: float) -> float:
        return margin_t + chart_h * (1 - (y - y0) / (y1 - y0))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" font-family="system-ui,sans-serif">',
        f'<rect width="{vw}" height="{vh}" fill="#fafbfd"/>',
        f'<text x="{margin_l}" y="18" font-size="13" fill="#222">{_xml_text(title)}</text>',
        f'<line x1="{margin_l}" y1="{margin_t + chart_h}" x2="{margin_l + chart_w}" y2="{margin_t + chart_h}" stroke="#888"/>',
        f'<line x1="{margin_l}" y1="{margin_t}" x2="{margin_l}" y2="{margin_t + chart_h}" stroke="#888"/>',
    ]
    d_parts = [f"M {sx(xs[0]):.2f} {sy(ys[0]):.2f}"]
    for i in range(1, n):
        d_parts.append(f"L {sx(xs[i]):.2f} {sy(ys[i]):.2f}")
    parts.append(f'<path d="{" ".join(d_parts)}" fill="none" stroke="{stroke}" stroke-width="1.8"/>')
    parts.append(
        f'<text x="{margin_l + chart_w // 2}" y="{vh - 8}" text-anchor="middle" font-size="11" fill="#555">{_xml_text(x_label)}</text>'
    )
    parts.append(
        f'<text x="14" y="{margin_t + chart_h // 2}" text-anchor="middle" font-size="11" fill="#555" '
        f'transform="rotate(-90 14 {margin_t + chart_h // 2})">{_xml_text(y_label)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def time_series_svg(
    t_vals: Sequence[float],
    series: dict[str, Sequence[float]],
    *,
    title: str,
    y_label: str = "",
) -> str:
    if not t_vals or not series:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 80">'
            f'<text x="8" y="40" font-size="13">{_xml_text(title)} — no data</text></svg>'
        )
    n = len(t_vals)
    t0, t1 = t_vals[0], t_vals[-1]
    if t1 <= t0:
        t1 = t0 + 1e-15

    all_y: list[float] = []
    for ys in series.values():
        all_y.extend(float(y) for y in ys[:n] if math.isfinite(y))
    y0, y1 = _nice_bounds(all_y) if all_y else (0.0, 1.0)

    margin_l, margin_r, margin_t, margin_b = 58, 22, 28, 46
    chart_w, chart_h = 520, 200
    vw = chart_w + margin_l + margin_r
    vh = chart_h + margin_t + margin_b
    colors = ("#06c", "#0a6", "#c60", "#909", "#a40", "#666")

    def sx(ti: float) -> float:
        return margin_l + (ti - t0) / (t1 - t0) * chart_w

    def sy(v: float) -> float:
        if not math.isfinite(v):
            v = y0
        return margin_t + chart_h * (1 - (v - y0) / (y1 - y0))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" font-family="system-ui,sans-serif">',
        f'<rect width="{vw}" height="{vh}" fill="#fafbfd"/>',
        f'<text x="{margin_l}" y="18" font-size="13" fill="#222">{_xml_text(title)}</text>',
        f'<line x1="{margin_l}" y1="{margin_t + chart_h}" x2="{margin_l + chart_w}" y2="{margin_t + chart_h}" stroke="#888"/>',
        f'<line x1="{margin_l}" y1="{margin_t}" x2="{margin_l}" y2="{margin_t + chart_h}" stroke="#888"/>',
    ]
    for j, (name, ys) in enumerate(series.items()):
        if len(ys) < n:
            continue
        color = colors[j % len(colors)]
        d_parts = [f"M {sx(t_vals[0]):.2f} {sy(float(ys[0])):.2f}"]
        for i in range(1, n):
            d_parts.append(f"L {sx(t_vals[i]):.2f} {sy(float(ys[i])):.2f}")
        parts.append(f'<path d="{" ".join(d_parts)}" fill="none" stroke="{color}" stroke-width="1.6"/>')
        parts.append(
            f'<text x="{margin_l + 4}" y="{margin_t + 14 + j * 14}" font-size="11" fill="{color}">{_xml_text(name)}</text>'
        )
    parts.append(
        f'<text x="{margin_l + chart_w // 2}" y="{vh - 8}" text-anchor="middle" font-size="11" fill="#555">time (s)</text>'
    )
    if y_label:
        parts.append(
            f'<text x="14" y="{margin_t + chart_h // 2}" text-anchor="middle" font-size="11" fill="#555" '
            f'transform="rotate(-90 14 {margin_t + chart_h // 2})">{_xml_text(y_label)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


__all__ = ["time_series_svg", "xy_plot_svg"]
