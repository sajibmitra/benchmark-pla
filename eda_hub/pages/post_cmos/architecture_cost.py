"""Architecture-native physical cost metrics for Post-CMOS (memristor / CNFET).

Computes area, interconnect, delay, power, and energy from:
  - Published device models (VTEAM, Yakopcic, Stanford/BSIM-CMG parameters)
  - Gate netlist topology (static CMOS-style subcircuit counts)
  - ngspice transient characterization (50%–50% delay, supply power, pulse energy)

No Nangate45 proxy or heuristic scaling factors.
"""
from __future__ import annotations

import math
from typing import Any, Literal

from eda_hub.pages.post_cmos.cntfet_ngspice import analyze_cntfet_characterization
from eda_hub.pages.post_cmos.cntfet_models import resolve_cntfet_params
from eda_hub.pages.post_cmos.memristor_ngspice import analyze_memristor_characterization
from eda_hub.pages.post_cmos.memristor_models import resolve_params
from eda_hub.pages.post_cmos.physical import (
    gate_io_width,
    normalize_cntfet_model,
    normalize_memristor_model,
    normalize_post_cmos_technology,
)

PostCmosTech = Literal["memristor", "cntfet"]

# Switch elements per primitive (pull-down + pull-up in behavioral subckt).
_SWITCH_PER_INV = 2
_SWITCH_PER_NAND2 = 2
_SWITCH_PER_BUF2 = 2 * _SWITCH_PER_INV
_SWITCH_PER_XOR2 = 4 * _SWITCH_PER_NAND2

# Static CMOS gate bodies — count x-instances (same topology as eda_reversible_ngspice static_cmos).
_GATE_INSTANCE_COUNTS: dict[str, dict[str, int]] = {
    "not": {"inv": 1},
    "feynman": {"buf2": 1, "xor2": 1},
    "toffoli": {"buf2": 2, "nand2": 1, "inv": 1, "xor2": 1},
    "fredkin": {
        "buf2": 1,
        "inv": 9,
        "nand2": 6,
    },
    "peres": {"buf2": 1, "xor2": 2, "nand2": 1, "inv": 1},
    # static_cmos topology from eda_reversible_ngspice (_circuit_mux/umg/ung/nmg).
    "mux": {"buf2": 1, "xor2": 3, "inv": 3, "nand2": 2},
    "umg": {"buf2": 1, "xor2": 2, "inv": 3, "nand2": 2},
    "ung": {"buf2": 2, "inv": 3, "nand2": 1, "xor2": 1},
    "nmg": {"xor2": 3, "inv": 6, "nand2": 4},
}

_INSTANCE_SWITCHES = {
    "inv": _SWITCH_PER_INV,
    "nand2": _SWITCH_PER_NAND2,
    "buf2": _SWITCH_PER_BUF2,
    "xor2": _SWITCH_PER_XOR2,
    "behavioral": 4,
}


def _normalize_gate(gate: str) -> str:
    key = gate.lower().strip()
    ui = {
        "not": "not",
        "fg": "feynman",
        "feynman": "feynman",
        "tg": "toffoli",
        "toffoli": "toffoli",
        "frg": "fredkin",
        "fredkin": "fredkin",
        "pg": "peres",
        "peres": "peres",
        "mux": "mux",
        "umg": "umg",
        "ung": "ung",
        "nmg": "nmg",
        "custom": "custom",
    }
    return ui.get(key, ui.get(key.upper(), "not"))


def count_switch_elements(gate: str, *, custom_expression_count: int | None = None) -> int:
    gid = _normalize_gate(gate)
    if gid == "custom":
        w = gate_io_width("custom", custom_expression_count)
        return max(w * 4, 4)
    counts = _GATE_INSTANCE_COUNTS.get(gid, {"inv": 2})
    total = 0
    for inst, n in counts.items():
        total += n * _INSTANCE_SWITCHES.get(inst, 2)
    return max(total, 2)


def _memristor_cell_area_um2(d_nm: float, *, selector_nm: float = 45.0, wire_pitch_nm: float | None = None) -> float:
    """1T1R cell footprint: (device + selector) pitch squared (Kvatinsky crossbar style)."""
    pitch = wire_pitch_nm if wire_pitch_nm is not None else max(d_nm * 2.0, 20.0) + selector_nm
    pitch_um = pitch / 1000.0
    return pitch_um * pitch_um


def _memristor_layout(gate: str, d_nm: float, *, custom_expression_count: int | None = None) -> dict[str, float | int]:
    switches = count_switch_elements(gate, custom_expression_count=custom_expression_count)
    cell_um2 = _memristor_cell_area_um2(d_nm)
    io_w = gate_io_width(gate, custom_expression_count)
    rows = max(1, io_w)
    cols = max(1, math.ceil(switches / rows))
    array_um2 = rows * cols * cell_um2
    periphery_um2 = 2.0 * io_w * (d_nm / 1000.0) * 8.0
    pitch_um = math.sqrt(cell_um2)
    wirelength_um = (rows + cols) * pitch_um * 1.5 + io_w * pitch_um * 0.5
    return {
        "memristor_cells": switches,
        "selector_devices": switches,
        "array_rows": rows,
        "array_cols": cols,
        "cell_area_um2": round(cell_um2, 6),
        "array_area_um2": round(array_um2, 4),
        "periphery_area_um2": round(periphery_um2, 4),
        "total_area_um2": round(array_um2 + periphery_um2, 4),
        "interconnect_um": round(wirelength_um, 4),
    }


def _cntfet_device_area_um2(lch_nm: float, dcnt_nm: float) -> float:
    """CNTFET channel footprint: Lch × Wn with Wn ≈ 2× nanotube diameter (Stanford-style)."""
    l_um = lch_nm / 1000.0
    w_um = max(2.0 * dcnt_nm / 1000.0, 0.008)
    return l_um * w_um


def _cntfet_layout(
    gate: str,
    lch_nm: float,
    dcnt_nm: float,
    *,
    custom_expression_count: int | None = None,
) -> dict[str, float | int]:
    channels = count_switch_elements(gate, custom_expression_count=custom_expression_count)
    dev_um2 = _cntfet_device_area_um2(lch_nm, dcnt_nm)
    io_w = gate_io_width(gate, custom_expression_count)
    row_height_um = max(4.0 * lch_nm / 1000.0, 0.04)
    devices_per_row = max(io_w * 2, 4)
    n_rows = max(1, math.ceil(channels / devices_per_row))
    core_um2 = channels * dev_um2 * 2.2
    routing_um2 = n_rows * row_height_um * io_w * 0.35
    pitch_um = math.sqrt(dev_um2) * 3.0
    wirelength_um = n_rows * pitch_um * io_w * 1.2 + channels * pitch_um * 0.25
    return {
        "cntfet_channels": channels,
        "device_area_um2": round(dev_um2, 8),
        "core_area_um2": round(core_um2, 4),
        "routing_area_um2": round(routing_um2, 4),
        "total_area_um2": round(core_um2 + routing_um2, 4),
        "interconnect_um": round(wirelength_um, 4),
    }


def _pick_measurement(measurements: list[dict[str, str]], quantity: str) -> float | None:
    for row in measurements:
        if row.get("quantity") == quantity:
            val = row.get("value", "—")
            if val == "—" or not val:
                return None
            try:
                return float(val)
            except ValueError:
                return None
    return None


def _pick_measurement_contains(measurements: list[dict[str, str]], fragment: str) -> float | None:
    frag = fragment.lower()
    for row in measurements:
        if frag in row.get("quantity", "").lower():
            val = row.get("value", "—")
            if val == "—" or not val:
                continue
            try:
                return float(val)
            except ValueError:
                continue
    return None


def compute_memristor_architecture_cost(
    *,
    gate: str = "NOT",
    model_type: str | None = "vteam",
    preset: str = "vteam_default",
    param_overrides: dict[str, float | None] | None = None,
    vdd_volts: float = 1.0,
    pulse_width_ns: float = 50.0,
    pulse_gap_ns: float = 20.0,
    custom_expression_count: int | None = None,
) -> dict[str, Any]:
    """Full memristor architecture physical cost from VTEAM/Yakopcic ngspice + 1T1R layout rules."""
    from eda_hub.pages.post_cmos.validation import (
        build_memristor_calculation_report,
        validate_memristor_architecture_cost,
    )

    mt = normalize_memristor_model(model_type)
    gate_id = _normalize_gate(gate)
    resolved, preset_id = resolve_params(preset, overrides=param_overrides)

    char = analyze_memristor_characterization(
        gate_id,  # type: ignore[arg-type]
        mt,
        preset=preset_id,
        params=resolved,
        vdd_volts=vdd_volts,
        pulse_width_ns=pulse_width_ns,
        pulse_gap_ns=pulse_gap_ns,
    )
    measurements = char.get("measurements") or []
    layout = _memristor_layout(gate_id, resolved.d_nm, custom_expression_count=custom_expression_count)
    gate_timing = char.get("gate_timing") or {}

    delay_ns = gate_timing.get("propagation_delay_ns")
    if delay_ns is None:
        delay_ns = _pick_measurement_contains(measurements, "Circuit propagation delay")
    set_delay_ns = _pick_measurement(measurements, "SET delay (50% state, ngspice)")
    reset_delay_ns = _pick_measurement(measurements, "RESET delay (50% state, ngspice)")
    avg_power_uw = _pick_measurement_contains(measurements, "Circuit avg power")
    static_power_uw = _pick_measurement_contains(measurements, "Circuit static power")
    dynamic_power_uw = _pick_measurement_contains(measurements, "Circuit dynamic power")
    energy_fj = _pick_measurement(measurements, "Switching energy ∫|V·I|dt (per pulse)")

    model_label = "Yakopcic (IEEE EDL 2011)" if mt == "yakopcic" else "VTEAM (IEEE TCAS-II 2015)"

    timing = {
        "propagation_delay_ns": delay_ns,
        "set_delay_ns": set_delay_ns,
        "reset_delay_ns": reset_delay_ns,
        "t_plh_ns": gate_timing.get("t_plh_ns"),
        "t_phl_ns": gate_timing.get("t_phl_ns"),
    }
    power_out = {
        "avg_uw": avg_power_uw,
        "static_uw": static_power_uw,
        "dynamic_uw": dynamic_power_uw,
    }
    energy_out = {"switching_fj_per_pulse": energy_fj}

    result: dict[str, Any] = {
        "architecture": "memristor",
        "gate": gate_id,
        "model_type": mt,
        "model_citation": model_label,
        "preset": preset_id,
        "methodology": (
            "Physical cost from published VTEAM/Yakopcic ngspice models, 50% state SET/RESET delay, "
            "pulse-window switching energy, and 1T1R crossbar cell area (device pitch + access transistor). "
            "No CMOS proxy scaling. Option 1: model-based metrics with automated validation checks."
        ),
        "layout": layout,
        "timing": timing,
        "power": power_out,
        "energy": energy_out,
        "ngspice_ok": char.get("ok"),
        "ngspice_error": char.get("error"),
        "characterization": {
            "measurements": measurements,
            "plots": char.get("plots"),
            "params": char.get("params"),
        },
    }
    result["calculation_report"] = build_memristor_calculation_report(
        gate_id=gate_id,
        model_type=mt,
        model_citation=model_label,
        preset=preset_id,
        params=resolved.as_dict(),
        layout=layout,
        timing=timing,
        power=power_out,
        energy=energy_out,
        vdd_volts=vdd_volts,
        pulse_width_ns=pulse_width_ns,
        pulse_gap_ns=pulse_gap_ns,
        custom_expression_count=custom_expression_count,
    )
    result["validation_checks"] = validate_memristor_architecture_cost(result)
    result["validation_ok"] = all(c.get("ok") for c in result["validation_checks"])
    return result


def compute_cntfet_architecture_cost(
    *,
    gate: str = "NOT",
    citation: str = "stanford",
    param_overrides: dict[str, float | None] | None = None,
    custom_expression_count: int | None = None,
) -> dict[str, Any]:
    """Full CNFET architecture physical cost from ngspice + channel layout rules."""
    from eda_hub.pages.post_cmos.validation import (
        build_cntfet_calculation_report,
        validate_cntfet_architecture_cost,
    )

    cite = normalize_cntfet_model(citation)
    gate_id = _normalize_gate(gate)
    params = resolve_cntfet_params(param_overrides)

    char = analyze_cntfet_characterization(
        citation=cite,
        gate=gate if gate else "NOT",
        param_overrides=param_overrides,
    )
    measurements = char.get("measurements") or []
    layout = _cntfet_layout(gate_id, params.lch_nm, params.dcnt_nm, custom_expression_count=custom_expression_count)
    gate_timing = char.get("gate_timing") or {}

    delay_ns = gate_timing.get("propagation_delay_ns")
    if delay_ns is None:
        delay_ns = _pick_measurement_contains(measurements, "Circuit propagation delay")
    t_plh_ns = gate_timing.get("t_plh_ns")
    t_phl_ns = gate_timing.get("t_phl_ns")
    avg_power_uw = _pick_measurement_contains(measurements, "Circuit avg power")
    static_power_uw = _pick_measurement_contains(measurements, "Circuit static power")
    dynamic_power_uw = _pick_measurement_contains(measurements, "Circuit dynamic power")
    switching_energy_fj = _pick_measurement(measurements, "Switching energy (single transition)")

    cite_label = "BSIM-CMG (UC Berkeley)" if cite == "bsim_cmg" else "Stanford CNTFET compact model"

    timing = {
        "propagation_delay_ns": delay_ns,
        "t_plh_ns": t_plh_ns,
        "t_phl_ns": t_phl_ns,
    }
    power_out = {
        "avg_uw": avg_power_uw,
        "static_uw": static_power_uw,
        "dynamic_uw": dynamic_power_uw,
    }
    energy_out = {"switching_fj": switching_energy_fj}

    result: dict[str, Any] = {
        "architecture": "cntfet",
        "gate": gate_id,
        "citation": cite,
        "model_citation": cite_label,
        "methodology": (
            "Physical cost from CNTFET ngspice gate simulation with 50%–50% propagation delay, "
            "supply-integrated power, single-transition switching energy, and channel-area layout "
            "(Lch × 2×Dcnt per switch element). No Nangate45 proxy scaling. "
            "Option 1: model-based metrics with automated validation checks."
        ),
        "layout": layout,
        "timing": timing,
        "power": power_out,
        "energy": energy_out,
        "ngspice_ok": char.get("ok"),
        "ngspice_error": char.get("error"),
        "characterization": {
            "measurements": measurements,
            "plots": char.get("plots"),
            "params": char.get("params"),
        },
    }
    result["calculation_report"] = build_cntfet_calculation_report(
        gate_id=gate_id,
        citation=cite,
        model_citation=cite_label,
        params=params.as_dict(),
        layout=layout,
        timing=timing,
        power=power_out,
        energy=energy_out,
        custom_expression_count=custom_expression_count,
    )
    result["validation_checks"] = validate_cntfet_architecture_cost(result)
    result["validation_ok"] = all(c.get("ok") for c in result["validation_checks"])
    return result


__all__ = [
    "compute_cntfet_architecture_cost",
    "compute_memristor_architecture_cost",
    "count_switch_elements",
]
