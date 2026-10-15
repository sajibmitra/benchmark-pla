"""Post-CMOS device technology adjustments for OpenROAD physical metrics (CNTFET / memristor)."""
from __future__ import annotations

import math
from typing import Any, Literal

from eda_hub.pages.post_cmos.cntfet_models import CITATIONS as CNTFET_CITATIONS
from eda_hub.pages.post_cmos.memristor_models import VTEAM_DEFAULT_PARAMS, YAKOPCIC_DEFAULT_PARAMS

PostCmosTech = Literal["cntfet", "memristor"]
CntfetModelId = Literal["stanford", "bsim_cmg"]
MemristorModelId = Literal["vteam", "yakopcic"]

# Default ngspice characterization parameters (Post-CMOS page presets).
CNTFET_MODEL = {
    "lch_nm": 10.0,
    "dcnt_nm": 1.2,
    "eg_ev": 0.6,
    "vdd_v": 0.8,
    "ion_ua": 30.0,
    "ioff_a": 1e-9,
    "cgate_ff": 2.0,
    "citation": "Stanford CNTFET compact model",
    "model_type": "stanford",
}

MEMRISTOR_MODEL = {
    "ron_ohm": 100.0,
    "roff_ohm": 16000.0,
    "d_nm": 10.0,
    "x_init": 0.2,
    "von_v": 1.0,
    "voff_v": -1.0,
    "vdd_v": 1.0,
    "citation": "VTEAM (IEEE TCAS-II 2015) threshold memristor",
    "model_type": "vteam",
}

NANGATE45_REF = {"l_nm": 45.0, "vdd_v": 1.8}

_GATE_IO_WIDTH = {
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


def normalize_post_cmos_technology(raw: str) -> PostCmosTech:
    key = raw.lower().strip()
    if key in {"cntfet", "cnt", "carbon_nanotube"}:
        return "cntfet"
    if key in {"memristor", "memristive", "reram"}:
        return "memristor"
    return "cntfet"


def normalize_cntfet_model(raw: str | None) -> CntfetModelId:
    key = (raw or "stanford").lower().strip().replace("-", "_")
    if key in {"bsim_cmg", "bsimcmg", "bsim"}:
        return "bsim_cmg"
    return "stanford"


def normalize_memristor_model(raw: str | None) -> MemristorModelId:
    key = (raw or "vteam").lower().strip()
    if key in {"vterm", "v-team"}:
        key = "vteam"
    if key == "yakopcic":
        return "yakopcic"
    return "vteam"


def resolve_cntfet_device_model(model_type: str | None = None) -> dict[str, Any]:
    mt = normalize_cntfet_model(model_type)
    m = dict(CNTFET_MODEL)
    m["model_type"] = mt
    if mt == "bsim_cmg":
        m.update(
            {
                "lch_nm": 15.0,
                "dcnt_nm": 1.0,
                "eg_ev": 0.55,
                "vdd_v": 0.75,
                "ion_ua": 25.0,
                "ioff_a": 5e-10,
                "cgate_ff": 2.5,
                "citation": CNTFET_CITATIONS["bsim_cmg"]["label"],
            }
        )
    else:
        m["citation"] = CNTFET_CITATIONS["stanford"]["label"]
    return m


def resolve_memristor_device_model(model_type: str | None = None) -> dict[str, Any]:
    mt = normalize_memristor_model(model_type)
    preset = YAKOPCIC_DEFAULT_PARAMS if mt == "yakopcic" else VTEAM_DEFAULT_PARAMS
    citation = (
        "Yakopcic (IEEE EDL 2011) threshold memristor"
        if mt == "yakopcic"
        else "VTEAM (IEEE TCAS-II 2015) threshold memristor"
    )
    return {
        "ron_ohm": preset.ron,
        "roff_ohm": preset.roff,
        "d_nm": preset.d_nm,
        "x_init": preset.x_init,
        "von_v": preset.von,
        "voff_v": preset.voff,
        "vdd_v": max(abs(preset.von), abs(preset.voff), 1.0),
        "citation": citation,
        "model_type": mt,
    }


def resolve_post_cmos_device_model(technology: str, model_type: str | None = None) -> dict[str, Any]:
    tech = normalize_post_cmos_technology(technology)
    if tech == "memristor":
        return resolve_memristor_device_model(model_type)
    return resolve_cntfet_device_model(model_type)


def gate_io_width(gate: str, custom_expr_count: int | None = None) -> int:
    g = gate.lower().strip()
    if g == "custom" and custom_expr_count is not None:
        return max(1, min(4, custom_expr_count))
    return _GATE_IO_WIDTH.get(g, 2)


def _scale_optional(v: float | None, factor: float) -> float | None:
    if v is None or not math.isfinite(v):
        return None
    return v * factor


def _adjust_slack_ns(slack_ns: float | None, delay_delta_ns: float) -> float | None:
    if slack_ns is None or not math.isfinite(slack_ns):
        return None
    return slack_ns - delay_delta_ns


def apply_post_cmos_physical_model(
    core: dict[str, Any],
    *,
    technology: str,
    gate: str,
    custom_expression_count: int | None = None,
    model_type: str | None = None,
) -> dict[str, Any]:
    """
    Scale Nangate45 OpenROAD proxy metrics using the selected post-CMOS device model.
    Structural placement is still Nangate45; adjusted fields reflect CNTFET or memristor assumptions.
    """
    tech = normalize_post_cmos_technology(technology)
    io_w = gate_io_width(gate, custom_expression_count)

    area = core.get("area_um2")
    wl = core.get("wirelength_um")
    hpwl = core.get("hpwl_um_est")
    sta_max = core.get("sta_worst_slack_max_ns")
    sta_min = core.get("sta_worst_slack_min_ns")
    trans = core.get("transistor_count_estimate")
    cells = core.get("mapped_cell_instances")

    if tech == "cntfet":
        m = resolve_cntfet_device_model(model_type)
        length_scale = m["lch_nm"] / NANGATE45_REF["l_nm"]
        vdd_ratio = m["vdd_v"] / NANGATE45_REF["vdd_v"]
        ion_scale = m["ion_ua"] / CNTFET_MODEL["ion_ua"]
        # Delay ~ L / Vdd relative to Nangate45 reference; BSIM-CMG proxy uses slightly higher Cgate.
        delay_scale = length_scale / max(vdd_ratio, 0.1) * (1.0 / max(ion_scale, 0.5))
        area_factor = (length_scale**0.88) * 0.78 * (1.0 + 0.04 * (m["cgate_ff"] / CNTFET_MODEL["cgate_ff"] - 1.0))
        wl_factor = (length_scale**0.55) * 0.9
        ref_delay_ns = 0.12
        delay_delta = ref_delay_ns * (delay_scale - 1.0)
        device_count = int(round((trans or cells or io_w * 4) * max(1.0 / length_scale, 1.0)))
        device_label = "CNTFET channel stacks (est.)"
        model_summary = (
            f"{m['citation']}: Lch={m['lch_nm']} nm, Dcnt={m['dcnt_nm']} nm, Eg={m['eg_ev']} eV, "
            f"Vdd={m['vdd_v']} V, ION≈{m['ion_ua']} µA."
        )
        note = (
            "OpenROAD still maps to Nangate45 for floorplan/placement. Area, wirelength, HPWL, and timing slack "
            "are scaled using the selected CNTFET compact-model geometry (Lch, Vdd, ION) relative to the "
            "45 nm / 1.8 V CMOS proxy."
        )
    else:
        m = resolve_memristor_device_model(model_type)
        r_ratio = m["roff_ohm"] / max(m["ron_ohm"], 1.0)
        crossbar_cells = io_w * io_w
        model_area_bias = 1.08 if m["model_type"] == "yakopcic" else 1.0
        area_factor = (1.35 + 0.15 * math.log10(max(r_ratio, 1.0))) * model_area_bias
        wl_factor = 1.12 + 0.04 * io_w + (0.03 if m["model_type"] == "yakopcic" else 0.0)
        # Memristive SET/RESET switching is slower than CMOS gate delay at the same Vdd.
        ref_delay_ns = 0.25 * (m["roff_ohm"] / 1000.0) ** 0.05
        if m["model_type"] == "yakopcic":
            ref_delay_ns *= 0.82
        delay_delta = ref_delay_ns
        device_count = max(crossbar_cells, int(cells or 0))
        device_label = "Memristor crossbar cells (est.)"
        model_summary = (
            f"{m['citation']}: Ron={m['ron_ohm']} Ω, Roff={m['roff_ohm']} Ω, D={m['d_nm']} nm, "
            f"Von={m['von_v']} V, Voff={m['voff_v']} V."
        )
        note = (
            "OpenROAD structural metrics use Nangate45 CMOS mapping. Adjusted figures add memristor crossbar area "
            "and interconnect overhead from the selected Ron/Roff model and gate I/O width, with switching speed "
            "reflected in slack."
        )

    adjusted = {
        "area_um2": _scale_optional(area, area_factor) if isinstance(area, (int, float)) else None,
        "wirelength_um": _scale_optional(wl, wl_factor) if isinstance(wl, (int, float)) else None,
        "hpwl_um_est": _scale_optional(hpwl, wl_factor) if isinstance(hpwl, (int, float)) else None,
        "sta_worst_slack_max_ns": _adjust_slack_ns(
            sta_max if isinstance(sta_max, (int, float)) else None, delay_delta
        ),
        "sta_worst_slack_min_ns": _adjust_slack_ns(
            sta_min if isinstance(sta_min, (int, float)) else None, delay_delta
        ),
        "device_element_count": device_count,
        "device_element_label": device_label,
        "scaling": {
            "area_factor": round(area_factor, 4),
            "wirelength_factor": round(wl_factor, 4),
            "delay_delta_ns": round(delay_delta, 4),
        },
    }

    return {
        "post_cmos_technology": tech.upper(),
        "post_cmos_model_type": m.get("model_type"),
        "device_model": m,
        "device_model_summary": model_summary,
        "post_cmos_adjusted": adjusted,
        "nangate45_proxy": {
            "area_um2": area,
            "wirelength_um": wl,
            "hpwl_um_est": hpwl,
            "sta_worst_slack_max_ns": sta_max,
            "sta_worst_slack_min_ns": sta_min,
            "transistor_count_estimate": trans,
            "mapped_cell_instances": cells,
        },
        "physical_implementation_note": note,
    }


__all__ = [
    "apply_post_cmos_physical_model",
    "gate_io_width",
    "normalize_cntfet_model",
    "normalize_memristor_model",
    "normalize_post_cmos_technology",
    "resolve_cntfet_device_model",
    "resolve_memristor_device_model",
    "resolve_post_cmos_device_model",
]
