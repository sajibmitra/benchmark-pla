"""CNTFET behavioral subcircuits and reversible-gate transient netlists."""
from __future__ import annotations

from typing import Any, Literal

from eda_hub.pages.post_cmos.cntfet_models import CntfetParams, _cntfet_device_params
from eda_hub.pages.cmos_ptl_tgl.reversible_ngspice import (
    _build_stimulus_width,
    _footer,
    _gate_width,
    _select_circuit,
    gate_delay_io_spec,
)

CntfetGateId = Literal["not", "feynman", "toffoli", "fredkin", "peres", "mux", "umg", "ung", "nmg"]

POST_CMOS_GATE_TO_ID: dict[str, CntfetGateId] = {
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
}

GATE_DISPLAY: dict[CntfetGateId, str] = {
    "not": "NOT (1×1)",
    "feynman": "Feynman (2×2)",
    "toffoli": "Toffoli (3×3)",
    "fredkin": "Fredkin (3×3)",
    "peres": "Peres (3×3)",
    "mux": "MUX (3×3)",
    "umg": "UMG (3×3)",
    "ung": "UNG (3×3)",
    "nmg": "NMG (3×3)",
}


def normalize_cntfet_gate(raw: str) -> CntfetGateId:
    key = raw.strip()
    mapped = POST_CMOS_GATE_TO_ID.get(key.lower())
    if mapped:
        return mapped
    upper = key.upper()
    ui_map = {
        "NOT": "not",
        "FG": "feynman",
        "TG": "toffoli",
        "FRG": "fredkin",
        "PG": "peres",
        "MUX": "mux",
        "UMG": "umg",
        "UNG": "ung",
        "NMG": "nmg",
    }
    if upper in ui_map:
        return ui_map[upper]  # type: ignore[return-value]
    return "not"


def _cntfet_subckt_inv() -> str:
    return """
.subckt inv a y vdd vss
Bnd y vss I = {u(v(a)-Vth)*ION*tanh(2*v(y))+IOFF}
Bpd vdd y I = {u(Vth-v(a))*ION*tanh(2*(Vdd-v(y)))+IOFF}
Cy y vss {Cgate}
.ends

"""


def _cntfet_subckt_nand2() -> str:
    return """
.subckt nand2 a b y vdd vss
Bnd y vss I = {u(min(v(a),v(b))-Vth)*ION*tanh(2*v(y))+IOFF}
Bpd vdd y I = {u(Vth-min(v(a),v(b)))*ION*tanh(2*(Vdd-v(y)))+IOFF}
Cy y vss {Cgate}
.ends

"""


def _cntfet_subckt_buf2() -> str:
    return """
.subckt buf2 a y vdd vss
xi1 a n1 vdd vss inv
xi2 n1 y vdd vss inv
.ends

"""


def _cntfet_subckt_xor2() -> str:
    return """
.subckt xor2 a b y vdd vss
xn1 a b p1 vdd vss nand2
xn2 a p1 p2 vdd vss nand2
xn3 b p1 p3 vdd vss nand2
xn4 p2 p3 y vdd vss nand2
.ends

"""


def _cntfet_subckt_library() -> str:
    return _cntfet_subckt_inv() + _cntfet_subckt_nand2() + _cntfet_subckt_buf2() + _cntfet_subckt_xor2()


def build_cntfet_gate_transient_netlist(gate: str, params: CntfetParams) -> tuple[str, str]:
    """Build ngspice transient deck for the selected reversible gate using CNTFET subcircuits."""
    gid = normalize_cntfet_gate(gate)
    vdd = params.vdd

    _, body, probe = _select_circuit(gid, "static_cmos")  # type: ignore[arg-type]
    w = _gate_width(gid)  # type: ignore[arg-type]
    stim, _pattern = _build_stimulus_width(w, vdd)
    t_step = 12e-9
    n_pat = (1 << w) * 2
    tran_stop = n_pat * t_step + 8 * t_step + 5e-9
    out_nodes = ("vp", "vq", "vr")[:w]
    delay_in, _delay_out, delay_inv = gate_delay_io_spec(gid)
    header = (
        f".title cntfet_gate_{gid}\n"
        f"{_cntfet_device_params(params)}"
        f"{_cntfet_subckt_library()}"
        f"Vsupply vdd 0 DC {{Vdd}}\n"
    )
    netlist = (
        header
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
    netlist = netlist.replace(
        ".tran 200p",
        ".option noopiter\n.tran 5p",
        1,
    )
    return netlist, probe


def gate_display_name(gate: str) -> str:
    gid = normalize_cntfet_gate(gate)
    return GATE_DISPLAY.get(gid, gid)


__all__ = [
    "GATE_DISPLAY",
    "POST_CMOS_GATE_TO_ID",
    "build_cntfet_gate_transient_netlist",
    "gate_display_name",
    "normalize_cntfet_gate",
]
