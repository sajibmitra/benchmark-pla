"""Compact cost-metric tables for reversible gates across EDA hub technologies."""
from __future__ import annotations

from typing import Any, Literal

from eda_hub.pages.cmos_ptl_tgl.openroad_metrics import OpenroadMetricsError, run_openroad_reversible_gate_metrics
from eda_hub.pages.post_cmos.architecture_cost import (
    compute_cntfet_architecture_cost,
    compute_memristor_architecture_cost,
)
from eda_hub.pages.cmos_ptl_tgl.reversible_ngspice import analyze_reversible_gate, gate_timing_from_ngspice_measures

CostMetricTechnology = Literal[
    "vteam_memristor",
    "stanford_cntfet",
    "pass_transistor",
    "static_cmos",
    "transmission_gate_logic",
]

ALLOWED_COST_METRIC_TECHNOLOGIES = frozenset(
    {
        "vteam_memristor",
        "stanford_cntfet",
        "pass_transistor",
        "static_cmos",
        "transmission_gate_logic",
    }
)

# Same preset gates as the published comparison table (excluding NOT).
COST_METRIC_GATES: tuple[tuple[str, str, str], ...] = (
    ("FG", "feynman", "Feynman Gate"),
    ("TG", "toffoli", "Toffoli Gate"),
    ("FRG", "fredkin", "Fredkin Gate"),
    ("PG", "peres", "Peres Gate"),
    ("NMG", "nmg", "NMG Gate"),
    ("MUX", "mux", "MUX Gate"),
    ("UMG", "umg", "Universal MUX Gate"),
    ("UNG", "ung", "Universal NOR Gate"),
)

TECHNOLOGY_LABELS: dict[str, str] = {
    "vteam_memristor": "VTEAM memristor model",
    "stanford_cntfet": "Stanford CNFET model",
    "pass_transistor": "Pass transistor style",
    "static_cmos": "Static CMOS",
    "transmission_gate_logic": "Transmission gate logic (TGL)",
}


def _to_ps(seconds: float | None) -> float | None:
    if seconds is None:
        return None
    try:
        v = abs(float(seconds))
    except (TypeError, ValueError):
        return None
    if v <= 0 or v != v:
        return None
    return v * 1e12


def _power_in_1e4_w_from_uw(avg_uw: float | None) -> float | None:
    if avg_uw is None:
        return None
    # 1 µW = 10^-6 W → value in units of 10^-4 W = µW / 100
    return float(avg_uw) / 100.0


def _power_in_1e4_w_from_w(avg_w: float | None) -> float | None:
    if avg_w is None:
        return None
    return float(avg_w) * 1e4


def _rise_fall_ps_from_measures(measures: dict[str, Any]) -> tuple[float | None, float | None]:
    m = measures or {}
    rise_s = m.get("td_plh")
    if rise_s is None:
        rise_s = m.get("td_rise")
    if rise_s is None:
        rise_s = m.get("trise")
    if rise_s is None:
        rise_s = m.get("rise")
    fall_s = m.get("td_phl")
    if fall_s is None:
        fall_s = m.get("td_fall")
    if fall_s is None:
        fall_s = m.get("tfall")
    if fall_s is None:
        fall_s = m.get("fall")
    # Prefer non-inverting edges; fall back to inverting pair when primary pair is missing.
    if rise_s is None:
        rise_s = m.get("td_inv_r")
    if fall_s is None:
        fall_s = m.get("td_inv_f")
    return _to_ps(rise_s if rise_s is not None else None), _to_ps(fall_s if fall_s is not None else None)


def _round_metric(v: float | None, digits: int = 4) -> float | None:
    if v is None:
        return None
    return round(float(v), digits)


def _row(
    *,
    gate_key: str,
    gate_id: str,
    gate_label: str,
    area_um2: float | None = None,
    wirelength_um: float | None = None,
    avg_power_1e4_w: float | None = None,
    hpwl_um: float | None = None,
    t_plh_ps: float | None = None,
    t_phl_ps: float | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "gate_key": gate_key,
        "gate_id": gate_id,
        "gate_label": gate_label,
        "area_um2": _round_metric(area_um2, 4),
        "wirelength_um": _round_metric(wirelength_um, 4),
        "avg_power_1e4_w": _round_metric(avg_power_1e4_w, 5),
        "hpwl_um": _round_metric(hpwl_um, 4),
        "t_plh_ps": _round_metric(t_plh_ps, 4),
        "t_phl_ps": _round_metric(t_phl_ps, 4),
        "error": error,
    }


def _timing_ps_from_architecture(timing: dict[str, Any] | None) -> tuple[float | None, float | None]:
    t = timing or {}
    tplh = t.get("t_plh_ns")
    tphl = t.get("t_phl_ns")
    if tplh is not None:
        tplh = float(tplh) * 1e3
    if tphl is not None:
        tphl = float(tphl) * 1e3
    if tplh is None and t.get("propagation_delay_ns") is not None:
        ns = float(t["propagation_delay_ns"])
        tplh = ns * 1e3
        tphl = ns * 1e3
    return tplh, tphl


def _row_vteam_memristor(gate_key: str, gate_id: str, gate_label: str) -> dict[str, Any]:
    try:
        result = compute_memristor_architecture_cost(gate=gate_key, model_type="vteam", preset="vteam_default")
        layout = result.get("layout") or {}
        power = result.get("power") or {}
        timing = result.get("timing") or {}
        tplh, tphl = _timing_ps_from_architecture(timing)
        return _row(
            gate_key=gate_key,
            gate_id=gate_id,
            gate_label=gate_label,
            area_um2=layout.get("total_area_um2"),
            wirelength_um=layout.get("interconnect_um"),
            avg_power_1e4_w=_power_in_1e4_w_from_uw(power.get("avg_uw")),
            hpwl_um=None,
            t_plh_ps=tplh,
            t_phl_ps=tphl,
            error=None if result.get("ngspice_ok") else result.get("ngspice_error"),
        )
    except Exception as exc:
        return _row(
            gate_key=gate_key,
            gate_id=gate_id,
            gate_label=gate_label,
            error=str(exc),
        )


def _row_stanford_cntfet(gate_key: str, gate_id: str, gate_label: str) -> dict[str, Any]:
    try:
        result = compute_cntfet_architecture_cost(gate=gate_key, citation="stanford")
        layout = result.get("layout") or {}
        power = result.get("power") or {}
        timing = result.get("timing") or {}
        tplh, tphl = _timing_ps_from_architecture(timing)
        return _row(
            gate_key=gate_key,
            gate_id=gate_id,
            gate_label=gate_label,
            area_um2=layout.get("total_area_um2"),
            wirelength_um=layout.get("interconnect_um"),
            avg_power_1e4_w=_power_in_1e4_w_from_uw(power.get("avg_uw")),
            hpwl_um=None,
            t_plh_ps=tplh,
            t_phl_ps=tphl,
            error=None if result.get("ngspice_ok") else result.get("ngspice_error"),
        )
    except Exception as exc:
        return _row(
            gate_key=gate_key,
            gate_id=gate_id,
            gate_label=gate_label,
            error=str(exc),
        )


def _row_cmos_style(
    gate_key: str,
    gate_id: str,
    gate_label: str,
    *,
    realization: str,
) -> dict[str, Any]:
    area_um2: float | None = None
    wirelength_um: float | None = None
    hpwl_um: float | None = None
    or_error: str | None = None
    try:
        or_out = run_openroad_reversible_gate_metrics(gate=gate_id, realization=realization)  # type: ignore[arg-type]
        area_um2 = or_out.get("area_um2")
        wirelength_um = or_out.get("wirelength_um")
        excerpt = or_out.get("metrics_excerpt") or {}
        raw_hpwl = excerpt.get("design__io__hpwl")
        if raw_hpwl is not None:
            try:
                hpwl_um = float(raw_hpwl)
            except (TypeError, ValueError):
                hpwl_um = or_out.get("hpwl_um_est")
        else:
            hpwl_um = or_out.get("hpwl_um_est")
    except OpenroadMetricsError as exc:
        or_error = str(exc)
    except Exception as exc:
        or_error = str(exc)

    ng_error: str | None = None
    avg_power: float | None = None
    tplh: float | None = None
    tphl: float | None = None
    try:
        ng = analyze_reversible_gate(gate_id, realization, vdd=1.8)  # type: ignore[arg-type]
        step4 = ng.get("steps", {}).get("step_4_extract") or {}
        power = step4.get("power") or {}
        delay = step4.get("delay") or {}
        raw = step4.get("raw_measures") or {}
        p_avg = power.get("average_w")
        if p_avg is None:
            p_avg = raw.get("p_avg") or raw.get("pavg")
        avg_power = _power_in_1e4_w_from_w(p_avg if p_avg is not None else None)
        tplh = delay.get("t_plh_ps")
        tphl = delay.get("t_phl_ps")
        if tplh is None or tphl is None:
            gt = gate_timing_from_ngspice_measures(raw, gate=gate_id, vdd=1.8)
            if tplh is None:
                ns = gt.get("t_plh_ns")
                tplh = float(ns) * 1e3 if ns is not None else None
            if tphl is None:
                ns = gt.get("t_phl_ns")
                tphl = float(ns) * 1e3 if ns is not None else None
        if tplh is None:
            tplh, _ = _rise_fall_ps_from_measures(raw)
        if tphl is None:
            _, tphl = _rise_fall_ps_from_measures(raw)
        if tplh is None:
            tplh = _to_ps(delay.get("rise_time_s"))
        if tphl is None:
            tphl = _to_ps(delay.get("fall_time_s"))
        if ng.get("steps", {}).get("step_3_simulate", {}).get("ok") is False:
            ng_error = ng.get("steps", {}).get("step_3_simulate", {}).get("error") or "ngspice failed"
    except Exception as exc:
        ng_error = str(exc)

    err = " | ".join(x for x in (or_error, ng_error) if x) or None
    return _row(
        gate_key=gate_key,
        gate_id=gate_id,
        gate_label=gate_label,
        area_um2=area_um2,
        wirelength_um=wirelength_um,
        avg_power_1e4_w=avg_power,
        hpwl_um=hpwl_um,
        t_plh_ps=tplh,
        t_phl_ps=tphl,
        error=err,
    )


def build_cost_metrics_table(technology: str) -> dict[str, Any]:
    tech = technology.strip().lower()
    if tech not in ALLOWED_COST_METRIC_TECHNOLOGIES:
        raise ValueError(
            f"Unknown technology {technology!r}. "
            f"Use one of: {', '.join(sorted(ALLOWED_COST_METRIC_TECHNOLOGIES))}."
        )

    rows: list[dict[str, Any]] = []
    for gate_key, gate_id, gate_label in COST_METRIC_GATES:
        if tech == "vteam_memristor":
            rows.append(_row_vteam_memristor(gate_key, gate_id, gate_label))
        elif tech == "stanford_cntfet":
            rows.append(_row_stanford_cntfet(gate_key, gate_id, gate_label))
        elif tech == "pass_transistor":
            rows.append(
                _row_cmos_style(gate_key, gate_id, gate_label, realization="pass_transistor")
            )
        elif tech == "transmission_gate_logic":
            rows.append(
                _row_cmos_style(
                    gate_key, gate_id, gate_label, realization="transmission_gate_logic"
                )
            )
        else:
            rows.append(_row_cmos_style(gate_key, gate_id, gate_label, realization="static_cmos"))

    return {
        "technology": tech,
        "technology_label": TECHNOLOGY_LABELS[tech],
        "columns": {
            "area_um2": "Area (µm²)",
            "wirelength_um": "Wire-length (µm)",
            "avg_power_1e4_w": "Avg. power (10⁻⁴ W)",
            "hpwl_um": "HPWL (µm)",
            "t_plh_ps": "Rise time tPLH (ps)",
            "t_phl_ps": "Fall time tPHL (ps)",
        },
        "methodology": (
            "Post-CMOS rows: architecture-native layout (structural switch-element counts from "
            "static_cmos gate netlists) + ngspice transient on memristor/CNFET subcircuit decks. "
            "Static CMOS / pass-transistor / TGL rows: Nangate45 OpenROAD + ngspice reversible gate "
            "simulation (Vdd=1.8 V); tPLH/tPHL from the same Step 4 extraction as CMOS / PTL / TGL page."
        ),
        "rows": rows,
    }


__all__ = [
    "ALLOWED_COST_METRIC_TECHNOLOGIES",
    "COST_METRIC_GATES",
    "build_cost_metrics_table",
]
