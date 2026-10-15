"""ngspice CNTFET inverter characterization with CMOS baseline comparison."""
from __future__ import annotations

import math
from typing import Any, Literal

from eda_hub.pages.post_cmos.cntfet_models import (
    CITATIONS,
    PARAM_METADATA,
    CntfetParams,
    build_cntfet_inverter_body,
    build_cntfet_transient_netlist,
    build_cntfet_vtc_netlist,
    build_cmos_baseline_body,
    build_cmos_transient_netlist,
    list_cntfet_presets_payload,
    resolve_cntfet_params,
)
from eda_hub.pages.post_cmos.cntfet_gate import build_cntfet_gate_transient_netlist, gate_display_name, normalize_cntfet_gate
from eda_hub.pages.post_cmos.memristor_viz import time_series_svg, xy_plot_svg
from eda_hub.pages.cmos_ptl_tgl.reversible_ngspice import gate_waveform_nodes, gate_timing_from_ngspice_measures, resolve_gate_propagation_delay, run_ngspice_netlist

CitationId = Literal["stanford", "bsim_cmg"]


def _wave_columns(wf: dict[str, Any] | None) -> dict[str, list[float]]:
    if not wf:
        return {}
    cols = wf.get("columns") or []
    rows = wf.get("rows") or []
    if not cols or not rows:
        return {}
    out: dict[str, list[float]] = {str(c): [] for c in cols}
    for row in rows:
        for i, c in enumerate(cols):
            if i < len(row):
                out[str(c)].append(float(row[i]))
    return out


def _comparison_bar_svg(
    labels: tuple[str, str],
    cntfet_vals: tuple[float | None, float | None],
    cmos_vals: tuple[float | None, float | None],
    *,
    title: str,
    units: tuple[str, str],
) -> str:
    """Grouped bar chart for delay (ns) and power (µW) comparison."""
    margin_l, margin_r, margin_t, margin_b = 58, 18, 28, 52
    chart_w, chart_h = 520, 200
    vw = chart_w + margin_l + margin_r
    vh = chart_h + margin_t + margin_b
    groups = ("Delay", "Power")
    all_vals = [v for v in (*cntfet_vals, *cmos_vals) if v is not None and math.isfinite(v)]
    ymax = max(all_vals) * 1.15 if all_vals else 1.0

    def sy(v: float) -> float:
        return margin_t + chart_h * (1 - min(v / ymax, 1.0))

    bar_w = 36
    gap = 80
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" font-family="system-ui,sans-serif">',
        f'<rect width="{vw}" height="{vh}" fill="#fafbfd"/>',
        f'<text x="{margin_l}" y="18" font-size="13" fill="#222">{title}</text>',
        f'<line x1="{margin_l}" y1="{margin_t + chart_h}" x2="{margin_l + chart_w}" y2="{margin_t + chart_h}" stroke="#888"/>',
    ]
    for gi, (cv, mv, unit) in enumerate(zip(cntfet_vals, cmos_vals, units, strict=True)):
        x0 = margin_l + 40 + gi * gap
        if cv is not None and math.isfinite(cv):
            y0 = sy(cv)
            parts.append(
                f'<rect x="{x0}" y="{y0}" width="{bar_w}" height="{margin_t + chart_h - y0}" fill="#06c"/>'
            )
            parts.append(
                f'<text x="{x0 + bar_w/2}" y="{y0 - 4}" text-anchor="middle" font-size="10" fill="#06c">{cv:.2g}</text>'
            )
        if mv is not None and math.isfinite(mv):
            x1 = x0 + bar_w + 8
            y1 = sy(mv)
            parts.append(
                f'<rect x="{x1}" y="{y1}" width="{bar_w}" height="{margin_t + chart_h - y1}" fill="#0a6"/>'
            )
            parts.append(
                f'<text x="{x1 + bar_w/2}" y="{y1 - 4}" text-anchor="middle" font-size="10" fill="#0a6">{mv:.2g}</text>'
            )
        parts.append(
            f'<text x="{x0 + bar_w}" y="{vh - 28}" text-anchor="middle" font-size="11" fill="#555">{groups[gi]} ({unit})</text>'
        )
    parts.append(f'<text x="{margin_l + 4}" y="{margin_t + 12}" font-size="11" fill="#06c">CNTFET</text>')
    parts.append(f'<text x="{margin_l + 64}" y="{margin_t + 12}" font-size="11" fill="#0a6">CMOS baseline</text>')
    parts.append("</svg>")
    return "".join(parts)


def analyze_cntfet_characterization(
    *,
    citation: CitationId = "stanford",
    gate: str = "NOT",
    param_overrides: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    """Run VTC + transient for CNTFET inverter, selected gate circuit, and CMOS baseline."""
    params = resolve_cntfet_params(param_overrides)
    vtc_net = build_cntfet_vtc_netlist(params)
    cntfet_tran = build_cntfet_transient_netlist(params)
    cmos_tran = build_cmos_transient_netlist(params)

    vtc_sim = run_ngspice_netlist(
        vtc_net,
        label="cntfet_vtc",
        waveform_exprs=("v(in)", "v(out)"),
        waveform_columns=("Vin", "Vout"),
    )
    cntfet_sim = run_ngspice_netlist(
        cntfet_tran,
        label="cntfet_transient",
        waveform_exprs=("v(in)", "v(out)"),
        waveform_columns=("Vin", "Vout"),
    )
    cmos_sim = run_ngspice_netlist(
        cmos_tran,
        label="cmos_baseline_transient",
        waveform_exprs=("v(in)", "v(out)"),
        waveform_columns=("Vin", "Vout"),
    )

    gate_netlist, _gate_probe = build_cntfet_gate_transient_netlist(gate, params)
    gate_gid = normalize_cntfet_gate(gate)
    gate_sim = run_ngspice_netlist(
        gate_netlist,
        label=f"cntfet_gate_{gate_display_name(gate)}",
        waveform_nodes=gate_waveform_nodes(gate_gid),
    )

    vtc_cols = _wave_columns(vtc_sim.get("waveform"))
    cf_cols = _wave_columns(cntfet_sim.get("waveform"))
    cm_cols = _wave_columns(cmos_sim.get("waveform"))

    vin_vtc = vtc_cols.get("Vin", [])
    vout_vtc = vtc_cols.get("Vout", [])
    t_cf = cf_cols.get("time_s", [])
    vout_cf = cf_cols.get("Vout", [])
    vin_cf = cf_cols.get("Vin", [])
    t_cm = cm_cols.get("time_s", [])
    vout_cm = cm_cols.get("Vout", [])
    vin_cm = cm_cols.get("Vin", [])

    cf_meas = cntfet_sim.get("measures") or {}
    cm_meas = cmos_sim.get("measures") or {}
    gate_meas = gate_sim.get("measures") or {}

    cf_tplh = cf_meas.get("t_plh")
    cf_tphl = cf_meas.get("t_phl")
    cf_pavg = cf_meas.get("pavg")
    cf_eswitch = cf_meas.get("e_switch")
    cm_tplh = cm_meas.get("t_plh")
    cm_tphl = cm_meas.get("t_phl")
    cm_pavg = cm_meas.get("pavg")
    gate_pavg = gate_meas.get("pavg") if gate_meas.get("pavg") is not None else gate_meas.get("p_avg")
    gate_pstat = gate_meas.get("pstat") if gate_meas.get("pstat") is not None else gate_meas.get("p_static")
    gate_delay = resolve_gate_propagation_delay(gate_sim, gate_gid, params.vdd)
    gate_timing = gate_timing_from_ngspice_measures(
        gate_meas, gate=gate_gid, gate_sim=gate_sim, vdd=params.vdd
    )

    cf_delay = None
    if cf_tplh is not None and cf_tphl is not None:
        cf_delay = (abs(cf_tplh) + abs(cf_tphl)) / 2
    elif cf_tplh is not None:
        cf_delay = abs(cf_tplh)
    elif cf_tphl is not None:
        cf_delay = abs(cf_tphl)
    cm_delay = None
    if cm_tplh is not None and cm_tphl is not None:
        cm_delay = (abs(cm_tplh) + abs(cm_tphl)) / 2
    elif cm_tplh is not None:
        cm_delay = abs(cm_tplh)
    elif cm_tphl is not None:
        cm_delay = abs(cm_tphl)

    cf_puw = abs(cf_pavg) * 1e6 if cf_pavg is not None else None
    cm_puw = abs(cm_pavg) * 1e6 if cm_pavg is not None else None
    gate_puw = abs(gate_pavg) * 1e6 if gate_pavg is not None else None
    gate_pstat_uw = abs(gate_pstat) * 1e6 if gate_pstat is not None else None
    gate_pdyn_uw = None
    if gate_puw is not None and gate_pstat_uw is not None:
        gate_pdyn_uw = max(gate_puw - gate_pstat_uw, 0.0)

    circuit_label = gate_display_name(gate)

    cite = CITATIONS.get(citation, CITATIONS["stanford"])
    spice_netlist = (
        f"* CNTFET inverter deck ({cite['label']})\n"
        + build_cntfet_inverter_body(params)
        + "\n* --- CMOS baseline ---\n"
        + build_cmos_baseline_body(params)
    )

    measurement_rows = [
        {"quantity": "Selected circuit", "value": circuit_label, "unit": "—"},
        {
            "quantity": f"Circuit avg power ({circuit_label})",
            "value": f"{gate_puw:.3f}" if gate_puw is not None else "—",
            "unit": "µW",
        },
        {
            "quantity": f"Circuit static power ({circuit_label})",
            "value": f"{gate_pstat_uw:.3f}" if gate_pstat_uw is not None else "—",
            "unit": "µW",
        },
        {
            "quantity": f"Circuit dynamic power ({circuit_label})",
            "value": f"{gate_pdyn_uw:.3f}" if gate_pdyn_uw is not None else "—",
            "unit": "µW",
        },
        {
            "quantity": f"Circuit propagation delay ({circuit_label})",
            "value": f"{gate_delay * 1e9:.3f}" if gate_delay is not None else "—",
            "unit": "ns",
        },
        {"quantity": "Model citation", "value": cite["label"], "unit": "—"},
        {"quantity": "Lch", "value": f"{params.lch_nm:.2g}", "unit": "nm"},
        {"quantity": "Dcnt", "value": f"{params.dcnt_nm:.2g}", "unit": "nm"},
        {"quantity": "Eg", "value": f"{params.eg_ev:.2g}", "unit": "eV"},
        {"quantity": "Vdd", "value": f"{params.vdd:.2g}", "unit": "V"},
        {"quantity": "ION (target)", "value": f"{params.ion_ua:.2g}", "unit": "µA"},
        {"quantity": "IOFF (target)", "value": f"{params.ioff_a:.4g}", "unit": "A"},
        {"quantity": "Cgate", "value": f"{params.cgate_ff:.2g}", "unit": "fF"},
        {
            "quantity": "Propagation delay tPLH (50%–50%, inverter)",
            "value": f"{cf_tplh * 1e9:.3f}" if cf_tplh is not None else "—",
            "unit": "ns",
        },
        {
            "quantity": "Propagation delay tPHL (50%–50%, inverter)",
            "value": f"{cf_tphl * 1e9:.3f}" if cf_tphl is not None else "—",
            "unit": "ns",
        },
        {
            "quantity": "CNTFET propagation delay (avg tPLH/tPHL)",
            "value": f"{cf_delay * 1e9:.2f}" if cf_delay is not None else "—",
            "unit": "ns",
        },
        {
            "quantity": "CMOS propagation delay (avg tPLH/tPHL)",
            "value": f"{cm_delay * 1e9:.2f}" if cm_delay is not None else "—",
            "unit": "ns",
        },
        {
            "quantity": "Switching energy (single transition)",
            "value": f"{abs(cf_eswitch) * 1e15:.2f}" if cf_eswitch is not None else "—",
            "unit": "fJ",
        },
        {
            "quantity": "CNTFET avg switching power",
            "value": f"{cf_puw:.3f}" if cf_puw is not None else "—",
            "unit": "µW",
        },
        {
            "quantity": "CMOS avg switching power",
            "value": f"{cm_puw:.3f}" if cm_puw is not None else "—",
            "unit": "µW",
        },
    ]
    if cf_delay and cm_delay and cm_delay > 0:
        measurement_rows.append(
            {
                "quantity": "Delay ratio CNTFET / CMOS",
                "value": f"{cf_delay / cm_delay:.3f}",
                "unit": "×",
            }
        )
    if cf_puw and cm_puw and cm_puw > 0:
        measurement_rows.append(
            {
                "quantity": "Power ratio CNTFET / CMOS",
                "value": f"{cf_puw / cm_puw:.3f}",
                "unit": "×",
            }
        )

    vtc_ok = bool(vtc_sim.get("waveform", {}).get("rows"))
    cf_ok = bool(cntfet_sim.get("waveform", {}).get("rows"))
    cm_ok = bool(cmos_sim.get("waveform", {}).get("rows"))
    ok = vtc_ok and cf_ok and cm_ok

    plots = {
        "vtc_svg": xy_plot_svg(
            vin_vtc,
            vout_vtc,
            title="VTC curve (CNTFET inverter)",
            x_label="Vin (V)",
            y_label="Vout (V)",
            stroke="#06c",
        ),
        "transient_cntfet_svg": time_series_svg(
            t_cf,
            {"Vin": vin_cf, "Vout (CNTFET)": vout_cf},
            title="Transient inverter response — CNTFET",
            y_label="V (V)",
        ),
        "transient_cmos_svg": time_series_svg(
            t_cm,
            {"Vin": vin_cm, "Vout (CMOS)": vout_cm},
            title="Transient inverter response — CMOS baseline",
            y_label="V (V)",
        ),
        "comparison_svg": _comparison_bar_svg(
            ("CNTFET", "CMOS"),
            (
                cf_delay * 1e9 if cf_delay is not None else None,
                cf_puw,
            ),
            (
                cm_delay * 1e9 if cm_delay is not None else None,
                cm_puw,
            ),
            title="Comparison vs CMOS baseline",
            units=("ns", "µW"),
        ),
    }

    outputs_checklist = [
        {"item": "SPICE netlist", "done": True},
        {"item": "CNTFET model citation (BSIM-CMG or Stanford)", "done": True},
        {"item": "VTC curve", "done": vtc_ok},
        {"item": "Transient inverter response", "done": cf_ok and cm_ok},
        {"item": "Delay + power measurements", "done": bool(gate_meas or cf_meas or cm_meas)},
        {"item": "Comparison vs CMOS (baseline)", "done": cm_ok},
    ]

    return {
        "ok": ok,
        "gate": gate,
        "circuit_label": circuit_label,
        "citation": citation,
        "citation_detail": cite,
        "params": params.as_dict(),
        "parameter_metadata": PARAM_METADATA,
        "spice_netlist": spice_netlist,
        "outputs_checklist": outputs_checklist,
        "measurements": measurement_rows,
        "gate_timing": gate_timing,
        "plots": plots,
        "netlists": {
            "vtc": vtc_net,
            "cntfet_transient": cntfet_tran,
            "cmos_transient": cmos_tran,
            "gate_transient": gate_netlist,
        },
        "ngspice_executable": cntfet_sim.get("ngspice_executable") or vtc_sim.get("ngspice_executable"),
        "error": None if ok else "One or more ngspice runs produced no waveform data",
    }


__all__ = ["analyze_cntfet_characterization", "list_cntfet_presets_payload"]
