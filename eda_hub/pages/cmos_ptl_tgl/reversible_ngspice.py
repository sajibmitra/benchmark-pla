"""Generate SPICE netlists for reversible gates, run ngspice, extract power/delay/switching."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from collections.abc import Callable
from typing import Any, Literal

from eda_hub.adapters.events import record_ngspice_event
from eda_hub.pages.cmos_ptl_tgl.reversible_viz import build_visualization_bundle
from eda_hub.pages.cmos_ptl_tgl.reversible_expr import (
    CUSTOM_OUTPUT_LABELS,
    CustomExprError,
    build_custom_behavioral_body,
    eval_outputs_tuple,
    normalize_custom_expressions,
    parse_expression,
    validate_reversible_permutation,
)

logger = logging.getLogger(__name__)

_ENV_NGSPICE_KEYS = ("EDA_NGSPICE", "NGSPICE_PATH", "NGSPICE")


def resolve_ngspice_executable() -> str | None:
    """Locate ngspice under EDA_ROOT only (Data/eda). Returns None if missing."""
    try:
        from eda_hub.tools import resolve_ngspice_executable as _resolve
        from eda_hub.tools import ToolNotFoundError
        return _resolve()
    except ToolNotFoundError:
        return None


GateId = Literal["not", "feynman", "toffoli", "fredkin", "peres", "mux", "umg", "ung", "nmg"]
Realization = Literal["static_cmos", "pass_transistor", "transmission_gate_logic"]

_MEASURE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+=\s*([-+eE0-9.]+)", re.MULTILINE)
_LOOSE_MEASURE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([-+0-9.eEdD,]+)",
    re.MULTILINE,
)

_CAP_ELEMENT = ("Clp", "Clq", "Clr", "Cls")
_TOGGLE_KEYS = ("y_p", "y_q", "y_r", "y_s")
_INPUT_LITERALS_ORDER = ("A", "B", "C", "D")

# Fixed 3-line reversible mappings (validated as bijections); simulated like custom (behavioral B-sources).
_NAMED_BEHAVIORAL_EXPRS_3: dict[str, tuple[str, str, str]] = {
    "umg": ("A", "B^C", "!A&C^A&B"),
    "ung": ("A", "B", "(A|B)^C"),
    "mux": ("A", "A^B^C", "~A&C^A&B"),
    "nmg": ("A^B", "B&!C^A&C", "!B&C^A&!C"),
}

# Legacy named-behavioral presets (no longer used for device-level gate decks).
_BEHAVIORAL_ONLY_GATES: frozenset[str] = frozenset()


def _overlay_named_behavioral_step1(gate_key: str, step1: dict[str, Any], exprs: tuple[str, str, str]) -> dict[str, Any]:
    """Replace generic custom step-1 text with catalog names (equations match user-facing literature)."""
    out = dict(step1)
    out["gate"] = gate_key
    out["named_behavioral"] = True
    out["parser_expressions"] = list(exprs)
    if gate_key == "umg":
        out["title"] = "Step 1 — Universal Multiplexer Gate (UMG)"
        out["description"] = (
            "The Universal Multiplexer Gate (UMG) is a 3×3 reversible gate: line A is preserved on P; "
            "Q combines B and C with XOR; R uses (¬A∧C)⊕(A∧B) so the eight input patterns map to eight "
            "distinct outputs (verified permutation)."
        )
        out["equations"] = ["P = A", "Q = B ⊕ C", "R = (¬A ∧ C) ⊕ (A ∧ B)"]
    elif gate_key == "ung":
        out["title"] = "Step 1 — Universal NOR Gate (UNG)"
        out["description"] = (
            "The Universal NOR Gate (UNG) fixes P=A and Q=B, and sets R = (A ∨ B) ⊕ C so the mapping "
            "on three bits is reversible (full permutation)."
        )
        out["equations"] = ["P = A", "Q = B", "R = (A ∨ B) ⊕ C"]
    elif gate_key == "nmg":
        out["title"] = "Step 1 — NMG reversible gate"
        out["description"] = (
            "The NMG gate is a 3×3 reversible gate: P = A ⊕ B, Q = (B ∧ ¬C) ⊕ (A ∧ C), and "
            "R = (¬B ∧ C) ⊕ (A ∧ ¬C), forming a valid bijection on (A,B,C)."
        )
        out["equations"] = [
            "P = A ⊕ B",
            "Q = (B ∧ ¬C) ⊕ (A ∧ C)",
            "R = (¬B ∧ C) ⊕ (A ∧ ¬C)",
        ]
    elif gate_key == "mux":
        out["title"] = "Step 1 — MUX reversible gate"
        out["description"] = (
            "This MUX-class 3×3 reversible gate passes A to P, sets Q = A ⊕ B ⊕ C, and "
            "R = (¬A ∧ C) ⊕ (A ∧ B), forming a valid bijection on (A,B,C)."
        )
        out["equations"] = ["P = A", "Q = A ⊕ B ⊕ C", "R = (¬A ∧ C) ⊕ (A ∧ B)"]
    else:
        raise ValueError(f"Unknown named behavioral gate {gate_key!r}")
    out["static_cmos_notes"] = (
        "UMG, UNG, and MUX named-behavioral overlays use the same ideal output model as “custom”; "
        "preset NMG / MUX / UMG / UNG simulation decks use structural NAND/INV/XOR netlists."
    )
    out["pass_transistor_notes"] = out["static_cmos_notes"]
    out["transmission_gate_logic_notes"] = out["static_cmos_notes"]
    return out


def _truth_table_literal_headers(width: int) -> tuple[list[str], list[str]]:
    """Input / output variable names for truth-table columns (left-to-right = A,B,… then P,Q,…)."""
    ins = list(_INPUT_LITERALS_ORDER[:width])
    outs = list(CUSTOM_OUTPUT_LABELS[:width])
    return ins, outs


def _eval_gate_outputs(gate: GateId, a: int, b: int, c: int) -> tuple[int, int, int]:
    """Return (p,q,r) as 0/1; unused lines still returned as 0 for 1- or 2-bit gates."""
    a, b, c = a & 1, b & 1, c & 1
    if gate == "not":
        return 1 - a, 0, 0
    if gate == "feynman":
        p, q = a, a ^ b
        return p, q, 0
    if gate == "toffoli":
        p, q, r = a, b, c ^ (a & b)
        return p, q, r
    if gate == "fredkin":
        p = a
        q = ((1 - a) & b) | (a & c)
        r = ((1 - a) & c) | (a & b)
        return p, q, r
    if gate == "peres":
        p, q = a, a ^ b
        r = c ^ (a & b)
        return p, q, r
    if gate == "mux":
        p = a
        q = a ^ b ^ c
        r = ((1 - a) & c) ^ (a & b)
        return p, q, r
    if gate == "umg":
        p = a
        q = b ^ c
        r = ((1 - a) & c) ^ (a & b)
        return p, q, r
    if gate == "ung":
        p = a
        q = b
        r = (a | b) ^ c
        return p, q, r
    if gate == "nmg":
        p = a ^ b
        q = ((b & (1 - c)) ^ (a & c))
        r = (((1 - b) & c) ^ (a & (1 - c)))
        return p, q, r
    raise ValueError(gate)


def _gate_width(gate: GateId) -> int:
    if gate == "not":
        return 1
    return 2 if gate == "feynman" else 3


def gate_delay_io_spec(gate: str) -> tuple[str, str, bool | None]:
    """
    Primary datapath nodes for propagation delay: (input, output, inverting).
    inverting=True: input rise → output fall (NOT). False: same-edge. None: XOR/complex (waveform).
    """
    specs: dict[str, tuple[str, str, bool | None]] = {
        "not": ("va", "vp", True),
        "feynman": ("vb", "vq", None),
        "toffoli": ("vc", "vr", None),
        "fredkin": ("vb", "vq", None),
        "peres": ("vc", "vr", None),
        "mux": ("vc", "vr", None),
        "umg": ("vc", "vr", None),
        "ung": ("vc", "vr", None),
        "nmg": ("vb", "vr", None),
    }
    return specs.get(gate.lower().strip(), ("va", "vp", True))


def gate_waveform_nodes(gate: str) -> tuple[str, ...]:
    """Input + output nodes to export for gate delay extraction."""
    g = gate.lower().strip()
    w = 1 if g == "not" else (2 if g == "feynman" else 3)
    ins = ("va", "vb", "vc", "vd")[:w]
    outs = ("vp", "vq", "vr", "vs")[:w]
    return ins + outs


def _interp_threshold_crossing(t0: float, t1: float, v0: float, v1: float, thresh: float) -> float:
    if v1 == v0:
        return t1
    frac = (thresh - v0) / (v1 - v0)
    frac = max(0.0, min(1.0, frac))
    return t0 + frac * (t1 - t0)


def _vout_at_time(t0: float, t1: float, v0: float, v1: float, t_query: float) -> float:
    if t1 <= t0:
        return v1
    alpha = (t_query - t0) / (t1 - t0)
    alpha = max(0.0, min(1.0, alpha))
    return v0 + alpha * (v1 - v0)


def _find_output_edge_delay(
    t: list[float],
    v_out: list[float],
    *,
    t_in: float,
    v_ref: float,
    vdd: float,
    edge: Literal["rise", "fall"] | None,
    start_k: int,
    max_window_s: float,
) -> float | None:
    vmid = 0.5 * vdd
    vmin_swing = 0.2 * vdd
    n = len(t)

    if edge is None:
        for k in range(start_k, n):
            if t[k] < t_in:
                continue
            if t[k] > t_in + max_window_s:
                break
            swing = abs(v_out[k] - v_ref)
            if swing < vmin_swing:
                continue
            target = v_ref + 0.5 * swing * (1.0 if v_out[k] > v_ref else -1.0)
            for j in range(max(start_k, k - 1), k + 1):
                if j < 1:
                    continue
                v0o, v1o = v_out[j - 1], v_out[j]
                crossed = (v0o - target) * (v1o - target) <= 0 and v1o != v0o
                if crossed or abs(v1o - target) < 0.02 * vdd:
                    t_resp = _interp_threshold_crossing(t[j - 1], t[j], v0o, v1o, target)
                    return t_resp - t_in
            return t[k] - t_in
        return None

    for k in range(start_k, n):
        if t[k] < t_in:
            continue
        if t[k] > t_in + max_window_s:
            break
        v0o, v1o = v_out[k - 1], v_out[k]
        if edge == "rise" and v0o < vmid <= v1o:
            if abs(v1o - v_ref) >= vmin_swing:
                t_out = _interp_threshold_crossing(t[k - 1], t[k], v0o, v1o, vmid)
                return t_out - t_in
        if edge == "fall" and v0o > vmid >= v1o:
            if abs(v1o - v_ref) >= vmin_swing:
                t_out = _interp_threshold_crossing(t[k - 1], t[k], v0o, v1o, vmid)
                return t_out - t_in
    return None


def compute_gate_propagation_delay(
    t: list[float],
    v_in: list[float],
    v_out: list[float],
    vdd: float,
    *,
    inverting: bool | None = None,
    max_window_s: float = 30e-9,
) -> float | None:
    """Average input→output propagation delay (s) from transient waveforms."""
    n = min(len(t), len(v_in), len(v_out))
    if n < 2 or vdd <= 0:
        return None
    vmid = 0.5 * vdd
    delays: list[float] = []

    for k in range(1, n):
        t0, t1 = t[k - 1], t[k]
        vin0, vin1 = v_in[k - 1], v_in[k]

        if vin0 < vmid <= vin1:
            t_in = _interp_threshold_crossing(t0, t1, vin0, vin1, vmid)
            v_ref = _vout_at_time(t0, t1, v_out[k - 1], v_out[k], t_in)
            out_edge: Literal["rise", "fall"] | None
            if inverting is True:
                out_edge = "fall"
            elif inverting is False:
                out_edge = "rise"
            else:
                out_edge = None
            d = _find_output_edge_delay(
                t, v_out, t_in=t_in, v_ref=v_ref, vdd=vdd, edge=out_edge, start_k=k, max_window_s=max_window_s
            )
            if d is not None and 0 < d < max_window_s:
                delays.append(d)

        if vin0 > vmid >= vin1:
            t_in = _interp_threshold_crossing(t0, t1, vin0, vin1, vmid)
            v_ref = _vout_at_time(t0, t1, v_out[k - 1], v_out[k], t_in)
            if inverting is True:
                out_edge = "rise"
            elif inverting is False:
                out_edge = "fall"
            else:
                out_edge = None
            d = _find_output_edge_delay(
                t, v_out, t_in=t_in, v_ref=v_ref, vdd=vdd, edge=out_edge, start_k=k, max_window_s=max_window_s
            )
            if d is not None and 0 < d < max_window_s:
                delays.append(d)

    if not delays:
        return None
    return sum(delays) / len(delays)


def _waveform_columns(wf: dict[str, Any] | None) -> dict[str, list[float]]:
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


def resolve_gate_propagation_delay(gate_sim: dict[str, Any], gate: str, vdd: float) -> float | None:
    """Propagation delay from ngspice input→output .measure, with waveform fallback."""
    m = gate_sim.get("measures") or {}
    primary = [float(m[k]) for k in ("td_plh", "td_phl") if m.get(k) is not None and m[k] > 0]
    if primary:
        return sum(primary) / len(primary)

    alt = [float(m[k]) for k in ("td_rise", "td_fall", "td_inv_r", "td_inv_f") if m.get(k) is not None and m[k] > 0]
    if alt:
        return sum(alt) / len(alt)

    delay_in, delay_out, inv = gate_delay_io_spec(gate)
    cols = _waveform_columns(gate_sim.get("waveform"))
    t = cols.get("time_s", [])
    v_in = cols.get(delay_in, [])
    v_out = cols.get(delay_out, [])
    if t and v_in and v_out:
        d = compute_gate_propagation_delay(t, v_in, v_out, vdd, inverting=inv)
        if d is not None:
            return d

    legacy = [abs(float(m[k])) for k in ("trise", "tfall") if m.get(k) is not None and abs(m[k]) > 0]
    return sum(legacy) / len(legacy) if legacy else None


def gate_timing_from_ngspice_measures(
    measures: dict[str, Any] | None,
    *,
    gate: str | None = None,
    gate_sim: dict[str, Any] | None = None,
    vdd: float = 1.0,
) -> dict[str, float | None]:
    """Unified tPLH/tPHL/propagation delay from gate transient .measure (seconds → ns)."""
    m = measures or {}
    rise_s = m.get("td_plh")
    if rise_s is None:
        rise_s = m.get("td_rise")
    if rise_s is None:
        rise_s = m.get("trise")
    if rise_s is None:
        rise_s = m.get("rise")
    if rise_s is None:
        rise_s = m.get("td_inv_r")

    fall_s = m.get("td_phl")
    if fall_s is None:
        fall_s = m.get("td_fall")
    if fall_s is None:
        fall_s = m.get("tfall")
    if fall_s is None:
        fall_s = m.get("fall")
    if fall_s is None:
        fall_s = m.get("td_inv_f")

    def _pos(v: Any) -> float | None:
        if v is None:
            return None
        try:
            x = abs(float(v))
        except (TypeError, ValueError):
            return None
        return x if x > 0 else None

    rise_s = _pos(rise_s)
    fall_s = _pos(fall_s)

    prop_s: float | None = None
    if rise_s is not None and fall_s is not None:
        prop_s = (rise_s + fall_s) / 2.0
    elif rise_s is not None:
        prop_s = rise_s
    elif fall_s is not None:
        prop_s = fall_s
    elif gate and gate_sim:
        prop_s = resolve_gate_propagation_delay(gate_sim, gate, vdd)

    def _ns(sec: float | None) -> float | None:
        return sec * 1e9 if sec is not None else None

    return {
        "t_plh_ns": _ns(rise_s),
        "t_phl_ns": _ns(fall_s),
        "propagation_delay_ns": _ns(prop_s),
    }


def _switching_activity_eval(
    input_pattern: list[tuple[int, ...]],
    eval_out: Callable[[tuple[int, ...]], tuple[int, ...]],
    out_width: int,
) -> dict[str, Any]:
    """Count output toggles between consecutive input vectors in the stimulus order."""
    prev: tuple[int, ...] | None = None
    toggles = {k: 0 for k in _TOGGLE_KEYS}
    trans = 0
    for bits in input_pattern:
        out = eval_out(bits)[:out_width]
        if prev is not None:
            trans += 1
            for i in range(out_width):
                if out[i] != prev[i]:
                    toggles[_TOGGLE_KEYS[i]] += 1
        prev = out
    max_edges = max(trans, 1)
    bit_keys = _TOGGLE_KEYS[:out_width]
    activity_mean = sum(toggles[k] for k in bit_keys) / (max_edges * out_width)
    return {
        "output_toggles": toggles,
        "input_transitions": trans,
        "mean_output_switching_activity": round(activity_mean, 4),
        "note": "Toggle counts follow the simulator stimulus order (full input-space walk).",
    }


def _switching_activity(gate: GateId, input_pattern: list[tuple[int, ...]]) -> dict[str, Any]:
    w = _gate_width(gate)

    def eval_out(bits: tuple[int, ...]) -> tuple[int, ...]:
        a = bits[0]
        b = bits[1] if len(bits) > 1 else 0
        c = bits[2] if len(bits) > 2 else 0
        return _eval_gate_outputs(gate, a, b, c)

    return _switching_activity_eval(input_pattern, eval_out, w)


def _models_and_header(vdd: float) -> str:
    return f""".title Reversible gate ({vdd} V)
.model nch nmos level=1 vto=0.4 kp=120e-6 gamma=0.3 lambda=0.05
.model pch pmos level=1 vto=-0.4 kp=40e-6 gamma=0.3 lambda=0.05
Vsupply vdd 0 DC {vdd}
"""


def _subckt_inv() -> str:
    return """
.subckt inv a y vdd vss
Mn y a vss vss nch W=2.4u L=0.18u
Mp y a vdd vdd pch W=4.8u L=0.18u
.ends

"""


def _subckt_nand2() -> str:
    return """
.subckt nand2 a b y vdd vss
Mn1 y a nmid vss nch W=4.8u L=0.18u
Mn2 nmid b vss vss nch W=4.8u L=0.18u
Mp1 y a vdd vdd pch W=4.8u L=0.18u
Mp2 y b vdd vdd pch W=4.8u L=0.18u
.ends

"""


def _subckt_buf2() -> str:
    return """
.subckt buf2 a y vdd vss
xi1 a n1 vdd vss inv
xi2 n1 y vdd vss inv
.ends

"""


def _subckt_xor2_cmos() -> str:
    return (
        _subckt_nand2()
        + """
.subckt xor2 a b y vdd vss
xn1 a b p1 vdd vss nand2
xn2 a p1 p2 vdd vss nand2
xn3 b p1 p3 vdd vss nand2
xn4 p2 p3 y vdd vss nand2
.ends

"""
    )


def _subckt_tg_pass() -> str:
    return """
.subckt tg_pass in out en enb vdd vss
Mn in en out vss nch W=3u L=0.18u
Mp in enb out vdd pch W=6u L=0.18u
.ends

.subckt xor2_pt a b y vdd vss
xinv_b b bn vdd vss inv
xinv_a a an vdd vss inv
xtg1 a nxt bn b vdd vss tg_pass
xtg2 an nxt b bn vdd vss tg_pass
xbuf nxt y vdd vss buf2
.ends

.subckt mux2_pt a ab x y out vdd vss
xtgx x nout a ab vdd vss tg_pass
xtgy y nout ab a vdd vss tg_pass
xbuf nout out vdd vss buf2
.ends

"""


def _subckt_nmos_ptl() -> str:
    """NMOS-only pass paths + restoring buffers (contrasts with full CMOS tg_pass pairs)."""
    return """
.subckt xor2_nmos_ptl a b y vdd vss
xinv_b b bn vdd vss inv
xinv_a a an vdd vss inv
Mn_a nx bn a vss nch W=3u L=0.18u
Mn_b nx b an vss nch W=3u L=0.18u
xbuf nx y vdd vss buf2
.ends

.subckt mux2_nmos_ptl sel selb i0 i1 out vdd vss
Mn0 nout selb i0 vss nch W=3u L=0.18u
Mn1 nout sel i1 vss nch W=3u L=0.18u
xbuf nout out vdd vss buf2
.ends

"""


def _step1_design(gate: GateId, realization: Realization) -> dict[str, Any]:
    rt = realization.replace("_", " ")
    if gate == "not":
        desc = (
            "1×1 unitary reversible gate (classical Pauli-X / NOT): single line A with output P = ¬A. "
            "Same cardinality as identity, so it is a valid reversible map on one bit."
        )
        eq = ["P = ¬A"]
    elif gate == "feynman":
        desc = (
            "Feynman (CNOT) gate on lines A,B: P=A, Q=A⊕B. "
            "Realization: buffer on A; XOR on second line."
        )
        eq = ["P = A", "Q = A ⊕ B"]
    elif gate == "toffoli":
        desc = (
            "Toffoli (CCNOT): P=A, Q=B, R=C⊕(A·B). "
            "Realization: preserve A,B; AND(A,B) XOR'd with C."
        )
        eq = ["P = A", "Q = B", "R = C ⊕ (A · B)"]
    elif gate == "fredkin":
        desc = (
            "Fredkin (controlled swap): P=A; if A=1 swap B and C. "
            "Q = (¬A·B)∨(A·C), R = (¬A·C)∨(A·B)."
        )
        eq = ["P = A", "Q = (¬A ∧ B) ∨ (A ∧ C)", "R = (¬A ∧ C) ∨ (A ∧ B)"]
    elif gate == "mux":
        desc = (
            "MUX-class 3×3 reversible gate: P=A, Q=A⊕B⊕C, "
            "R=(¬A∧C)⊕(A∧B)."
        )
        eq = ["P = A", "Q = A ⊕ B ⊕ C", "R = (¬A ∧ C) ⊕ (A ∧ B)"]
    elif gate == "umg":
        desc = (
            "Universal Multiplexer Gate (UMG): P=A, Q=B⊕C, "
            "R=(¬A∧C)⊕(A∧B)."
        )
        eq = ["P = A", "Q = B ⊕ C", "R = (¬A ∧ C) ⊕ (A ∧ B)"]
    elif gate == "ung":
        desc = (
            "Universal NOR Gate (UNG): P=A, Q=B, "
            "R=(A∨B)⊕C."
        )
        eq = ["P = A", "Q = B", "R = (A ∨ B) ⊕ C"]
    elif gate == "nmg":
        desc = (
            "NMG gate: P=A⊕B, Q=(B∧¬C)⊕(A∧C), "
            "R=(¬B∧C)⊕(A∧¬C)."
        )
        eq = [
            "P = A ⊕ B",
            "Q = (B ∧ ¬C) ⊕ (A ∧ C)",
            "R = (¬B ∧ C) ⊕ (A ∧ ¬C)",
        ]
    else:  # peres
        desc = (
            "Peres gate: P=A, Q=A⊕B, R=C⊕(A·B). "
            "Differs from Toffoli only because Q is mixed on the B line."
        )
        eq = ["P = A", "Q = A ⊕ B", "R = C ⊕ (A · B)"]

    rows = []
    w = _gate_width(gate)
    for k in range(1 << w):
        bits = tuple((k >> i) & 1 for i in range(w))
        a, b, c = bits[0], bits[1] if w > 1 else 0, bits[2] if w > 2 else 0
        p, q, r = _eval_gate_outputs(gate, a, b, c)
        if w == 1:
            rows.append(f"{bits[0]} → {p}")
        elif w == 2:
            rows.append(f"{bits[0]}{bits[1]} → {p}{q}")
        else:
            rows.append(f"{bits[0]}{bits[1]}{bits[2]} → {p}{q}{r}")

    ins_lit, outs_lit = _truth_table_literal_headers(w)
    return {
        "title": "Step 1 — Boolean specification and realization",
        "gate": gate,
        "style": rt,
        "description": desc,
        "equations": eq,
        "truth_table_input_literals": ins_lit,
        "truth_table_output_literals": outs_lit,
        "truth_table_rows": rows,
        "static_cmos_notes": "Built from static CMOS NAND2 / INV subcircuits; XOR is four NANDs.",
        "pass_transistor_notes": (
            "Pass-transistor logic (PTL): NMOS pass networks on XOR/MUX datapaths with restoring buffers; "
            "control and precharge-style paths still use static CMOS inverters / NAND where needed."
        ),
        "transmission_gate_logic_notes": (
            "Transmission gate logic (TGL): complementary NMOS+PMOS pairs (tg_pass) on XOR/MUX datapaths "
            "with restoring buffers; ancillary logic uses static CMOS NAND/INV for robust levels."
        ),
    }


def _circuit_not(realization: Realization) -> tuple[str, str, str]:
    """Single static CMOS inverter (both realizations use the same restoring INV for robustness)."""
    _ = realization
    probe = "vp"
    sub = _subckt_inv()
    body = """
xinv va vp vdd 0 inv
"""
    return sub, body, probe


def _circuit_feynman(realization: Realization) -> tuple[str, str, str]:
    """Returns (subckt_defs, main_body, delay_probe_node)."""
    probe = "vq"
    if realization == "static_cmos":
        sub = _subckt_inv() + _subckt_nand2() + _subckt_xor2_cmos() + _subckt_buf2()
        body = """
xvp va vp vdd 0 buf2
xxq va vb vq vdd 0 xor2
"""
    elif realization == "transmission_gate_logic":
        sub = _subckt_inv() + _subckt_nand2() + _subckt_buf2() + _subckt_tg_pass()
        body = """
xtgp va vp vdd 0 vdd 0 tg_pass
xinv_nb vb vnb vdd 0 inv
xxq va vb vq vdd 0 xor2_pt
"""
    else:
        sub = _subckt_inv() + _subckt_buf2() + _subckt_nmos_ptl()
        body = """
xvp va vp vdd 0 buf2
xxq va vb vq vdd 0 xor2_nmos_ptl
"""

    return sub, body, probe


def _circuit_toffoli(realization: Realization) -> tuple[str, str, str]:
    probe = "vr"
    base = _subckt_inv() + _subckt_nand2() + _subckt_buf2()
    if realization == "static_cmos":
        sub = base + _subckt_xor2_cmos()
        body = """
xvp va vp vdd 0 buf2
xvq vb vq vdd 0 buf2
xnab va vb nab vdd 0 nand2
xinv_ab nab vab vdd 0 inv
xxr vc vab vr vdd 0 xor2
"""
    elif realization == "transmission_gate_logic":
        sub = base + _subckt_tg_pass()
        body = """
xvp va vp vdd 0 buf2
xvq vb vq vdd 0 buf2
xnab va vb nab vdd 0 nand2
xinv_ab nab vab vdd 0 inv
xxr vc vab vr vdd 0 xor2_pt
"""
    else:
        sub = base + _subckt_nmos_ptl()
        body = """
xvp va vp vdd 0 buf2
xvq vb vq vdd 0 buf2
xnab va vb nab vdd 0 nand2
xinv_ab nab vab vdd 0 inv
xxr vc vab vr vdd 0 xor2_nmos_ptl
"""
    return sub, body, probe


def _circuit_peres(realization: Realization) -> tuple[str, str, str]:
    probe = "vr"
    base = _subckt_inv() + _subckt_nand2() + _subckt_buf2()
    if realization == "static_cmos":
        sub = base + _subckt_xor2_cmos()
        body = """
xvp va vp vdd 0 buf2
xxq va vb vq vdd 0 xor2
xnab va vb nab vdd 0 nand2
xinv_ab nab vab vdd 0 inv
xxr vc vab vr vdd 0 xor2
"""
    elif realization == "transmission_gate_logic":
        sub = base + _subckt_tg_pass()
        body = """
xvp va vp vdd 0 buf2
xxq va vb vq vdd 0 xor2_pt
xnab va vb nab vdd 0 nand2
xinv_ab nab vab vdd 0 inv
xxr vc vab vr vdd 0 xor2_pt
"""
    else:
        sub = base + _subckt_nmos_ptl()
        body = """
xvp va vp vdd 0 buf2
xxq va vb vq vdd 0 xor2_nmos_ptl
xnab va vb nab vdd 0 nand2
xinv_ab nab vab vdd 0 inv
xxr vc vab vr vdd 0 xor2_nmos_ptl
"""
    return sub, body, probe


def _circuit_fredkin(realization: Realization) -> tuple[str, str, str]:
    probe = "vq"
    base = _subckt_inv() + _subckt_nand2() + _subckt_buf2()
    if realization == "static_cmos":
        sub = base
        body = """
xvp va vp vdd 0 buf2
xinv_a va na vdd 0 inv
xn1 na vb t1n vdd 0 nand2
xinv1 t1n t1 vdd 0 inv
xn2 va vc t2n vdd 0 nand2
xinv2 t2n t2 vdd 0 inv
xinv_t1i t1 t1i vdd 0 inv
xinv_t2i t2 t2i vdd 0 inv
xnq t1i t2i vqn vdd 0 nand2
xinvq vqn vq vdd 0 inv
xn3 na vc t3n vdd 0 nand2
xinv3 t3n t3 vdd 0 inv
xn4 va vb t4n vdd 0 nand2
xinv4 t4n t4 vdd 0 inv
xinv_t3i t3 t3i vdd 0 inv
xinv_t4i t4 t4i vdd 0 inv
xnr t3i t4i vrn vdd 0 nand2
xinvr vrn vr vdd 0 inv
"""
    elif realization == "transmission_gate_logic":
        sub = base + _subckt_tg_pass()
        body = """
xvp va vp vdd 0 buf2
xinv_a va na vdd 0 inv
xmux_q va na vb vc vq vdd 0 mux2_pt
xmux_r va na vc vb vr vdd 0 mux2_pt
"""
    else:
        sub = _subckt_inv() + _subckt_buf2() + _subckt_nmos_ptl()
        body = """
xvp va vp vdd 0 buf2
xinv_a va na vdd 0 inv
xmux_q va na vb vc vq vdd 0 mux2_nmos_ptl
xmux_r va na vc vb vr vdd 0 mux2_nmos_ptl
"""
    return sub, body, probe


def _body_r_term_mux_umg(xor_cell: str) -> str:
    """Shared R=(¬A∧C)⊕(A∧B) datapath for MUX and UMG presets."""
    return f"""
xinv_a va na vdd 0 inv
xn_ac na vc acn vdd 0 nand2
xinv_ac acn ac vdd 0 inv
xn_ab va vb abn vdd 0 nand2
xinv_ab abn ab vdd 0 inv
xxr ac ab vr vdd 0 {xor_cell}
"""


def _circuit_mux(realization: Realization) -> tuple[str, str, str]:
    probe = "vr"
    base = _subckt_inv() + _subckt_nand2() + _subckt_buf2()
    if realization == "static_cmos":
        sub = base + _subckt_xor2_cmos()
        xor_cell = "xor2"
    elif realization == "transmission_gate_logic":
        sub = base + _subckt_tg_pass()
        xor_cell = "xor2_pt"
    else:
        sub = base + _subckt_nmos_ptl()
        xor_cell = "xor2_nmos_ptl"
    body = f"""
xvp va vp vdd 0 buf2
xxq1 va vb tq vdd 0 {xor_cell}
xxq2 tq vc vq vdd 0 {xor_cell}
""" + _body_r_term_mux_umg(xor_cell)
    return sub, body, probe


def _circuit_umg(realization: Realization) -> tuple[str, str, str]:
    probe = "vr"
    base = _subckt_inv() + _subckt_nand2() + _subckt_buf2()
    if realization == "static_cmos":
        sub = base + _subckt_xor2_cmos()
        xor_cell = "xor2"
    elif realization == "transmission_gate_logic":
        sub = base + _subckt_tg_pass()
        xor_cell = "xor2_pt"
    else:
        sub = base + _subckt_nmos_ptl()
        xor_cell = "xor2_nmos_ptl"
    body = f"""
xvp va vp vdd 0 buf2
xxq vb vc vq vdd 0 {xor_cell}
""" + _body_r_term_mux_umg(xor_cell)
    return sub, body, probe


def _circuit_ung(realization: Realization) -> tuple[str, str, str]:
    probe = "vr"
    base = _subckt_inv() + _subckt_nand2() + _subckt_buf2()
    if realization == "static_cmos":
        sub = base + _subckt_xor2_cmos()
        xor_cell = "xor2"
    elif realization == "transmission_gate_logic":
        sub = base + _subckt_tg_pass()
        xor_cell = "xor2_pt"
    else:
        sub = base + _subckt_nmos_ptl()
        xor_cell = "xor2_nmos_ptl"
    body = f"""
xvp va vp vdd 0 buf2
xvq vb vq vdd 0 buf2
xina va na vdd 0 inv
xinb vb nb vdd 0 inv
xn_or na nb orn vdd 0 nand2
xinv_or orn vor vdd 0 inv
xxr vc vor vr vdd 0 {xor_cell}
"""
    return sub, body, probe


def _circuit_nmg(realization: Realization) -> tuple[str, str, str]:
    """NMG: P=A⊕B, Q=(B∧¬C)⊕(A∧C), R=(¬B∧C)⊕(A∧¬C)."""
    probe = "vr"
    base = _subckt_inv() + _subckt_nand2() + _subckt_buf2()
    if realization == "static_cmos":
        sub = base + _subckt_xor2_cmos()
        xor_cell = "xor2"
    elif realization == "transmission_gate_logic":
        sub = base + _subckt_tg_pass()
        xor_cell = "xor2_pt"
    else:
        sub = base + _subckt_nmos_ptl()
        xor_cell = "xor2_nmos_ptl"
    body = f"""
xxp va vb vp vdd 0 {xor_cell}
xinv_b vb nb vdd 0 inv
xinv_c vc nc vdd 0 inv
xn_bnc vb nc bncn vdd 0 nand2
xinv_bnc bncn bnc vdd 0 inv
xn_ac va vc acn vdd 0 nand2
xinv_ac acn ac vdd 0 inv
xxq bnc ac vq vdd 0 {xor_cell}
xn_nbc nb vc nbcn vdd 0 nand2
xinv_nbc nbcn nbc vdd 0 inv
xn_anc va nc ancn vdd 0 nand2
xinv_anc ancn anc vdd 0 inv
xxr nbc anc vr vdd 0 {xor_cell}
"""
    return sub, body, probe


def _select_circuit(gate: GateId, realization: Realization) -> tuple[str, str, str]:
    if gate == "not":
        return _circuit_not(realization)
    if gate == "feynman":
        s, b, p = _circuit_feynman(realization)
        return s, b, p
    if gate == "toffoli":
        return _circuit_toffoli(realization)
    if gate == "peres":
        return _circuit_peres(realization)
    if gate == "mux":
        return _circuit_mux(realization)
    if gate == "umg":
        return _circuit_umg(realization)
    if gate == "ung":
        return _circuit_ung(realization)
    if gate == "nmg":
        return _circuit_nmg(realization)
    return _circuit_fredkin(realization)


def _build_stimulus_width(
    w: int, vdd: float, t_step_ns: float = 12.0, repeats: int = 2
) -> tuple[str, list[tuple[int, ...]]]:
    pattern: list[tuple[int, ...]] = []
    t = 0.0
    t_step = t_step_ns * 1e-9
    for _ in range(repeats):
        for k in range(1 << w):
            bits = tuple((k >> i) & 1 for i in range(w))
            pattern.append(bits)
            t += t_step
    quiet = 6 * t_step
    t_end = t + quiet

    def pwl_for_bit(bit_idx: int) -> str:
        pts: list[str] = []
        for j, bvec in enumerate(pattern):
            val = vdd * float(bvec[bit_idx])
            time_j = j * t_step
            pts.append(f"{time_j} {val}")
        last_v = vdd * float(pattern[-1][bit_idx])
        pts.append(f"{t_end} {last_v}")
        return " ".join(pts)

    va = pwl_for_bit(0)
    if w == 1:
        stim = f"""
Va va 0 PWL( {va} )
"""
    elif w == 2:
        vb = pwl_for_bit(1)
        stim = f"""
Va va 0 PWL( {va} )
Vb vb 0 PWL( {vb} )
Vc vc 0 DC 0
"""
    elif w == 3:
        vb = pwl_for_bit(1)
        vc = pwl_for_bit(2)
        stim = f"""
Va va 0 PWL( {va} )
Vb vb 0 PWL( {vb} )
Vc vc 0 PWL( {vc} )
"""
    else:
        vb = pwl_for_bit(1)
        vc = pwl_for_bit(2)
        vd = pwl_for_bit(3)
        stim = f"""
Va va 0 PWL( {va} )
Vb vb 0 PWL( {vb} )
Vc vc 0 PWL( {vc} )
Vd vd 0 PWL( {vd} )
"""
    return stim, pattern


def _footer(
    tran_stop: float,
    probe: str,
    vdd: float,
    *,
    output_nodes: tuple[str, ...],
    power_mode: Literal["vdd_supply", "behavioral_outputs"],
    delay_input: str | None = None,
    delay_inverting: bool | None = None,
) -> str:
    vlo = 0.1 * vdd
    vhi = 0.9 * vdd
    t_meas_hi = max(tran_stop - 2e-9, 20e-9)
    t_static_lo = max(tran_stop - 8e-9, 10e-9)
    caps = "".join(f"{_CAP_ELEMENT[i]} {n} 0 25f\n" for i, n in enumerate(output_nodes))
    if power_mode == "vdd_supply":
        pexpr = "v(vdd)*abs(i(vsupply))"
    else:
        terms = [f"abs(v({n})*i(b{n}))" for n in output_nodes]
        pexpr = "+".join(terms)
    if delay_input:
        if delay_inverting is True:
            delay_meas = f"""
.measure tran td_plh TRIG v({delay_input}) VAL={vlo} RISE=1 TARG v({probe}) VAL={vhi} FALL=1
.measure tran td_phl TRIG v({delay_input}) VAL={vhi} FALL=1 TARG v({probe}) VAL={vlo} RISE=1
"""
        elif delay_inverting is False:
            delay_meas = f"""
.measure tran td_plh TRIG v({delay_input}) VAL={vlo} RISE=1 TARG v({probe}) VAL={vhi} RISE=1
.measure tran td_phl TRIG v({delay_input}) VAL={vhi} FALL=1 TARG v({probe}) VAL={vlo} FALL=1
"""
        else:
            delay_meas = f"""
.measure tran td_rise TRIG v({delay_input}) VAL={vlo} RISE=1 TARG v({probe}) VAL={vhi} RISE=1
.measure tran td_fall TRIG v({delay_input}) VAL={vhi} FALL=1 TARG v({probe}) VAL={vlo} FALL=1
.measure tran td_inv_r TRIG v({delay_input}) VAL={vlo} RISE=1 TARG v({probe}) VAL={vlo} FALL=1
.measure tran td_inv_f TRIG v({delay_input}) VAL={vhi} FALL=1 TARG v({probe}) VAL={vhi} RISE=1
"""
    else:
        delay_meas = f"""
.measure tran trise TRIG v({probe}) VAL={vlo} RISE=1 TARG v({probe}) VAL={vhi} RISE=1
.measure tran tfall TRIG v({probe}) VAL={vhi} FALL=1 TARG v({probe}) VAL={vlo} FALL=1
"""
    return f"""
{caps}
.tran 200p {tran_stop}
* Single-token names: some ngspice builds alter names with underscores.
.measure tran pavg AVG PAR('{pexpr}') FROM=5n TO={t_meas_hi}
.measure tran pstat AVG PAR('{pexpr}') FROM={t_static_lo} TO={tran_stop - 1e-9}
{delay_meas}
.end
"""


def _step1_design_custom(exprs: list[str], width: int, realization: Realization) -> dict[str, Any]:
    rt = realization.replace("_", " ")
    labels = list(CUSTOM_OUTPUT_LABELS[: len(exprs)])
    eq = [f"{labels[i]} = {exprs[i]}" for i in range(len(exprs))]
    nodes = [parse_expression(e, width) for e in exprs]
    rows = []
    for k in range(1 << width):
        bits = tuple((k >> i) & 1 for i in range(width))
        outs = eval_outputs_tuple(nodes, bits)
        instr = "".join(str(bits[i]) for i in range(width))
        outstr = "".join(str(outs[i]) for i in range(len(outs)))
        rows.append(f"{instr} → {outstr}")
    ins_lit, outs_lit = _truth_table_literal_headers(width)
    return {
        "title": "Step 1 — Boolean specification (custom reversible gate)",
        "gate": "custom",
        "style": rt,
        "description": (
            "User-defined reversible gate: each line is P (1×1), then Q, R, S for wider gates. "
            "Inputs: A only (1-line), A–B (2-line), A–C (3-line), or A–D (4-line). "
            "Operators: & AND, | OR, ^ XOR, ~ or ! NOT; parentheses allowed. "
            "The mapping must be a bijection (valid permutation)."
        ),
        "equations": eq,
        "expression_syntax": (
            "1×1 NOT example: single line ~A or !A. Variables A[,B[,C[,D]]]; operators & | ^ ~ !; "
            "3-line Toffoli-style: A, B, C^(A&B); 4 lines use P–S for outputs."
        ),
        "truth_table_input_literals": ins_lit,
        "truth_table_output_literals": outs_lit,
        "truth_table_rows": rows,
        "static_cmos_notes": (
            "Custom gates are simulated with ideal behavioral sources (B…), not synthesized CMOS. "
            "Use built-in presets for transistor-level static CMOS or pass-transistor netlists."
        ),
        "pass_transistor_notes": (
            "Custom gates use the same behavioral deck as static_cmos for simulation; "
            "pass_transistor and transmission_gate_logic transistor styles apply only to presets."
        ),
        "transmission_gate_logic_notes": (
            "Custom gates use the same behavioral deck as static_cmos for simulation; "
            "pass_transistor and transmission_gate_logic transistor styles apply only to presets."
        ),
    }


def build_netlist_custom(
    raw_expressions: list[str],
    realization: Realization,
    vdd: float,
) -> tuple[str, str, dict[str, Any], list[tuple[int, ...]]]:
    exprs = normalize_custom_expressions(raw_expressions)
    w = len(exprs)
    nodes = [parse_expression(e, w) for e in exprs]
    validate_reversible_permutation(nodes, w)
    out_nodes = ("vp", "vq", "vr", "vs")[:w]
    probe = out_nodes[-1]
    stim, pattern = _build_stimulus_width(w, vdd)
    body = build_custom_behavioral_body(nodes, vdd)
    t_step = 12e-9
    n_pat = (1 << w) * 2
    tran_stop = n_pat * t_step + 8 * t_step + 5e-9
    netlist = (
        _models_and_header(vdd)
        + stim
        + body
        + _footer(
            tran_stop,
            probe,
            vdd,
            output_nodes=out_nodes,
            power_mode="behavioral_outputs",
        )
    )
    step1 = _step1_design_custom(exprs, w, realization)
    step1["stimulus"] = {
        "input_order": "All input combinations visited twice (deterministic for power averaging).",
        "pattern_length": len(pattern),
    }
    return netlist, probe, step1, pattern


def _build_named_behavioral_netlist(
    gate_key: str,
    realization: Realization,
    vdd: float,
) -> tuple[str, str, dict[str, Any], list[tuple[int, ...]]]:
    """Behavioral B-source deck for preset gates without structural transistor decomposition."""
    exprs_tuple = _NAMED_BEHAVIORAL_EXPRS_3[gate_key]
    exprs = list(exprs_tuple)
    w = len(exprs)
    nodes = [parse_expression(e, w) for e in exprs]
    validate_reversible_permutation(nodes, w)
    out_nodes = ("vp", "vq", "vr", "vs")[:w]
    probe = out_nodes[-1]
    stim, pattern = _build_stimulus_width(w, vdd)
    body = build_custom_behavioral_body(nodes, vdd)
    t_step = 12e-9
    n_pat = (1 << w) * 2
    tran_stop = n_pat * t_step + 8 * t_step + 5e-9
    netlist = (
        _models_and_header(vdd)
        + stim
        + body
        + _footer(
            tran_stop,
            probe,
            vdd,
            output_nodes=out_nodes,
            power_mode="behavioral_outputs",
        )
    )
    step1 = _step1_design_custom(exprs, w, realization)
    step1 = _overlay_named_behavioral_step1(gate_key, step1, exprs_tuple)
    step1["stimulus"] = {
        "input_order": "All input combinations visited twice (deterministic for power averaging).",
        "pattern_length": len(pattern),
    }
    return netlist, probe, step1, pattern


def build_netlist(
    gate: GateId, realization: Realization, vdd: float = 1.8
) -> tuple[str, str, dict[str, Any], list[tuple[int, ...]]]:
    """Full SPICE deck, probe node, step-1 design dict, stimulus pattern."""
    if gate in _BEHAVIORAL_ONLY_GATES:
        return _build_named_behavioral_netlist(gate, realization, vdd)
    sub, body, probe = _select_circuit(gate, realization)
    stim, pattern = _build_stimulus_width(_gate_width(gate), vdd)
    t_step = 12e-9
    w = _gate_width(gate)
    n_pat = (1 << w) * 2
    tran_stop = n_pat * t_step + 8 * t_step + 5e-9

    out_nodes = ("vp", "vq", "vr")[:w]
    delay_in, _delay_out, delay_inv = gate_delay_io_spec(gate)
    netlist = (
        _models_and_header(vdd)
        + sub
        + stim
        + body
        + _footer(
            tran_stop,
            probe,
            vdd,
            output_nodes=out_nodes,
            power_mode="vdd_supply",
            delay_input=delay_in,
            delay_inverting=delay_inv,
        )
    )
    step1 = _step1_design(gate, realization)
    step1["stimulus"] = {
        "input_order": "All input combinations visited twice (deterministic for power averaging).",
        "pattern_length": len(pattern),
    }
    return netlist, probe, step1, pattern


def _parse_float_token(tok: str) -> float | None:
    t = tok.strip().replace(",", ".").strip()
    # Fortran-style exponent (e.g. 1.23D-4) from some SPICE builds
    t = re.sub(r"(?<=[0-9])[dD]", "e", t)
    if t.lower() in ("failed", "nan", "inf", "-inf", "+inf"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _alias_measures(d: dict[str, float]) -> dict[str, float]:
    """Unify alternate names ngspice or parsers may emit."""
    out = dict(d)
    if "p_avg" not in out and "pavg" in out:
        out["p_avg"] = out["pavg"]
    if "p_avg" not in out and "p-avg" in out:
        out["p_avg"] = out["p-avg"]
    if "p_static" not in out and "pstat" in out:
        out["p_static"] = out["pstat"]
    if "p_static" not in out and "pstatic" in out:
        out["p_static"] = out["pstatic"]
    if "trise" not in out and "rise" in out:
        out["trise"] = out["rise"]
    if "tfall" not in out and "fall" in out:
        out["tfall"] = out["fall"]
    return out


def _strip_trailing_end_card(netlist: str) -> str:
    """Remove the final SPICE `.end` card so we can append a `.control` section."""
    lines = netlist.rstrip().splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip().lower() == ".end":
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines) + "\n"


def _inject_wrdata_control(
    netlist: str,
    wave_base_abs: str,
    spice_nodes: tuple[str, ...] | None = None,
    *,
    spice_exprs: tuple[str, ...] | None = None,
) -> str:
    """
    ngspice writes wrdata to ``{wave_base_abs}.data`` (it appends ``.data`` to the given path).
    Requires a `.control` `run` so transient vectors exist for `wrdata`.
    """
    body = _strip_trailing_end_card(netlist)
    if spice_exprs:
        v_exprs = " ".join(spice_exprs)
    elif spice_nodes:
        v_exprs = " ".join(f"v({n})" for n in spice_nodes)
    else:
        raise ValueError("spice_nodes or spice_exprs required")
    ctl = f"""
.control
run
wrdata {wave_base_abs} {v_exprs}
quit
.endc
.end
"""
    return body.rstrip() + "\n" + ctl.lstrip("\n")


def _downsample_wave_rows(rows: list[list[float]], max_rows: int) -> list[list[float]]:
    n = len(rows)
    if n <= max_rows:
        return rows
    return [rows[int(round(i * (n - 1) / (max_rows - 1)))] for i in range(max_rows)]


def _parse_wrdata_data(
    path: Path,
    node_names: tuple[str, ...],
    *,
    max_rows: int = 2000,
) -> dict[str, Any] | None:
    """
    ngspice ``wrdata`` uses one (time, value) pair per plotted expression concatenated on each line
    (2 columns for a single ``v(...)``, 4 for two probes, etc.).
    """
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    rows: list[list[float]] = []
    n_nodes = len(node_names)
    expected = 2 * n_nodes
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            raw = [float(x) for x in parts]
        except ValueError:
            continue
        if len(raw) != expected:
            if not rows:
                logger.warning(
                    "wrdata row width %s differs from expected %s (2 per probe); skipping malformed lines",
                    len(raw),
                    expected,
                )
            continue
        t0 = raw[0]
        vals = [raw[2 * i + 1] for i in range(n_nodes)]
        rows.append([t0, *vals])
    if not rows:
        return None
    cols = ["time_s", *node_names]
    ds = _downsample_wave_rows(rows, max_rows)
    return {
        "columns": cols,
        "rows": ds,
        "sample_count": len(ds),
        "source_file_suffix": ".data",
    }


def _parse_measures(log_text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for m in _MEASURE_RE.finditer(log_text):
        name, tok = m.group(1).lower(), m.group(2)
        v = _parse_float_token(tok)
        if v is not None:
            out[name] = v
    for m in _LOOSE_MEASURE_RE.finditer(log_text):
        name, tok = m.group(1).lower(), m.group(2)
        if name in out:
            continue
        v = _parse_float_token(tok)
        if v is not None:
            out[name] = v
    return _alias_measures(out)


def run_ngspice_netlist(
    netlist: str,
    *,
    label: str,
    waveform_nodes: tuple[str, ...] | None = None,
    waveform_exprs: tuple[str, ...] | None = None,
    waveform_columns: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Write netlist, invoke ngspice -b, return stdout + log path + measures + exit code + optional waveform."""
    ngspice = resolve_ngspice_executable()
    if not ngspice:
        return {
            "ok": False,
            "exit_code": None,
            "error": (
                "ngspice executable not found under EDA_ROOT. Install ngspice under Data/eda "
                "(bin/ngspice or ngspice build tree), or set EDA_NGSPICE to a path under EDA_ROOT."
            ),
            "measures": {},
        }

    with tempfile.TemporaryDirectory(prefix="mit_eda_ng_") as tmp:
        cir = Path(tmp) / "reversible.cir"
        logf = Path(tmp) / "reversible.log"
        deck = netlist
        wave_base: str | None = None
        col_names: tuple[str, ...] | None = None
        if waveform_exprs or waveform_nodes:
            wave_base = str((Path(tmp) / "wave_export").resolve())
            deck = _inject_wrdata_control(
                netlist,
                wave_base,
                waveform_nodes,
                spice_exprs=waveform_exprs,
            )
            if waveform_columns:
                col_names = waveform_columns
            elif waveform_nodes:
                col_names = waveform_nodes
            elif waveform_exprs:
                col_names = tuple(f"probe_{i}" for i in range(len(waveform_exprs)))
        cir.write_text(deck, encoding="utf-8")
        cmd = [ngspice, "-b", str(cir), "-o", str(logf)]
        t0 = __import__("time").perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            record_ngspice_event(
                status="timeout",
                command=" ".join(cmd),
                duration_ms=120_000,
                detail="reversible gate batch",
            )
            return {"ok": False, "error": "ngspice timed out", "measures": {}}
        elapsed_ms = int((__import__("time").perf_counter() - t0) * 1000)

        log_text = ""
        if logf.is_file():
            log_text = logf.read_text(encoding="utf-8", errors="replace")
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        # Prefer log file; some installs echo measurements only to stdout (or vice versa).
        combined = "\n".join(
            part for part in (log_text, stdout, stderr) if (part or "").strip()
        )
        if not combined.strip():
            combined = (stdout or "") + "\n" + (stderr or "")
        measures = _parse_measures(combined)
        ok = proc.returncode == 0

        wf: dict[str, Any] | None = None
        if col_names and wave_base:
            wf_path = Path(f"{wave_base}.data")
            if wf_path.is_file():
                wf = _parse_wrdata_data(wf_path, col_names)
            elif ok:
                logger.warning("ngspice wrdata output missing at %s", wf_path)

        record_ngspice_event(
            status="ok" if ok else "error",
            command=" ".join(cmd),
            duration_ms=elapsed_ms,
            detail=label[:500],
        )
        out: dict[str, Any] = {
            "ok": ok,
            "exit_code": proc.returncode,
            "ngspice_executable": ngspice,
            "log": log_text[-12000:] if len(log_text) > 12000 else log_text,
            "stdout_tail": stdout[-4000:] if len(stdout) > 4000 else stdout,
            "stderr_tail": stderr[-2000:] if len(stderr) > 2000 else stderr,
            "measures": measures,
        }
        if wf is not None:
            out["waveform"] = wf
        return out


def analyze_reversible_gate(
    gate: str,
    realization: Realization,
    vdd: float = 1.8,
    *,
    custom_expressions: list[str] | None = None,
) -> dict[str, Any]:
    g = gate.lower().strip()
    behavioral_power_gate = False
    wf_nodes: tuple[str, ...] = ()

    def _wf_nodes(width: int) -> tuple[str, ...]:
        ins = ("va", "vb", "vc", "vd")[:width]
        outs = ("vp", "vq", "vr", "vs")[:width]
        return ins + outs

    if g == "custom":
        if not custom_expressions:
            raise CustomExprError("Field custom_expressions is required when gate is 'custom' (non-empty strings).")
        netlist, probe, step1, pattern = build_netlist_custom(custom_expressions, realization, vdd)
        exprs = normalize_custom_expressions(custom_expressions)
        w = len(exprs)
        nodes = [parse_expression(e, w) for e in exprs]
        switching = _switching_activity_eval(
            pattern,
            lambda bits, _n=nodes: eval_outputs_tuple(_n, bits),
            len(exprs),
        )
        wf_nodes = _wf_nodes(len(exprs))
        sim = run_ngspice_netlist(
            netlist, label=f"reversible custom {realization}", waveform_nodes=wf_nodes
        )
        behavioral_power_gate = True
    elif g in _BEHAVIORAL_ONLY_GATES:
        netlist, probe, step1, pattern = build_netlist(g, realization, vdd=vdd)  # type: ignore[arg-type]
        switching = _switching_activity(g, pattern)  # type: ignore[arg-type]
        wf_nodes = _wf_nodes(_gate_width(g))  # type: ignore[arg-type]
        sim = run_ngspice_netlist(
            netlist, label=f"reversible {gate} {realization}", waveform_nodes=wf_nodes
        )
        behavioral_power_gate = True
    else:
        netlist, probe, step1, pattern = build_netlist(gate, realization, vdd=vdd)  # type: ignore[arg-type]
        switching = _switching_activity(gate, pattern)  # type: ignore[arg-type]
        wf_nodes = _wf_nodes(_gate_width(gate))  # type: ignore[arg-type]
        sim = run_ngspice_netlist(
            netlist, label=f"reversible {gate} {realization}", waveform_nodes=wf_nodes
        )

    m = sim.get("measures") or {}
    p_avg = m.get("p_avg") if m.get("p_avg") is not None else m.get("pavg")
    p_static = m.get("p_static") if m.get("p_static") is not None else m.get("pstat")
    p_dyn = None
    if p_avg is not None and p_static is not None:
        p_dyn = max(p_avg - p_static, 0.0)

    metrics_warning: str | None = None
    if sim.get("error"):
        metrics_warning = str(sim["error"])
    elif not m and sim.get("exit_code") not in (0, None):
        metrics_warning = "ngspice exited with a non-zero status; power/delay measures may be missing. See Step 3 log."
    elif not m:
        metrics_warning = (
            "No measurements were parsed from ngspice output. "
            "Ensure ngspice batch mode is available on the EDA API host and inspect Step 3 log."
        )
    elif p_avg is None and p_static is None:
        metrics_warning = "Power measures missing from parser output; check Step 3 log for failed .measure lines."

    _preset_power_notes = (
        "Average is time-averaged supply power over .tran (Vdd × |I(Vsupply)|). "
        "static_estimate uses the final steady window; dynamic_estimate ≈ average − static "
        "(short-circuit included in average)."
    )
    _custom_power_notes = (
        "Custom gates use behavioral voltage sources that do not draw DC current from Vdd, so supply current is ~0. "
        "Here average/static are the time average of Σ |v(out)·i(bout)| on each output (charging 25 fF loads), "
        "which matches switched-capacitor energy delivery from the behavioral drivers. "
        "dynamic_estimate ≈ average − static."
    )
    gate_for_timing = None if g == "custom" else g
    gt = gate_timing_from_ngspice_measures(
        m, gate=gate_for_timing, gate_sim=sim, vdd=vdd
    )
    delay_in, delay_out, delay_inv = gate_delay_io_spec(g) if g != "custom" else ("va", probe, None)
    tplh_ns = gt.get("t_plh_ns")
    tphl_ns = gt.get("t_phl_ns")

    def _s_from_ns(ns: float | None) -> float | None:
        return ns * 1e-9 if ns is not None else None

    def _ps_from_ns(ns: float | None) -> float | None:
        return ns * 1e3 if ns is not None else None

    step4 = {
        "power": {
            "average_w": p_avg,
            "static_estimate_w": p_static,
            "dynamic_estimate_w": p_dyn,
            "notes": _custom_power_notes if behavioral_power_gate else _preset_power_notes,
        },
        "delay_probe_node": probe,
        "delay": {
            "t_plh_ns": tplh_ns,
            "t_phl_ns": tphl_ns,
            "t_plh_s": _s_from_ns(tplh_ns),
            "t_phl_s": _s_from_ns(tphl_ns),
            "t_plh_ps": _ps_from_ns(tplh_ns),
            "t_phl_ps": _ps_from_ns(tphl_ns),
            "propagation_delay_ns": gt.get("propagation_delay_ns"),
            "delay_input_node": delay_in,
            "delay_output_node": delay_out,
            "delay_inverting": delay_inv,
            "rise_time_s": _s_from_ns(tplh_ns),
            "fall_time_s": _s_from_ns(tphl_ns),
            "notes": (
                "Input→output propagation delay (td_plh/td_phl or td_rise/td_fall/td_inv_* "
                f"on {delay_in}→{delay_out}); matches Cost-Metric tPLH/tPHL columns."
            ),
        },
        "switching_activity_detail": switching,
    }
    if metrics_warning:
        step4["metrics_warning"] = metrics_warning

    payload: dict[str, Any] = {
        "gate": g,
        "realization": realization,
        "vdd": vdd,
        "visualization": build_visualization_bundle(
            g,
            realization,
            step1,
            sim.get("waveform"),
            vdd,
        ),
        "steps": {
            "step_1_design": step1,
            "step_2_netlist": {
                "title": "Step 2 — SPICE netlist (ngspice)",
                "netlist": netlist,
            },
            "step_3_simulate": {
                "title": "Step 3 — Simulation",
                "command": "ngspice -b reversible.cir -o reversible.log",
                "ngspice_executable": sim.get("ngspice_executable"),
                "exit_code": sim.get("exit_code"),
                "ok": sim.get("ok"),
                "error": sim.get("error"),
                "log_excerpt": sim.get("log"),
                "stderr_excerpt": sim.get("stderr_tail"),
                "waveform": sim.get("waveform"),
                "waveform_probe_nodes": list(wf_nodes),
            },
            "step_4_extract": {
                "title": "Step 4 — Extracted metrics",
                **step4,
                "raw_measures": m,
            },
        },
    }
    if g == "custom":
        payload["custom_expressions"] = normalize_custom_expressions(custom_expressions or [])
    return payload


__all__ = ["analyze_reversible_gate", "build_netlist", "build_netlist_custom", "gate_timing_from_ngspice_measures", "run_ngspice_netlist", "CustomExprError"]
