"""Memristor crossbar switch subcircuits and reversible-gate transient netlists."""
from __future__ import annotations

from typing import Literal

from eda_hub.pages.post_cmos.cntfet_gate import POST_CMOS_GATE_TO_ID, normalize_cntfet_gate
from eda_hub.pages.post_cmos.memristor_models import GATE_LABEL, MemristorParams
from eda_hub.pages.cmos_ptl_tgl.reversible_ngspice import (
    _build_stimulus_width,
    _footer,
    _gate_width,
    _select_circuit,
    gate_delay_io_spec,
)

MemristorGateId = Literal["not", "feynman", "toffoli", "fredkin", "peres", "mux", "umg", "ung", "nmg"]


def normalize_memristor_gate(raw: str) -> MemristorGateId:
    gid = normalize_cntfet_gate(raw)
    return gid  # type: ignore[return-value]


def _memristor_device_params(params: MemristorParams, vdd: float) -> str:
    ron = max(params.ron, 1.0)
    roff = max(params.roff, ron * 10.0)
    vth = max(vdd * 0.45, 0.1)
    ion = vdd / ron
    ileak = vdd / roff
    cgate_ff = max(2.0 * (ron / 100.0), 0.5)
    return f"""
* Memristor switch parameters (Ron={ron} Ω, Roff={roff} Ω at Vdd={vdd} V)
.param Vdd={vdd} Ron={ron} Roff={roff} Vth={vth}
.param Ion={ion} Ileak={ileak} Cgate={cgate_ff}f
"""


def _memristor_subckt_inv() -> str:
    return """
.subckt inv a y vdd vss
Bnd y vss I = {u(v(a)-Vth)*Ion*tanh(2*v(y))+Ileak}
Bpd vdd y I = {u(Vth-v(a))*Ion*tanh(2*(Vdd-v(y)))+Ileak}
Cy y vss {Cgate}
.ends

"""


def _memristor_subckt_nand2() -> str:
    return """
.subckt nand2 a b y vdd vss
Bnd y vss I = {u(min(v(a),v(b))-Vth)*Ion*tanh(2*v(y))+Ileak}
Bpd vdd y I = {u(Vth-min(v(a),v(b)))*Ion*tanh(2*(Vdd-v(y)))+Ileak}
Cy y vss {Cgate}
.ends

"""


def _memristor_subckt_buf2() -> str:
    return """
.subckt buf2 a y vdd vss
xi1 a n1 vdd vss inv
xi2 n1 y vdd vss inv
.ends

"""


def _memristor_subckt_xor2() -> str:
    return """
.subckt xor2 a b y vdd vss
xn1 a b p1 vdd vss nand2
xn2 a p1 p2 vdd vss nand2
xn3 b p1 p3 vdd vss nand2
xn4 p2 p3 y vdd vss nand2
.ends

"""


def _memristor_subckt_library() -> str:
    return (
        _memristor_subckt_inv()
        + _memristor_subckt_nand2()
        + _memristor_subckt_buf2()
        + _memristor_subckt_xor2()
    )


def build_memristor_gate_transient_netlist(
    gate: str,
    params: MemristorParams,
    *,
    vdd: float,
) -> tuple[str, str]:
    """Build ngspice transient deck for the selected reversible gate using memristor switch subcircuits."""
    gid = normalize_memristor_gate(gate)

    _, body, probe = _select_circuit(gid, "static_cmos")  # type: ignore[arg-type]
    w = _gate_width(gid)  # type: ignore[arg-type]
    stim, _pattern = _build_stimulus_width(w, vdd)
    t_step = 12e-9
    n_pat = (1 << w) * 2
    tran_stop = n_pat * t_step + 8 * t_step + 5e-9
    out_nodes = ("vp", "vq", "vr")[:w]
    delay_in, _delay_out, delay_inv = gate_delay_io_spec(gid)
    header = (
        f".title memristor_gate_{gid}\n"
        f"{_memristor_device_params(params, vdd)}"
        f"{_memristor_subckt_library()}"
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
    gid = normalize_memristor_gate(gate)
    return GATE_LABEL.get(gid, gid)


__all__ = [
    "POST_CMOS_GATE_TO_ID",
    "build_memristor_gate_transient_netlist",
    "gate_display_name",
    "normalize_memristor_gate",
]
