"""Option 1 validation: calculation traces and consistency checks for Post-CMOS architecture cost."""
from __future__ import annotations

import math
from typing import Any

from eda_hub.pages.post_cmos.architecture_cost import (
    _GATE_INSTANCE_COUNTS,
    _INSTANCE_SWITCHES,
    _cntfet_device_area_um2,
    _memristor_cell_area_um2,
    count_switch_elements,
)
from eda_hub.pages.post_cmos.physical import gate_io_width

# Golden switch-element counts (hand-verified against static_cmos netlist instance map).
GOLDEN_SWITCH_COUNTS: dict[str, int] = {
    "not": 2,
    "feynman": 12,
    "toffoli": 20,
    "fredkin": 34,
    "peres": 24,
    "mux": 38,
    "umg": 30,
    "ung": 24,
    "nmg": 44,
}


def _fmt(v: float | int | None, digits: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, int):
        return str(v)
    return f"{v:.{digits}f}"


def _gate_instance_breakdown(gate_id: str) -> list[tuple[str, int, int, int]]:
    counts = _GATE_INSTANCE_COUNTS.get(gate_id, {"inv": 1})
    rows: list[tuple[str, int, int, int]] = []
    for inst, n in counts.items():
        per = _INSTANCE_SWITCHES.get(inst, 2)
        rows.append((inst, n, per, n * per))
    return rows


def build_memristor_calculation_report(
    *,
    gate_id: str,
    model_type: str,
    model_citation: str,
    preset: str,
    params: dict[str, float],
    layout: dict[str, Any],
    timing: dict[str, Any],
    power: dict[str, Any],
    energy: dict[str, Any],
    vdd_volts: float,
    pulse_width_ns: float,
    pulse_gap_ns: float,
    custom_expression_count: int | None,
) -> str:
    d_nm = float(params.get("d_nm", 10.0))
    selector_nm = 45.0
    pitch_nm = max(d_nm * 2.0, 20.0) + selector_nm
    cell_um2 = _memristor_cell_area_um2(d_nm)
    switches = count_switch_elements(gate_id, custom_expression_count=custom_expression_count)
    io_w = gate_io_width(gate_id, custom_expression_count)
    rows = max(1, io_w)
    cols = max(1, math.ceil(switches / rows))

    lines = [
        "Post-CMOS memristor architecture cost — Option 1 calculation trace",
        "=" * 60,
        f"Gate ID: {gate_id}",
        f"Model: {model_citation} ({model_type}), preset={preset}",
        f"Simulation: Vdd={vdd_volts} V, pulse_width={pulse_width_ns} ns, pulse_gap={pulse_gap_ns} ns",
        "",
        "LAYOUT (architecture-native — analytical, not from ngspice)",
        "-" * 40,
        "Switch count = Σ (subcircuit_instances × switches_per_instance)",
        "  inv=2, nand2=2, buf2=4, xor2=8, behavioral=4 switches (pull-up + pull-down each)",
    ]
    for inst, n, per, sub in _gate_instance_breakdown(gate_id):
        lines.append(f"  {inst}: {n} instance(s) × {per} = {sub}")
    lines.extend(
        [
            f"  Total switch elements: {switches}",
            f"  I/O width: {io_w}",
            f"  Crossbar array: {rows} × {cols} cells",
            f"  Cell pitch (nm) = max(2×D, 20) + selector = max(2×{d_nm}, 20) + {selector_nm} = {pitch_nm}",
            f"  Cell area (µm²) = (pitch_nm/1000)² = {_fmt(cell_um2, 6)}",
            f"  Array area (µm²) = rows × cols × cell = {_fmt(layout.get('array_area_um2'))}",
            f"  Periphery (µm²) = 2 × io_w × (D_nm/1000) × 8 = {_fmt(layout.get('periphery_area_um2'))}",
            f"  Total area (µm²) = array + periphery = {_fmt(layout.get('total_area_um2'))}",
            f"  Interconnect (µm) ≈ (rows+cols)×√cell×1.5 + io_w×√cell×0.5 = {_fmt(layout.get('interconnect_um'))}",
            "",
            "ELECTRICAL (ngspice — VTEAM/Yakopcic behavioral deck + gate transient)",
            "-" * 40,
            f"  Gate propagation delay (ns): {_fmt(timing.get('propagation_delay_ns'), 3)}",
            f"  SET delay 50% state x (ns): {_fmt(timing.get('set_delay_ns'), 3)}",
            f"  RESET delay 50% state x (ns): {_fmt(timing.get('reset_delay_ns'), 3)}",
            f"  Avg / static / dynamic power (µW): {_fmt(power.get('avg_uw'), 3)} / "
            f"{_fmt(power.get('static_uw'), 3)} / {_fmt(power.get('dynamic_uw'), 3)}",
            f"  Switching energy per pulse (fJ): {_fmt(energy.get('switching_fj_per_pulse'), 2)}",
            "",
            "REFERENCES: Kvatinsky VTEAM (IEEE TCAS-II 2015); Yakopcic (IEEE EDL 2011).",
            "LIMIT: model-based exploration metrics — not foundry GDS/LEF signoff.",
        ]
    )
    return "\n".join(lines)


def build_cntfet_calculation_report(
    *,
    gate_id: str,
    citation: str,
    model_citation: str,
    params: dict[str, float],
    layout: dict[str, Any],
    timing: dict[str, Any],
    power: dict[str, Any],
    energy: dict[str, Any],
    custom_expression_count: int | None,
) -> str:
    lch = float(params.get("lch_nm", 10.0))
    dcnt = float(params.get("dcnt_nm", 1.2))
    dev_um2 = _cntfet_device_area_um2(lch, dcnt)
    w_um = max(2.0 * dcnt / 1000.0, 0.008)
    channels = count_switch_elements(gate_id, custom_expression_count=custom_expression_count)
    io_w = gate_io_width(gate_id, custom_expression_count)
    devices_per_row = max(io_w * 2, 4)
    n_rows = max(1, math.ceil(channels / devices_per_row))

    lines = [
        "Post-CMOS CNFET architecture cost — Option 1 calculation trace",
        "=" * 60,
        f"Gate ID: {gate_id}",
        f"Model: {model_citation} ({citation})",
        "",
        "LAYOUT (architecture-native — analytical, not from ngspice)",
        "-" * 40,
    ]
    for inst, n, per, sub in _gate_instance_breakdown(gate_id):
        lines.append(f"  {inst}: {n} instance(s) × {per} = {sub}")
    lines.extend(
        [
            f"  Total CNTFET channels (switch elements): {channels}",
            f"  Device footprint (µm²) = Lch/1000 × max(2×Dcnt/1000, 0.008) = {lch/1000} × {w_um} = {_fmt(dev_um2, 8)}",
            f"  Core area (µm²) = channels × device × 2.2 = {_fmt(layout.get('core_area_um2'))}",
            f"  Routing area (µm²) = n_rows × row_height × io_w × 0.35 = {_fmt(layout.get('routing_area_um2'))}",
            f"  Total area (µm²) = core + routing = {_fmt(layout.get('total_area_um2'))}",
            f"  Interconnect (µm) = n_rows×pitch×io_w×1.2 + channels×pitch×0.25 = {_fmt(layout.get('interconnect_um'))}",
            f"    (n_rows={n_rows}, devices_per_row={devices_per_row}, io_w={io_w})",
            "",
            "ELECTRICAL (ngspice — behavioral CNTFET deck + gate transient)",
            "-" * 40,
            f"  Gate propagation delay (ns): {_fmt(timing.get('propagation_delay_ns'), 3)}",
            f"  tPLH / tPHL 50%–50% (ns): {_fmt(timing.get('t_plh_ns'), 3)} / {_fmt(timing.get('t_phl_ns'), 3)}",
            f"  Avg / static / dynamic power (µW): {_fmt(power.get('avg_uw'), 3)} / "
            f"{_fmt(power.get('static_uw'), 3)} / {_fmt(power.get('dynamic_uw'), 3)}",
            f"  Switching energy single transition (fJ): {_fmt(energy.get('switching_fj'), 2)}",
            "",
            "LIMIT: behavioral Stanford/BSIM-CMG proxy — not foundry GDS/LEF signoff.",
        ]
    )
    return "\n".join(lines)


def _check(ok: bool, check_id: str, label: str, detail: str) -> dict[str, Any]:
    return {"id": check_id, "ok": ok, "label": label, "detail": detail}


def validate_memristor_architecture_cost(result: dict[str, Any]) -> list[dict[str, Any]]:
    layout = result.get("layout") or {}
    timing = result.get("timing") or {}
    power = result.get("power") or {}
    gate_id = str(result.get("gate", "not"))
    checks: list[dict[str, Any]] = []

    switches = layout.get("memristor_cells")
    golden = GOLDEN_SWITCH_COUNTS.get(gate_id)
    if golden is not None and switches is not None:
        checks.append(
            _check(
                switches == golden,
                "switch_count_golden",
                "Switch count matches netlist map",
                f"computed={switches}, expected={golden} for gate {gate_id}",
            )
        )

    array_a = layout.get("array_area_um2")
    per_a = layout.get("periphery_area_um2")
    total_a = layout.get("total_area_um2")
    if all(isinstance(x, (int, float)) for x in (array_a, per_a, total_a)):
        expected = float(array_a) + float(per_a)
        checks.append(
            _check(
                abs(expected - float(total_a)) < 1e-3,
                "area_sum",
                "Total area = array + periphery",
                f"array({array_a}) + periphery({per_a}) = {expected:.4f}, reported total={total_a}",
            )
        )

    rows = layout.get("array_rows")
    cols = layout.get("array_cols")
    cell_a = layout.get("cell_area_um2")
    if all(isinstance(x, (int, float)) for x in (rows, cols, cell_a, array_a)):
        expected_array = float(rows) * float(cols) * float(cell_a)
        checks.append(
            _check(
                abs(expected_array - float(array_a)) < 1e-2,
                "array_area_formula",
                "Array area = rows × cols × cell_area",
                f"expected={expected_array:.4f}, reported={array_a}",
            )
        )

    checks.append(
        _check(
            bool(result.get("ngspice_ok")),
            "ngspice_simulation",
            "ngspice characterization completed",
            result.get("ngspice_error") or "hysteresis + programming transients produced data",
        )
    )

    avg_p = power.get("avg_uw")
    dyn_p = power.get("dynamic_uw")
    if avg_p is not None and dyn_p is not None:
        checks.append(
            _check(
                float(dyn_p) <= float(avg_p) + 1e-6,
                "dynamic_le_avg",
                "Dynamic power ≤ average power",
                f"dynamic={dyn_p} µW, avg={avg_p} µW",
            )
        )

    prop = timing.get("propagation_delay_ns")
    if prop is not None:
        checks.append(
            _check(
                float(prop) > 0,
                "propagation_delay_positive",
                "Gate propagation delay > 0",
                f"delay={prop} ns",
            )
        )

    return checks


def validate_cntfet_architecture_cost(result: dict[str, Any]) -> list[dict[str, Any]]:
    layout = result.get("layout") or {}
    timing = result.get("timing") or {}
    power = result.get("power") or {}
    gate_id = str(result.get("gate", "not"))
    checks: list[dict[str, Any]] = []

    channels = layout.get("cntfet_channels")
    golden = GOLDEN_SWITCH_COUNTS.get(gate_id)
    if golden is not None and channels is not None:
        checks.append(
            _check(
                channels == golden,
                "switch_count_golden",
                "Channel count matches netlist map",
                f"computed={channels}, expected={golden} for gate {gate_id}",
            )
        )

    core = layout.get("core_area_um2")
    route = layout.get("routing_area_um2")
    total = layout.get("total_area_um2")
    if all(isinstance(x, (int, float)) for x in (core, route, total)):
        expected = float(core) + float(route)
        checks.append(
            _check(
                abs(expected - float(total)) < 1e-3,
                "area_sum",
                "Total area = core + routing",
                f"core({core}) + routing({route}) = {expected:.4f}, reported total={total}",
            )
        )

    checks.append(
        _check(
            bool(result.get("ngspice_ok")),
            "ngspice_simulation",
            "ngspice characterization completed",
            result.get("ngspice_error") or "VTC + transient runs produced data",
        )
    )

    tplh = timing.get("t_plh_ns")
    tphl = timing.get("t_phl_ns")
    prop = timing.get("propagation_delay_ns")
    if tplh is not None and tphl is not None:
        checks.append(
            _check(
                float(tplh) > 0 and float(tphl) > 0,
                "inverter_delay_positive",
                "Inverter tPLH and tPHL > 0 (50%–50% deck)",
                f"tPLH={tplh} ns, tPHL={tphl} ns",
            )
        )
    if prop is not None:
        checks.append(
            _check(
                float(prop) > 0,
                "gate_delay_positive",
                "Gate propagation delay > 0 (gate transient deck)",
                f"delay={prop} ns",
            )
        )

    avg_p = power.get("avg_uw")
    dyn_p = power.get("dynamic_uw")
    if avg_p is not None and dyn_p is not None:
        checks.append(
            _check(
                float(dyn_p) <= float(avg_p) + 1e-6,
                "dynamic_le_avg",
                "Dynamic power ≤ average power",
                f"dynamic={dyn_p} µW, avg={avg_p} µW",
            )
        )

    return checks


__all__ = [
    "GOLDEN_SWITCH_COUNTS",
    "build_cntfet_calculation_report",
    "build_memristor_calculation_report",
    "validate_cntfet_architecture_cost",
    "validate_memristor_architecture_cost",
]
