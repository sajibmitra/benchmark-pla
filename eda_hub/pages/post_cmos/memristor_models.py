"""Published memristor models and parameter presets for Post-CMOS ngspice characterization."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

PresetId = Literal["vteam_default", "yakopcic", "custom"]

GATE_WIDTH = {
    "not": 1,
    "feynman": 2,
    "toffoli": 3,
    "fredkin": 3,
    "peres": 3,
    "mux": 3,
    "umg": 3,
    "ung": 3,
    "nmg": 3,
    "custom": 2,
}

GATE_LABEL = {
    "not": "NOT (1×1)",
    "feynman": "Feynman (2×2)",
    "toffoli": "Toffoli (3×3)",
    "fredkin": "Fredkin (3×3)",
    "peres": "Peres (3×3)",
    "mux": "MUX (3×3)",
    "umg": "UMG (3×3)",
    "ung": "UNG (3×3)",
    "nmg": "NMG (3×3)",
    "custom": "Custom",
}


@dataclass(frozen=True)
class MemristorParams:
    ron: float = 100.0
    roff: float = 16000.0
    d_nm: float = 10.0
    x_init: float = 0.2
    von: float = 1.0
    voff: float = -1.0
    kon: float = 1e-13
    koff: float = 1e-13
    alpha_on: float = 3.0
    alpha_off: float = 3.0

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


VTEAM_DEFAULT_PARAMS = MemristorParams()

YAKOPCIC_DEFAULT_PARAMS = MemristorParams(
    ron=100.0,
    roff=10000.0,
    d_nm=10.0,
    x_init=0.11,
    von=0.65,
    voff=-0.56,
    kon=4000.0,
    koff=4000.0,
    alpha_on=1.0,
    alpha_off=5.0,
)

PRESET_PARAMS: dict[PresetId, MemristorParams] = {
    "vteam_default": VTEAM_DEFAULT_PARAMS,
    "yakopcic": YAKOPCIC_DEFAULT_PARAMS,
    "custom": VTEAM_DEFAULT_PARAMS,
}

PARAM_METADATA: list[dict[str, str]] = [
    {"key": "ron", "parameter": "Ron", "description": "Low resistance state", "example": "100", "unit": "Ω"},
    {"key": "roff", "parameter": "Roff", "description": "High resistance state", "example": "16000", "unit": "Ω"},
    {"key": "d_nm", "parameter": "D", "description": "Device length", "example": "10", "unit": "nm"},
    {"key": "x_init", "parameter": "x_init", "description": "Initial state", "example": "0.2", "unit": "—"},
    {"key": "von", "parameter": "Von", "description": "SET threshold voltage", "example": "1.0", "unit": "V"},
    {"key": "voff", "parameter": "Voff", "description": "RESET threshold voltage", "example": "-1.0", "unit": "V"},
    {"key": "kon", "parameter": "Kon", "description": "SET rate coefficient", "example": "1e-13", "unit": "—"},
    {"key": "koff", "parameter": "Koff", "description": "RESET rate coefficient", "example": "1e-13", "unit": "—"},
    {"key": "alpha_on", "parameter": "Alpha_on", "description": "SET exponent", "example": "3", "unit": "—"},
    {"key": "alpha_off", "parameter": "Alpha_off", "description": "RESET exponent", "example": "3", "unit": "—"},
]


def resolve_params(
    preset: str,
    *,
    overrides: dict[str, float | None] | None = None,
) -> tuple[MemristorParams, PresetId]:
    key: PresetId = preset if preset in PRESET_PARAMS else "vteam_default"  # type: ignore[assignment]
    base = PRESET_PARAMS[key]
    if key != "custom" and not overrides:
        return base, key
    data = base.as_dict()
    if overrides:
        for k, v in overrides.items():
            if v is not None and k in data:
                data[k] = float(v)
    return MemristorParams(**data), key


def vteam_device_body(params: MemristorParams) -> str:
    """VTEAM — Kvatinsky et al. 2015 (ngspice B-sources, published rate coefficients)."""
    v_set = params.von
    v_reset = params.voff
    kon = max(abs(params.kon), 1e-20)
    koff = max(abs(params.koff), 1e-20)
    return f"""
* VTEAM memristor (ngspice behavioral; Kvatinsky et al., IEEE TCAS-II 2015)
* D={params.d_nm} nm scales state window; x_init={params.x_init}
.param Ron={params.ron} Roff={params.roff} v_set={v_set} v_reset={v_reset}
+ kon={kon} koff={koff} alpha_on={params.alpha_on} alpha_off={params.alpha_off} w0={params.x_init}
Bx 0 nX I = {{koff*pow(v(TEi)/v_set-1,alpha_off)*u(v(TEi)-v_set)+kon*pow(v(TEi)/v_reset-1,alpha_on)*u(v_reset-v(TEi))}}
Cx nX 0 1
.ic v(nX)=w0
Bmem TEi 0 I = {{v(TEi)/(Ron+(Roff-Ron)*0.5*(tanh(10*(v(nX)-0.5))+1))}}
"""


def yakopcic_device_body(params: MemristorParams) -> str:
    """Yakopcic et al. 2011 — maps shared parameter table onto published subcircuit."""
    a1 = 0.17 * (100.0 / params.ron) if params.ron > 0 else 0.17
    vp = params.von
    vn = abs(params.voff)
    ap = max(abs(params.koff), 1.0) if params.koff else 4000.0
    an = max(abs(params.kon), 1.0) if params.kon else 4000.0
    return f"""
* Yakopcic memristor (ngspice behavioral; Yakopcic et al., IEEE EDL 2011)
.param a1={a1} a2={a1} b=0.05 Vp={vp} Vn={vn} Ap={ap} An={an} xo={params.x_init}
Bx 0 nX I = {{Ap*(exp(v(TEi))-exp(Vp))*u(v(TEi)-Vp)-An*(exp(-v(TEi))-exp(Vn))*u(-Vn-v(TEi))}}
Cx nX 0 1
.ic v(nX)=xo
Bmem TEi 0 I = {{a1*v(nX)*sinh(b*v(TEi))}}
"""


def device_body(model: str, params: MemristorParams) -> str:
    if model == "yakopcic":
        return yakopcic_device_body(params)
    return vteam_device_body(params)


def list_presets_payload() -> dict[str, Any]:
    return {
        "parameter_metadata": PARAM_METADATA,
        "presets": {
            "vteam_default": {
                "label": "VTEAM default (Post-CMOS)",
                "model_type": "vteam",
                "params": VTEAM_DEFAULT_PARAMS.as_dict(),
                "simulation_defaults": {
                    "vdd_volts": 1.0,
                    "pulse_width_ns": 50.0,
                    "pulse_gap_ns": 20.0,
                    "sweep_period_us": 40.0,
                },
            },
            "yakopcic": {
                "label": "Yakopcic published",
                "model_type": "yakopcic",
                "params": YAKOPCIC_DEFAULT_PARAMS.as_dict(),
                "simulation_defaults": {
                    "vdd_volts": 0.9,
                    "pulse_width_ns": 8.0,
                    "pulse_gap_ns": 6.0,
                    "sweep_period_us": 20.0,
                },
            },
        },
    }


__all__ = [
    "GATE_LABEL",
    "GATE_WIDTH",
    "MemristorParams",
    "PARAM_METADATA",
    "PRESET_PARAMS",
    "VTEAM_DEFAULT_PARAMS",
    "YAKOPCIC_DEFAULT_PARAMS",
    "device_body",
    "list_presets_payload",
    "resolve_params",
]
