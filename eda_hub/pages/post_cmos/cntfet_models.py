"""CNTFET device parameters and behavioral ngspice decks (Stanford / BSIM-CMG citation)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

CitationId = Literal["stanford", "bsim_cmg"]

CITATIONS: dict[CitationId, dict[str, str]] = {
    "stanford": {
        "id": "stanford",
        "label": "Stanford CNTFET compact model",
        "authors": "Wong, Deng, and Stanford nano group",
        "reference": (
            "H.-S. P. Wong et al., carbon nanotube FET compact modeling for circuit simulation "
            "(Stanford RBT / PBRAM); ballistic and quasi-ballistic CNTFET I–V with diameter-dependent "
            "bandgap and contact effects."
        ),
        "url": "https://nano.stanford.edu/",
        "note": "This flow uses a calibrated behavioral inverter deck inspired by Stanford CNTFET parameters.",
    },
    "bsim_cmg": {
        "id": "bsim_cmg",
        "label": "BSIM-CMG (GAA / CNT extension)",
        "authors": "UC Berkeley Device Group",
        "reference": (
            "BSIM-CMG — common multi-gate MOSFET model (UC Berkeley); CNTFET decks often map "
            "nanotube diameter and channel length into BSIM-CMG geometry and capacitance tables."
        ),
        "url": "https://bsim.berkeley.edu/models/bsimcmg/",
        "note": "Full BSIM-CMG cards require compiled model libraries; ngspice here runs a behavioral proxy with your table parameters.",
    },
}


@dataclass(frozen=True)
class CntfetParams:
    lch_nm: float = 10.0
    dcnt_nm: float = 1.2
    eg_ev: float = 0.6
    vdd: float = 0.8
    ion_ua: float = 30.0
    ioff_a: float = 1e-9
    cgate_ff: float = 2.0

    @property
    def vth_v(self) -> float:
        """Schottky-barrier style threshold from bandgap (simplified)."""
        return max(0.15, self.eg_ev / 2.0)

    @property
    def ion_a(self) -> float:
        return self.ion_ua * 1e-6

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


DEFAULT_PARAMS = CntfetParams()

PARAM_METADATA: list[dict[str, str]] = [
    {"key": "lch_nm", "parameter": "Lch", "description": "Channel length", "example": "10", "unit": "nm"},
    {"key": "dcnt_nm", "parameter": "Dcnt", "description": "CNT diameter", "example": "1.2", "unit": "nm"},
    {"key": "eg_ev", "parameter": "Eg", "description": "Bandgap", "example": "0.6", "unit": "eV"},
    {"key": "vdd", "parameter": "Vdd", "description": "Supply voltage", "example": "0.8", "unit": "V"},
    {"key": "ion_ua", "parameter": "ION", "description": "On current", "example": "30", "unit": "µA"},
    {"key": "ioff_a", "parameter": "IOFF", "description": "Leakage", "example": "1e-9", "unit": "A"},
    {"key": "cgate_ff", "parameter": "Cgate", "description": "Gate capacitance", "example": "2", "unit": "fF"},
]


def resolve_cntfet_params(overrides: dict[str, float | None] | None = None) -> CntfetParams:
    data = DEFAULT_PARAMS.as_dict()
    if overrides:
        for k, v in overrides.items():
            if v is not None and k in data:
                data[k] = float(v)
    return CntfetParams(**data)


def _cntfet_device_params(p: CntfetParams) -> str:
    return f"""
.param Lch={p.lch_nm}n Dcnt={p.dcnt_nm}n Eg={p.eg_ev} Vdd={p.vdd}
.param ION={p.ion_a} IOFF={p.ioff_a} Cgate={p.cgate_ff}f Vth={p.vth_v}
"""


def build_cntfet_inverter_body(p: CntfetParams) -> str:
    """Behavioral CNTFET CMOS-style inverter (n + p CNTFET B-sources)."""
    return f"""* CNTFET inverter — behavioral (Lch={{Lch}}, Dcnt={{Dcnt}}, Eg={{Eg}} eV)
{_cntfet_device_params(p)}
Vdd vdd 0 {{Vdd}}
* n-CNT pull-down
Bnd out 0 I = {{u(v(in)-Vth)*ION*tanh(5*v(out))+IOFF}}
* p-CNT pull-up
Bpd vdd out I = {{u(Vth-v(in))*ION*tanh(5*(Vdd-v(out)))+IOFF}}
Cload out 0 {{Cgate}}
"""


def build_cmos_baseline_body(p: CntfetParams) -> str:
    """45 nm-class CMOS inverter baseline at the same Vdd and load."""
    wn = max(p.lch_nm * 10, 100)
    wp = wn * 2
    return f"""* CMOS baseline inverter (Level-1 proxy at Vdd={{Vdd}})
.param Vdd={p.vdd}
.model nmos nmos level=1 Vto=0.4 kp=50u
.model pmos pmos level=1 Vto=-0.4 kp=25u
Vdd vdd 0 {{Vdd}}
Mn out in 0 0 nmos W={wn}n L={max(p.lch_nm, 10)}n
Mp out in vdd vdd pmos W={wp}n L={max(p.lch_nm, 10)}n
Cload out 0 {p.cgate_ff}f
"""


def build_cntfet_vtc_netlist(p: CntfetParams) -> str:
    body = build_cntfet_inverter_body(p)
    step = max(p.vdd / 50.0, 0.01)
    return f"""* CNTFET VTC sweep
.title cntfet_vtc
{body}
Vin in 0 0
.dc Vin 0 {{Vdd}} {step}
.option noopiter
.end
"""


def build_cntfet_transient_netlist(p: CntfetParams) -> str:
    body = build_cntfet_inverter_body(p)
    vmid = p.vdd / 2.0
    return f"""* CNTFET inverter transient
.title cntfet_transient
{body}
Vin in 0 PULSE(0 {{Vdd}} 2n 0.1n 0.1n 8n 20n)
.tran 5p 25n 0 5p
.option noopiter
.measure tran t_plh TRIG v(in) VAL={vmid} RISE=1 TARG v(out) VAL={vmid} FALL=1
.measure tran t_phl TRIG v(in) VAL={vmid} FALL=1 TARG v(out) VAL={vmid} RISE=1
.measure tran pavg AVG PAR('V(vdd)*I(Vdd)') FROM=5n TO=22n
.measure tran e_switch INTEG PAR('abs(V(vdd)*I(Vdd))') FROM=5n TO=15n
.end
"""


def build_cmos_transient_netlist(p: CntfetParams) -> str:
    body = build_cmos_baseline_body(p)
    vmid = p.vdd / 2.0
    return f"""* CMOS baseline inverter transient (same Vdd as CNTFET deck)
.title cmos_transient
{body}
Vin in 0 PULSE(0 {{Vdd}} 2n 0.1n 0.1n 8n 20n)
.tran 5p 25n 0 5p
.option noopiter
.measure tran t_plh TRIG v(in) VAL={vmid} RISE=1 TARG v(out) VAL={vmid} FALL=1
.measure tran t_phl TRIG v(in) VAL={vmid} FALL=1 TARG v(out) VAL={vmid} RISE=1
.measure tran pavg AVG PAR('V(vdd)*I(Vdd)') FROM=5n TO=22n
.end
"""


def list_cntfet_presets_payload() -> dict[str, Any]:
    return {
        "parameter_metadata": PARAM_METADATA,
        "citations": CITATIONS,
        "default_params": DEFAULT_PARAMS.as_dict(),
        "simulation_defaults": {
            "citation": "stanford",
            "pulse_period_ns": 20.0,
        },
    }


__all__ = [
    "CITATIONS",
    "DEFAULT_PARAMS",
    "PARAM_METADATA",
    "CntfetParams",
    "build_cntfet_transient_netlist",
    "build_cntfet_vtc_netlist",
    "build_cmos_transient_netlist",
    "list_cntfet_presets_payload",
    "resolve_cntfet_params",
]
