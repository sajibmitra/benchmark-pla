"""ngspice memristor characterization (VTEAM / Yakopcic) for Post-CMOS metrics."""
from __future__ import annotations

import math
from typing import Any, Literal

from eda_hub.pages.post_cmos.memristor_gate import (
    build_memristor_gate_transient_netlist,
    gate_display_name,
    normalize_memristor_gate,
)
from eda_hub.pages.post_cmos.memristor_models import (
    GATE_LABEL,
    GATE_WIDTH,
    MemristorParams,
    PARAM_METADATA,
    device_body,
    list_presets_payload,
    resolve_params,
)
from eda_hub.pages.post_cmos.memristor_viz import time_series_svg, xy_plot_svg
from eda_hub.pages.cmos_ptl_tgl.reversible_ngspice import gate_waveform_nodes, gate_timing_from_ngspice_measures, resolve_gate_propagation_delay, run_ngspice_netlist

ModelType = Literal["vteam", "yakopcic"]
GateId = Literal["not", "feynman", "toffoli", "fredkin", "peres", "mux", "umg", "ung", "nmg", "custom"]


def _ns_to_s(ns: float) -> str:
    if ns >= 1000:
        return f"{ns * 1e-9:.6g}"
    return f"{ns}n"


def _build_pwl_programming(vdd: float, cycles: int, pulse_width_ns: float, gap_ns: float) -> str:
    """Alternating SET (+Vdd) and RESET (−Vdd) programming pulses."""
    points: list[str] = ["0 0"]
    t = 1.0
    for _ in range(cycles):
        rise = t
        high = t + pulse_width_ns
        fall = high + 1.0
        zero = fall + gap_ns
        points.extend(
            [
                f"{_ns_to_s(rise)} 0",
                f"{_ns_to_s(rise + 0.5)} {vdd}",
                f"{_ns_to_s(high)} {vdd}",
                f"{_ns_to_s(fall)} 0",
            ]
        )
        t = zero
        rise = t
        high = t + pulse_width_ns
        fall = high + 1.0
        zero = fall + gap_ns
        points.extend(
            [
                f"{_ns_to_s(rise)} 0",
                f"{_ns_to_s(rise + 0.5)} {-vdd}",
                f"{_ns_to_s(high)} {-vdd}",
                f"{_ns_to_s(fall)} 0",
            ]
        )
        t = zero
    stop = t + gap_ns
    return f"PWL({' '.join(points)})", stop


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


def _compute_resistance(v_vals: list[float], i_vals: list[float]) -> list[float]:
    out: list[float] = []
    for v, i in zip(v_vals, i_vals, strict=False):
        if abs(i) < 1e-18:
            out.append(float("nan"))
        else:
            out.append(abs(v / i))
    return out


def _integrate_energy_window(
    t: list[float], v: list[float], i: list[float], *, t_start: float, t_end: float
) -> float:
    if len(t) < 2:
        return 0.0
    e = 0.0
    for k in range(1, len(t)):
        if t[k] < t_start:
            continue
        if t[k - 1] > t_end:
            break
        dt = t[k] - t[k - 1]
        if dt <= 0:
            continue
        p = 0.5 * (abs(v[k] * i[k]) + abs(v[k - 1] * i[k - 1]))
        e += p * dt
    return e


def _find_delay(t: list[float], x: list[float], *, frac: float = 0.5) -> float | None:
    if len(t) < 2 or len(x) < 2:
        return None
    x0, x1 = x[0], x[-1]
    target = x0 + frac * (x1 - x0)
    for k in range(1, len(t)):
        if (x[k - 1] - target) * (x[k] - target) <= 0 and x[k] != x[k - 1]:
            alpha = (target - x[k - 1]) / (x[k] - x[k - 1])
            return t[k - 1] + alpha * (t[k] - t[k - 1])
    return None


def build_hysteresis_netlist(
    model: ModelType,
    params: MemristorParams,
    *,
    sweep_amplitude_v: float,
    sweep_period_us: float,
) -> str:
    half = sweep_period_us * 0.5
    body = device_body(model, params)
    amp = sweep_amplitude_v
    return f"""* Memristor I-V hysteresis ({model})
.title memristor_hysteresis
{body}
Vdrv drv 0 PWL(0 {-amp} {half}u {amp} {sweep_period_us}u {-amp})
Vsense drv TEi 0
.tran 10n {sweep_period_us}u 0 10n
.option noopiter
.end
"""


def build_programming_netlist(
    model: ModelType,
    gate: GateId,
    params: MemristorParams,
    *,
    vdd: float,
    pulse_width_ns: float,
    gap_ns: float,
) -> tuple[str, float]:
    cycles = GATE_WIDTH.get(gate, 2)
    pwl, stop_ns = _build_pwl_programming(vdd, cycles, pulse_width_ns, gap_ns)
    stop_s = stop_ns * 1e-9
    step = min(max(pulse_width_ns * 0.05, 0.5), 200.0)
    body = device_body(model, params)
    t_meas_hi = _ns_to_s(stop_ns - gap_ns)
    vlo = vdd * 0.1
    vhi = vdd * 0.9
    x_mid = 0.5
    x_set_start = params.x_init
    x_reset_target = params.x_init
    pulse_end = _ns_to_s(pulse_width_ns + 1.0)
    return (
        f"""* Memristor programming transient ({model}, gate={gate})
.title memristor_programming
{body}
Vdrv drv 0 {pwl}
Vsense drv TEi 0
.tran {_ns_to_s(step)} {_ns_to_s(stop_ns + gap_ns)} 0 {_ns_to_s(step)}
.option noopiter
.measure tran iset MAX i(Vsense) FROM=2n TO={t_meas_hi}
.measure tran ireset MIN i(Vsense) FROM=2n TO={t_meas_hi}
.measure tran xfinal AVG v(nX) FROM={t_meas_hi} TO={_ns_to_s(stop_ns + gap_ns - 1)}
.measure tran trise TRIG v(TEi) VAL={vlo} RISE=1 TARG v(nX) VAL={x_mid} RISE=1
.measure tran tfall TRIG v(TEi) VAL={vhi} FALL=1 TARG v(nX) VAL={x_reset_target} FALL=1
.measure tran eset INTEG PAR('abs(v(TEi)*i(Vsense))') FROM=1n TO={pulse_end}
.end
""",
        stop_s,
    )


def analyze_memristor_characterization(
    gate: GateId,
    model: ModelType,
    *,
    preset: str = "vteam_default",
    params: MemristorParams | None = None,
    param_overrides: dict[str, float | None] | None = None,
    vdd_volts: float = 1.0,
    pulse_width_ns: float = 50.0,
    pulse_gap_ns: float = 20.0,
    sweep_period_us: float = 40.0,
) -> dict[str, Any]:
    """Run hysteresis + programming transients; return plots and measurement table."""
    resolved, preset_id = resolve_params(preset, overrides=param_overrides)
    if params is not None:
        resolved = params
    sweep_amp = max(abs(resolved.von), abs(resolved.voff), vdd_volts)

    hyst_net = build_hysteresis_netlist(
        model,
        resolved,
        sweep_amplitude_v=sweep_amp,
        sweep_period_us=sweep_period_us,
    )
    prog_net, _ = build_programming_netlist(
        model,
        gate,
        resolved,
        vdd=vdd_volts,
        pulse_width_ns=pulse_width_ns,
        gap_ns=pulse_gap_ns,
    )

    hyst_sim = run_ngspice_netlist(
        hyst_net,
        label=f"memristor_hysteresis_{model}",
        waveform_exprs=("v(TEi)", "i(Vsense)"),
        waveform_columns=("V_mem", "I_mem"),
    )
    prog_sim = run_ngspice_netlist(
        prog_net,
        label=f"memristor_programming_{model}_{gate}",
        waveform_exprs=("v(TEi)", "i(Vsense)", "v(nX)"),
        waveform_columns=("V_pulse", "I_mem", "x_state"),
    )

    gate_netlist, _gate_probe = build_memristor_gate_transient_netlist(gate, resolved, vdd=vdd_volts)
    gate_gid = normalize_memristor_gate(gate)
    gate_sim = run_ngspice_netlist(
        gate_netlist,
        label=f"memristor_gate_{gate_display_name(gate)}",
        waveform_nodes=gate_waveform_nodes(gate_gid),
    )

    hyst_cols = _wave_columns(hyst_sim.get("waveform"))
    prog_cols = _wave_columns(prog_sim.get("waveform"))

    v_h = hyst_cols.get("V_mem", [])
    i_h = hyst_cols.get("I_mem", [])
    t_p = prog_cols.get("time_s", [])
    v_p = prog_cols.get("V_pulse", [])
    i_p = prog_cols.get("I_mem", [])
    x_p = prog_cols.get("x_state", [])
    r_p = _compute_resistance(v_p, i_p)

    measures = {**(hyst_sim.get("measures") or {}), **(prog_sim.get("measures") or {})}
    gate_meas = gate_sim.get("measures") or {}
    pulse_end_s = (pulse_width_ns + 1.0) * 1e-9
    energy_j = measures.get("eset")
    if energy_j is None and t_p:
        energy_j = _integrate_energy_window(t_p, v_p, i_p, t_start=1e-9, t_end=pulse_end_s)
    else:
        energy_j = float(energy_j or 0.0)
    set_delay = measures.get("trise")
    reset_delay = measures.get("tfall")
    gate_pavg = gate_meas.get("pavg") if gate_meas.get("pavg") is not None else gate_meas.get("p_avg")
    gate_pstat = gate_meas.get("pstat") if gate_meas.get("pstat") is not None else gate_meas.get("p_static")
    gate_delay = resolve_gate_propagation_delay(gate_sim, gate_gid, vdd_volts)
    gate_timing = gate_timing_from_ngspice_measures(
        gate_meas, gate=gate_gid, gate_sim=gate_sim, vdd=vdd_volts
    )
    gate_puw = abs(gate_pavg) * 1e6 if gate_pavg is not None else None
    gate_pstat_uw = abs(gate_pstat) * 1e6 if gate_pstat is not None else None
    gate_pdyn_uw = None
    if gate_puw is not None and gate_pstat_uw is not None:
        gate_pdyn_uw = max(gate_puw - gate_pstat_uw, 0.0)
    circuit_label = gate_display_name(gate)
    r_final = r_p[-1] if r_p and math.isfinite(r_p[-1]) else None
    r_init = r_p[0] if r_p and math.isfinite(r_p[0]) else None
    i_peak = max((abs(x) for x in i_p), default=None)
    x_delay = _find_delay(t_p, x_p) if t_p and x_p else None

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
        {"quantity": "Gate context", "value": GATE_LABEL.get(gate, gate), "unit": "—"},
        {"quantity": "Model", "value": model.upper(), "unit": "—"},
        {"quantity": "Preset", "value": preset_id, "unit": "—"},
        {"quantity": "Programming amplitude", "value": f"{vdd_volts:.3g}", "unit": "V"},
        {"quantity": "Ron (table)", "value": f"{resolved.ron:.4g}", "unit": "Ω"},
        {"quantity": "Roff (table)", "value": f"{resolved.roff:.4g}", "unit": "Ω"},
        {"quantity": "Initial resistance R(0)", "value": f"{r_init:.4g}" if r_init else "—", "unit": "Ω"},
        {"quantity": "Final resistance R(t_end)", "value": f"{r_final:.4g}" if r_final else "—", "unit": "Ω"},
        {
            "quantity": "Peak |I| during programming",
            "value": f"{i_peak:.4g}" if i_peak is not None else "—",
            "unit": "A",
        },
        {
            "quantity": "SET delay (50% state, ngspice)",
            "value": f"{set_delay * 1e9:.2f}" if set_delay is not None else "—",
            "unit": "ns",
        },
        {
            "quantity": "RESET delay (50% state, ngspice)",
            "value": f"{reset_delay * 1e9:.2f}" if reset_delay is not None else "—",
            "unit": "ns",
        },
        {
            "quantity": "State midpoint crossing time",
            "value": f"{x_delay * 1e9:.2f}" if x_delay is not None else "—",
            "unit": "ns",
        },
        {
            "quantity": "Switching energy ∫|V·I|dt (per pulse)",
            "value": f"{energy_j * 1e15:.2f}" if energy_j else "—",
            "unit": "fJ",
        },
        {
            "quantity": "I_SET peak (ngspice .measure)",
            "value": f"{measures['iset']:.4g}" if "iset" in measures else "—",
            "unit": "A",
        },
        {
            "quantity": "I_RESET valley (ngspice .measure)",
            "value": f"{measures['ireset']:.4g}" if "ireset" in measures else "—",
            "unit": "A",
        },
    ]

    hyst_wf = hyst_sim.get("waveform")
    prog_wf = prog_sim.get("waveform")
    hyst_ok = bool(hyst_sim.get("ok")) or bool(hyst_wf and hyst_wf.get("rows"))
    prog_ok = bool(prog_sim.get("ok")) or bool(prog_wf and prog_wf.get("rows"))
    ok = hyst_ok and prog_ok
    error_parts = []
    if not hyst_ok:
        error_parts.append(hyst_sim.get("error") or "hysteresis simulation failed")
    if not prog_ok:
        error_parts.append(prog_sim.get("error") or "programming simulation failed")

    plots = {
        "hysteresis_iv_svg": xy_plot_svg(
            v_h,
            i_h,
            title="Pinched I–V hysteresis loop",
            x_label="V across memristor (V)",
            y_label="I through memristor (A)",
            stroke="#06c",
        ),
        "programming_pulses_svg": time_series_svg(
            t_p,
            {"V_pulse": v_p},
            title="Applied programming pulses",
            y_label="V (V)",
        ),
        "current_vs_time_svg": time_series_svg(
            t_p,
            {"I_mem": i_p},
            title="Memristor current vs time",
            y_label="I (A)",
        ),
        "state_variable_svg": time_series_svg(
            t_p,
            {"x(t)": x_p},
            title="State variable x(t)",
            y_label="x (norm.)",
        ),
        "resistance_vs_time_svg": time_series_svg(
            t_p,
            {"R(t)": [r if math.isfinite(r) else 0.0 for r in r_p]},
            title="Resistance R(t) = |V/I|",
            y_label="R (Ω)",
        ),
    }

    return {
        "ok": ok,
        "gate": gate,
        "gate_label": GATE_LABEL.get(gate, gate),
        "circuit_label": circuit_label,
        "model": model,
        "preset": preset_id,
        "params": resolved.as_dict(),
        "parameter_metadata": PARAM_METADATA,
        "vdd": vdd_volts,
        "pulse_width_ns": pulse_width_ns,
        "pulse_gap_ns": pulse_gap_ns,
        "sweep_period_us": sweep_period_us,
        "error": "; ".join(error_parts) if error_parts else None,
        "ngspice_executable": hyst_sim.get("ngspice_executable") or prog_sim.get("ngspice_executable"),
        "measurements": measurement_rows,
        "measures_raw": measures,
        "gate_timing": gate_timing,
        "plots": plots,
        "netlists": {
            "hysteresis": hyst_net,
            "programming": prog_net,
            "gate_transient": gate_netlist,
        },
        "simulation": {
            "hysteresis": {
                "ok": hyst_sim.get("ok"),
                "exit_code": hyst_sim.get("exit_code"),
                "log_excerpt": (hyst_sim.get("log") or "")[-4000:],
            },
            "programming": {
                "ok": prog_sim.get("ok"),
                "exit_code": prog_sim.get("exit_code"),
                "log_excerpt": (prog_sim.get("log") or "")[-4000:],
            },
        },
    }


__all__ = [
    "analyze_memristor_characterization",
    "build_hysteresis_netlist",
    "build_programming_netlist",
    "list_presets_payload",
]
