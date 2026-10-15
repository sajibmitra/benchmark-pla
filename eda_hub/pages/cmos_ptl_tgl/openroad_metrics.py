"""
SOP vs ESOP boolean front-end → Yosys (Nangate45) → OpenROAD lite floorplan/place/global-route.

Produces **area** (µm²), **wirelength** (µm from global route), and **congestion** summary
(parsed from FastRoute congestion report when present).

Requires:
- ``yosys``, ``abc``, ``openroad`` on PATH
- Platform files under ``EDA_OPENROAD_ROOT`` (default: ``~/eda/OpenROAD/test``)
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

from eda_hub.pages.benchmarks.benchmark_index import generated_benchmark_root, resolve_benchmark_file
from eda_hub.adapters.events import record_openroad_event
from eda_hub.tools import (
    ToolNotFoundError,
    resolve_abc_executable,
    resolve_openroad_executable,
    resolve_yosys_executable,
)
from eda_hub.pages.cmos_ptl_tgl.reversible_expr import (
    CustomExprError,
    compile_node_to_verilog,
    normalize_custom_expressions,
    parse_expression,
    validate_reversible_permutation,
)
from eda_hub.pages.benchmarks.sop_esop import ConversionError, convert_sop_to_esop

logger = logging.getLogger(__name__)

LogicForm = Literal["sop", "esop"]
ReversibleRealization = Literal["static_cmos", "pass_transistor", "transmission_gate_logic"]


class OpenroadMetricsError(RuntimeError):
    """Raised when synthesis or OpenROAD cannot produce metrics."""


def _require_yosys() -> str:
    try:
        return resolve_yosys_executable()
    except ToolNotFoundError as exc:
        raise OpenroadMetricsError(str(exc)) from exc


def _require_abc() -> str:
    try:
        return resolve_abc_executable()
    except ToolNotFoundError as exc:
        raise OpenroadMetricsError(str(exc)) from exc


def _require_openroad() -> str:
    try:
        return resolve_openroad_executable()
    except ToolNotFoundError as exc:
        raise OpenroadMetricsError(str(exc)) from exc


def openroad_test_root() -> Path:
    raw = os.environ.get("EDA_OPENROAD_ROOT", "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        return p
    from eda_hub.paths import eda_root
    return (eda_root() / "OpenROAD" / "test").resolve()


def _ng_dir(root: Path) -> Path:
    d = root / "Nangate45"
    if not d.is_dir():
        raise OpenroadMetricsError(
            f"Nangate45 platform not found under {root}. "
            "Set EDA_OPENROAD_ROOT to the OpenROAD ``test`` directory (contains Nangate45/)."
        )
    return d


def _normalize_blif_top(blif_in: Path, blif_out: Path, top_name: str = "mitverse_top") -> None:
    """Force a single safe Verilog identifier as the BLIF ``.model`` (PLA/ESOP often embeds file paths)."""
    lines = blif_in.read_text(encoding="utf-8", errors="replace").splitlines()
    out_lines: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(".model "):
            out_lines.append(f".model {top_name}")
            replaced = True
        else:
            out_lines.append(line)
    if not replaced:
        out_lines.insert(0, f".model {top_name}")
    blif_out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def _abc_pla_to_blif(abc: str, pla_in: Path, blif_out: Path, *, timeout: int = 180) -> None:
    cmd = (
        f"read_pla {pla_in.resolve().as_posix()}; strash; "
        f"write_blif {blif_out.resolve().as_posix()}"
    )
    subprocess.run(
        [abc, "-c", cmd],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _resolve_existing_esop(suite: str, category: str, circuit: str, source: Path) -> Path | None:
    cat_parts = tuple(p for p in category.replace("\\", "/").split("/") if p and p != "." and p != "..")
    rel_cat = Path(*cat_parts) if cat_parts else Path(".")
    for cand in (
        source.with_name(f"{circuit}.esop"),
        generated_benchmark_root() / suite.lower().strip() / rel_cat / f"{circuit}.esop",
    ):
        try:
            if cand.is_file():
                return cand.resolve()
        except OSError:
            continue
    return None


def _materialize_esop_pla(
    suite: str,
    category: str,
    circuit: str,
    source: Path,
) -> Path:
    found = _resolve_existing_esop(suite, category, circuit, source)
    if found is not None:
        return found
    try:
        convert_sop_to_esop(suite, category, circuit, source)
    except ConversionError as exc:
        raise OpenroadMetricsError(f"ESOP conversion failed: {exc}") from exc
    found = _resolve_existing_esop(suite, category, circuit, source)
    if found is None:
        raise OpenroadMetricsError("ESOP file was not created next to the source or in the generated overlay.")
    return found


def _yosys_map_nangate(
    yosys: str,
    liberty: Path,
    source_v_or_blif: Path,
    out_verilog: Path,
    *,
    top_module: str | None = None,
    timeout: int = 600,
) -> str:
    """Tech-map to Nangate45 cells; return top module name."""
    ext = source_v_or_blif.suffix.lower()
    if ext in {".v", ".sv"}:
        read = f"read_verilog -defer {source_v_or_blif.resolve().as_posix()}"
    elif ext == ".blif":
        read = f"read_blif {source_v_or_blif.resolve().as_posix()}"
    else:
        raise OpenroadMetricsError(f"Unsupported synth input extension: {ext}")
    lib = liberty.resolve().as_posix()
    out = out_verilog.resolve().as_posix()
    hierarchy = (
        f"hierarchy -check -top {top_module}"
        if top_module
        else "hierarchy -auto-top"
    )
    script = (
        f"{read}; {hierarchy}; proc; opt; flatten; opt; techmap; opt; "
        f"dfflibmap -liberty {lib}; abc -liberty {lib}; opt; clean; "
        f"write_verilog -noattr -noexpr -nohex {out}"
    )
    r = subprocess.run(
        [yosys, "-q", "-p", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if r.returncode != 0:
        tail = ((r.stderr or "") + "\n" + (r.stdout or ""))[-4000:]
        raise OpenroadMetricsError(f"Yosys mapping failed ({r.returncode}). Last output:\n{tail}")
    text = out_verilog.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)", text, re.MULTILINE)
    top = m.group(1) if m else "top"
    return top


def _write_sdc(path: Path) -> None:
    path.write_text(
        "create_clock -name core_clock -period 10\n"
        "set_input_delay 0 -clock core_clock [all_inputs]\n"
        "set_output_delay 0 -clock core_clock [all_outputs]\n",
        encoding="utf-8",
    )


def _build_openroad_tcl(
    *,
    ng: Path,
    synth_v: Path,
    sdc: Path,
    top: str,
    metrics_json: Path,
    log_file: Path,
    guide: Path,
    cong_rpt: Path,
) -> str:
    """Lite flow: floorplan → tap → PDN → place → global_route (no CTS/DRT)."""
    tech_lef = ng / "Nangate45_tech.lef"
    cell_lef = ng / "Nangate45_stdcell.lef"
    lib = ng / "Nangate45_typ.lib"
    tracks = ng / "Nangate45.tracks"
    pdn = ng / "Nangate45.pdn.tcl"
    for p in (tech_lef, cell_lef, lib, tracks, pdn):
        if not p.is_file():
            raise OpenroadMetricsError(f"Missing platform file: {p}")

    thr = os.environ.get("EDA_OPENROAD_THREADS", "4").strip() or "4"
    sv = synth_v.resolve().as_posix()
    sdc_p = sdc.resolve().as_posix()
    mtr = metrics_json.resolve().as_posix()
    lg = log_file.resolve().as_posix()
    gd = guide.resolve().as_posix()
    cr = cong_rpt.resolve().as_posix()

    return f"""
puts "mitverse-eda: OpenROAD lite (SOP/ESOP metrics)"
read_lef {tech_lef.as_posix()}
read_lef {cell_lef.as_posix()}
read_liberty {lib.as_posix()}
read_verilog {sv}
link_design {top}
read_sdc {sdc_p}
set_thread_count {thr}
initialize_floorplan -die_area {{0 0 150 150}} -core_area {{10 10 140 140}} \\
  -site FreePDK45_38x28_10R_NP_162NW_34O
source {tracks.as_posix()}
tapcell -distance 120 -tapcell_master TAPCELL_X1 -endcap_master TAPCELL_X1
source {pdn.as_posix()}
pdngen
set_global_routing_layer_adjustment metal2-metal10 0.5
set_routing_layers -signal metal2-metal10 -clock metal6-metal10
global_placement -density 0.45 -pad_left 2 -pad_right 2 -skip_io
place_pins -hor_layers metal3 -ver_layers metal2
global_placement -routability_driven -density 0.45 -pad_left 2 -pad_right 2
utl::metric "mitverse::design_area_um2" [sta::format_area [rsz::design_area] 0]
set_placement_padding -global -left 1 -right 1
detailed_placement
estimate_parasitics -placement
catch {{ set __wns [sta::worst_slack -max] ; puts "MITPANEL_WNS_MAX $__wns" }}
catch {{ set __wmn [sta::worst_slack -min] ; puts "MITPANEL_WNS_MIN $__wmn" }}
global_route -congestion_iterations 50 -guide_file {gd} \\
  -congestion_report_file {cr} -congestion_report_iter_step 25
report_design_area
"""


def _parse_metrics(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Could not parse OpenROAD metrics JSON at %s", path)
        return {}


def _coerce_float(val: Any) -> float | None:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.strip())
        except ValueError:
            return None
    return None


def _parse_congestion_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "overflow_sum": 0,
            "hotspot_count": 0,
            "note": "No FastRoute congestion report was written (often indicates a clean global route).",
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    overflows = [int(x) for x in re.findall(r"overflow:(\d+)", text)]
    hotspots = len(re.findall(r"violation type:", text))
    return {
        "overflow_sum": sum(overflows) if overflows else 0,
        "hotspot_count": hotspots,
        "overflow_samples": len(overflows),
    }


def _area_from_log(log_text: str) -> float | None:
    m = re.search(r"Design area\s+(\S+)\s+um\^2", log_text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _dbu_per_micron_from_log(log_text: str) -> int:
    """OpenROAD global-placement log includes DBU; Nangate45 flow uses 2000 DBU/µm by default."""
    m = re.search(r"\[INFO GPL-0002\]\s+DBU:\s*(\d+)", log_text)
    if m:
        return max(int(m.group(1)), 1)
    m = re.search(r"(?:^|\n)DBU:\s*(\d+)", log_text)
    if m:
        return max(int(m.group(1)), 1)
    return 2000


def _hpwl_um_from_log(log_text: str) -> float | None:
    """Fallback when metrics JSON omits design__io__hpwl (value is already in µm in the log)."""
    m = re.search(r"I/O nets HPWL:\s*([0-9.eE+-]+)\s*um", log_text)
    if m:
        return _coerce_float(m.group(1))
    m = re.search(r"legalized HPWL\s+(\S+)\s+u", log_text)
    if m:
        return _coerce_float(m.group(1))
    return None


# Rough NMOS+PMOS pair count per Nangate45 cell (for reporting CMOS “transistor” proxy).
_NANGATE_TRANSISTOR_EST: dict[str, int] = {
    "INV_X1": 2,
    "INV_X2": 2,
    "INV_X4": 2,
    "CLKBUF_X1": 2,
    "CLKBUF_X2": 2,
    "CLKBUF_X3": 2,
    "BUF_X1": 2,
    "BUF_X2": 2,
    "BUF_X4": 2,
    "BUF_X8": 2,
    "BUF_X16": 2,
    "BUF_X32": 2,
    "NAND2_X1": 4,
    "NAND2_X2": 4,
    "NAND2_X4": 4,
    "NAND3_X1": 6,
    "NOR2_X1": 4,
    "NOR2_X2": 4,
    "NOR3_X1": 6,
    "AND2_X1": 6,
    "OR2_X1": 6,
    "XOR2_X1": 12,
    "XNOR2_X1": 12,
    "MUX2_X1": 6,
    "OAI21_X1": 6,
    "AOI21_X1": 6,
    "OAI211_X1": 8,
    "AOI211_X1": 8,
    "OAI22_X1": 8,
    "AOI22_X1": 8,
    "TAPCELL_X1": 0,
    "FILLCELL_X1": 0,
    "FILLCELL_X2": 0,
    "FILLCELL_X4": 0,
    "FILLCELL_X8": 0,
    "FILLCELL_X16": 0,
    "FILLCELL_X32": 0,
}


def _parse_mitpanel_float(token: str) -> float | None:
    t = token.strip().strip(",").rstrip(")")
    if not t or t.lower() in {"nan", "inf", "-inf", "na", "n/a"}:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _parse_mitpanel_sta_log(log_text: str) -> tuple[float | None, float | None]:
    """Parse markers emitted after OpenSTA ``sta::worst_slack`` (values in seconds → ns)."""
    wmax: float | None = None
    wmin: float | None = None
    for m in re.finditer(r"MITPANEL_WNS_MAX\s+(\S+)", log_text):
        wmax = _parse_mitpanel_float(m.group(1))
    for m in re.finditer(r"MITPANEL_WNS_MIN\s+(\S+)", log_text):
        wmin = _parse_mitpanel_float(m.group(1))

    def to_ns(sec: float | None) -> float | None:
        if sec is None:
            return None
        return sec * 1e9

    return to_ns(wmax), to_ns(wmin)


def _mapped_verilog_cell_stats(synth_v: Path) -> dict[str, Any]:
    """Count Nangate-style instances in Yosys-mapped Verilog (CMOS standard-cell proxy)."""
    if not synth_v.is_file():
        return {
            "mapped_cell_instances": 0,
            "mapped_cell_histogram": {},
            "transistor_count_estimate": 0,
        }
    text = synth_v.read_text(encoding="utf-8", errors="replace")
    hist: dict[str, int] = {}
    skip_prefixes = (
        "module ",
        "endmodule",
        "assign ",
        "wire ",
        "input ",
        "output ",
        "inout ",
    )
    inst_re = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_$]*)\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\(")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if any(line.startswith(p) for p in skip_prefixes):
            continue
        mo = inst_re.match(line)
        if not mo:
            continue
        cell_type = mo.group(1)
        if cell_type == "module":
            continue
        hist[cell_type] = hist.get(cell_type, 0) + 1

    total = sum(hist.values())
    est = 0
    for ctype, n in hist.items():
        per = _NANGATE_TRANSISTOR_EST.get(ctype, 4)
        est += per * n

    top = dict(sorted(hist.items(), key=lambda kv: (-kv[1], kv[0]))[:40])
    return {
        "mapped_cell_instances": total,
        "mapped_cell_histogram": top,
        "transistor_count_estimate": est,
    }


# Same Boolean lines as ngspice behavioral presets (3×3).
_NAMED_REV_EXPS_3: dict[str, tuple[str, str, str]] = {
    "umg": ("A", "B^C", "!A&C^A&B"),
    "ung": ("A", "B", "(A|B)^C"),
    "mux": ("A", "A^B^C", "~A&C^A&B"),
    "nmg": ("A^B", "B&!C^A&C", "!B&C^A&!C"),
}

# Structural RTL aligned with ngspice preset decomposition (CMOS: NAND/XOR stack; PTL: XOR as AND/OR, MUX paths).
_REV_VERILOG_CELLS = """
module mit_inv(input wire a, output wire y);
  assign y = ~a;
endmodule
module mit_nand2(input wire a, input wire b, output wire y);
  assign y = ~(a & b);
endmodule
module mit_and2(input wire a, input wire b, output wire y);
  assign y = a & b;
endmodule
module mit_or2(input wire a, input wire b, output wire y);
  assign y = a | b;
endmodule
module mit_buf2(input wire a, output wire y);
  wire n;
  mit_inv i1(.a(a), .y(n));
  mit_inv i2(.a(n), .y(y));
endmodule
module mit_xor_cmos(input wire a, input wire b, output wire y);
  wire p1, p2, p3;
  mit_nand2 n1(.a(a), .b(b), .y(p1));
  mit_nand2 n2(.a(a), .b(p1), .y(p2));
  mit_nand2 n3(.a(b), .b(p1), .y(p3));
  mit_nand2 n4(.a(p2), .b(p3), .y(y));
endmodule
module mit_xor_pt(input wire a, input wire b, output wire y);
  wire an, bn, t1, t2;
  mit_inv ia(.a(a), .y(an));
  mit_inv ib(.a(b), .y(bn));
  assign t1 = a & bn;
  assign t2 = an & b;
  assign y = t1 | t2;
endmodule
module mit_xor_pl(input wire a, input wire b, output wire y);
  assign y = a ^ b;
endmodule
module mit_mux2(input wire sel, input wire i0, input wire i1, output wire y);
  assign y = sel ? i1 : i0;
endmodule
""".strip()


def _verilog_module_reversible_from_exprs(exprs: list[str]) -> str:
    w = len(exprs)
    nodes = [parse_expression(e, w) for e in exprs]
    validate_reversible_permutation(nodes, w)
    outs = ("p", "q", "r", "s")[:w]
    ins = ("a", "b", "c", "d")[:w]
    port_decls = [f"  input wire {x}" for x in ins] + [f"  output wire {x}" for x in outs]
    ports_joined = ",\n".join(port_decls)
    assigns = "\n".join(f"  assign {po} = {compile_node_to_verilog(n)};" for po, n in zip(outs, nodes))
    return f"module mit_rev_top (\n{ports_joined}\n);\n{assigns}\nendmodule\n"


def _build_reversible_gate_verilog(
    gate: str,
    custom_expressions: list[str] | None,
    realization: ReversibleRealization,
) -> tuple[str, str, list[str] | None, str | None]:
    """
    Return (verilog source, normalized gate id, custom lines if gate==custom, optional rtl_note).

    Preset NOT/Feynman/Toffoli/Peres/Fredkin: structural RTL differs by ``realization`` (like ngspice netlists).
    Custom / UMG / UNG / MUX / NMG: OpenROAD uses ideal Boolean RTL for every style; ``rtl_note`` explains this.
    """
    g = gate.lower().strip()
    custom_norm: list[str] | None = None

    if g in _NAMED_REV_EXPS_3 or g == "custom":
        if g == "custom":
            exprs = normalize_custom_expressions(custom_expressions or [])
            custom_norm = exprs
            src = _verilog_module_reversible_from_exprs(exprs)
        else:
            src = _verilog_module_reversible_from_exprs(list(_NAMED_REV_EXPS_3[g]))
        note = (
            "Ideal Boolean RTL is identical for static CMOS, pass-transistor, and transmission-gate logic here "
            "(same as ngspice behavioral custom/named gates). Structural variants apply only to NOT, Feynman, "
            "Toffoli, Peres, and Fredkin."
        )
        return src, g, custom_norm, note

    lib = _REV_VERILOG_CELLS + "\n\n"

    if g == "not":
        top = """module mit_rev_top (
  input wire a,
  output wire p
);
  mit_inv i(.a(a), .y(p));
endmodule
"""
        return lib + top, g, None, None

    if g == "feynman":
        if realization == "static_cmos":
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  output wire p,
  output wire q
);
  mit_buf2 b0(.a(a), .y(p));
  mit_xor_cmos x0(.a(a), .b(b), .y(q));
endmodule
"""
        elif realization == "transmission_gate_logic":
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  output wire p,
  output wire q
);
  assign p = a;
  mit_xor_pt x0(.a(a), .b(b), .y(q));
endmodule
"""
        else:
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  output wire p,
  output wire q
);
  assign p = a;
  mit_xor_pl x0(.a(a), .b(b), .y(q));
endmodule
"""
        return lib + top, g, None, None

    if g == "toffoli":
        if realization == "static_cmos":
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  input wire c,
  output wire p,
  output wire q,
  output wire r
);
  mit_buf2 b1(.a(a), .y(p));
  mit_buf2 b2(.a(b), .y(q));
  wire nab, vab;
  mit_nand2 n_ab(.a(a), .b(b), .y(nab));
  mit_inv i_ab(.a(nab), .y(vab));
  mit_xor_cmos x_r(.a(c), .b(vab), .y(r));
endmodule
"""
        elif realization == "transmission_gate_logic":
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  input wire c,
  output wire p,
  output wire q,
  output wire r
);
  mit_buf2 b1(.a(a), .y(p));
  mit_buf2 b2(.a(b), .y(q));
  wire nab, vab;
  mit_nand2 n_ab(.a(a), .b(b), .y(nab));
  mit_inv i_ab(.a(nab), .y(vab));
  mit_xor_pt x_r(.a(c), .b(vab), .y(r));
endmodule
"""
        else:
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  input wire c,
  output wire p,
  output wire q,
  output wire r
);
  mit_buf2 b1(.a(a), .y(p));
  mit_buf2 b2(.a(b), .y(q));
  wire nab, vab;
  mit_nand2 n_ab(.a(a), .b(b), .y(nab));
  mit_inv i_ab(.a(nab), .y(vab));
  mit_xor_pl x_r(.a(c), .b(vab), .y(r));
endmodule
"""
        return lib + top, g, None, None

    if g == "peres":
        if realization == "static_cmos":
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  input wire c,
  output wire p,
  output wire q,
  output wire r
);
  mit_buf2 b1(.a(a), .y(p));
  mit_xor_cmos x_q(.a(a), .b(b), .y(q));
  wire nab, vab;
  mit_nand2 n_ab(.a(a), .b(b), .y(nab));
  mit_inv i_ab(.a(nab), .y(vab));
  mit_xor_cmos x_r(.a(c), .b(vab), .y(r));
endmodule
"""
        elif realization == "transmission_gate_logic":
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  input wire c,
  output wire p,
  output wire q,
  output wire r
);
  mit_buf2 b1(.a(a), .y(p));
  mit_xor_pt x_q(.a(a), .b(b), .y(q));
  wire nab, vab;
  mit_nand2 n_ab(.a(a), .b(b), .y(nab));
  mit_inv i_ab(.a(nab), .y(vab));
  mit_xor_pt x_r(.a(c), .b(vab), .y(r));
endmodule
"""
        else:
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  input wire c,
  output wire p,
  output wire q,
  output wire r
);
  mit_buf2 b1(.a(a), .y(p));
  mit_xor_pl x_q(.a(a), .b(b), .y(q));
  wire nab, vab;
  mit_nand2 n_ab(.a(a), .b(b), .y(nab));
  mit_inv i_ab(.a(nab), .y(vab));
  mit_xor_pl x_r(.a(c), .b(vab), .y(r));
endmodule
"""
        return lib + top, g, None, None

    if g == "fredkin":
        if realization == "static_cmos":
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  input wire c,
  output wire p,
  output wire q,
  output wire r
);
  wire na, t1, t2, t3, t4;
  mit_inv i_a(.a(a), .y(na));
  mit_and2 a1(.a(na), .b(b), .y(t1));
  mit_and2 a2(.a(a), .b(c), .y(t2));
  mit_or2 o1(.a(t1), .b(t2), .y(q));
  mit_and2 a3(.a(na), .b(c), .y(t3));
  mit_and2 a4(.a(a), .b(b), .y(t4));
  mit_or2 o2(.a(t3), .b(t4), .y(r));
  assign p = a;
endmodule
"""
        elif realization == "transmission_gate_logic":
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  input wire c,
  output wire p,
  output wire q,
  output wire r
);
  mit_mux2 mq(.sel(a), .i0(b), .i1(c), .y(q));
  mit_mux2 mr(.sel(a), .i0(c), .i1(b), .y(r));
  assign p = a;
endmodule
"""
        else:
            top = """module mit_rev_top (
  input wire a,
  input wire b,
  input wire c,
  output wire p,
  output wire q,
  output wire r
);
  assign p = a;
  assign q = (~a & b) | (a & c);
  assign r = (~a & c) | (a & b);
endmodule
"""
        return lib + top, g, None, None

    raise OpenroadMetricsError(f"Unknown reversible gate {gate!r}.")


def _openroad_run_place_route(
    wd: Path,
    *,
    root: Path,
    ng: Path,
    openroad: str,
    synth_v: Path,
    sdc: Path,
    top: str,
    t0: float,
    suite: str,
    category: str,
    circuit: str,
    logic_form: str,
    source_file: str,
) -> dict[str, Any]:
    metrics_json = wd / "metrics.json"
    or_log = wd / "openroad.log"
    tcl = wd / "run.tcl"
    guide = wd / "route.guide"
    cong = wd / "congestion.rpt"

    tcl.write_text(
        _build_openroad_tcl(
            ng=ng,
            synth_v=synth_v,
            sdc=sdc,
            top=top,
            metrics_json=metrics_json,
            log_file=or_log,
            guide=guide,
            cong_rpt=cong,
        ),
        encoding="utf-8",
    )

    cmd = [
        openroad,
        "-exit",
        "-log",
        str(or_log),
        "-metrics",
        str(metrics_json),
        str(tcl),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(wd),
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("EDA_OPENROAD_TIMEOUT", "900")),
        )
    except subprocess.TimeoutExpired:
        record_openroad_event(
            status="timeout",
            command=" ".join(cmd),
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="OpenROAD timed out",
            suite=suite,
            category=category,
            circuit=circuit,
            logic_form=logic_form,
            source_file=source_file,
        )
        raise OpenroadMetricsError(
            "OpenROAD timed out. Try a smaller MCNC circuit, or increase EDA_OPENROAD_TIMEOUT."
        ) from None

    log_text = or_log.read_text(encoding="utf-8", errors="replace") if or_log.is_file() else ""
    ok = proc.returncode == 0
    if not ok:
        tail = ((proc.stderr or "") + "\n" + (proc.stdout or "") + "\n" + log_text)[-5000:]
        record_openroad_event(
            status="error",
            command=" ".join(cmd),
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail=tail[:1500],
            suite=suite,
            category=category,
            circuit=circuit,
            logic_form=logic_form,
            source_file=source_file,
        )
        raise OpenroadMetricsError(f"OpenROAD exited with status {proc.returncode}. Last output:\n{tail}")

    metrics = _parse_metrics(metrics_json)
    cong_info = _parse_congestion_report(cong)
    cell_stats = _mapped_verilog_cell_stats(synth_v)
    sta_max_ns, sta_min_ns = _parse_mitpanel_sta_log(log_text)

    area_m = _coerce_float(metrics.get("mitverse::design_area_um2"))
    area_log = _area_from_log(log_text)
    area_um2 = area_m if area_m is not None else area_log

    wl = _coerce_float(metrics.get("global_route__wirelength"))
    if wl is None:
        wl = _coerce_float(metrics.get("route__wirelength__estimated"))

    # design__io__hpwl is recorded in database units (see IOPlacer::reportHPWL); convert to µm for the API.
    hpwl_raw = _coerce_float(metrics.get("design__io__hpwl"))
    dbu_per_um = _dbu_per_micron_from_log(log_text)
    hpwl = (hpwl_raw / dbu_per_um) if hpwl_raw is not None else None
    if hpwl is None:
        hpwl = _hpwl_um_from_log(log_text)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    record_openroad_event(
        status="ok",
        command=" ".join(cmd),
        duration_ms=elapsed_ms,
        detail=f"area={area_um2} um2 wl={wl}",
        suite=suite,
        category=category,
        circuit=circuit,
        logic_form=logic_form,
        source_file=source_file,
    )

    return {
        "top_module": top,
        "openroad_root": str(root),
        "area_um2": area_um2,
        "wirelength_um": wl,
        "hpwl_um_est": hpwl,
        "congestion": cong_info,
        "metrics_excerpt": {
            k: metrics[k]
            for k in (
                "mitverse::design_area_um2",
                "global_route__wirelength",
                "route__wirelength__estimated",
                "design__io__hpwl",
                "floorplan__design__io",
            )
            if k in metrics
        },
        "duration_ms": elapsed_ms,
        "mapped_cell_instances": cell_stats["mapped_cell_instances"],
        "mapped_cell_histogram": cell_stats["mapped_cell_histogram"],
        "transistor_count_estimate": cell_stats["transistor_count_estimate"],
        "sta_worst_slack_max_ns": sta_max_ns,
        "sta_worst_slack_min_ns": sta_min_ns,
    }


def run_openroad_reversible_gate_metrics(
    gate: str,
    custom_expressions: list[str] | None = None,
    realization: ReversibleRealization = "static_cmos",
    *,
    post_cmos_technology: str = "CNTFET",
    model_type: str | None = None,
) -> dict[str, Any]:
    """
    Synthesize a small combinational reversible gate (same presets/custom syntax as ngspice),
    optional **static_cmos**, **pass_transistor**, or **transmission_gate_logic** structural RTL for built-in presets,
    map with Yosys to Nangate45, and run the same lite OpenROAD flow as SOP/ESOP metrics.
    """
    try:
        v_text, g, custom_norm, rtl_note = _build_reversible_gate_verilog(
            gate, custom_expressions, realization
        )
    except CustomExprError as exc:
        raise OpenroadMetricsError(str(exc)) from exc

    yosys = _require_yosys()
    openroad = _require_openroad()

    root = openroad_test_root()
    ng = _ng_dir(root)
    liberty = ng / "Nangate45_typ.lib"

    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="mit_eda_or_rev_") as tmp:
        wd = Path(tmp)
        rev_v = wd / "mit_rev.v"
        rev_v.write_text(v_text, encoding="utf-8")
        synth_v = wd / "synth_mapped.v"
        sdc = wd / "design.sdc"
        _write_sdc(sdc)
        top = _yosys_map_nangate(yosys, liberty, rev_v, synth_v, top_module="mit_rev_top")
        core = _openroad_run_place_route(
            wd,
            root=root,
            ng=ng,
            openroad=openroad,
            synth_v=synth_v,
            sdc=sdc,
            top=top,
            t0=t0,
            suite="reversible",
            category=g,
            circuit="mit_rev_top",
            logic_form=f"reversible:{realization}",
            source_file="mit_rev.v",
        )

    out: dict[str, Any] = {"gate": g, "realization": realization, **core}
    if custom_norm is not None:
        out["custom_expressions"] = custom_norm
    if rtl_note:
        out["rtl_note"] = rtl_note
    return out


def run_openroad_sop_esop_metrics(
    suite: str,
    category: str,
    circuit: str,
    filename: str,
    logic_form: LogicForm,
) -> dict[str, Any]:
    suite_key = suite.lower().strip()
    yosys = _require_yosys()
    abc = _require_abc()
    openroad = _require_openroad()

    path = resolve_benchmark_file(suite_key, f"{category}/{filename}")
    if path is None:
        for ext in ("blif", "pla", "v", "sv"):
            alt = resolve_benchmark_file(suite_key, f"{category}/{circuit}.{ext}")
            if alt is not None:
                path = alt
                break
    if path is None:
        raise OpenroadMetricsError("Benchmark source file not found.")

    root = openroad_test_root()
    ng = _ng_dir(root)
    liberty = ng / "Nangate45_typ.lib"

    t0 = time.monotonic()

    with tempfile.TemporaryDirectory(prefix="mit_eda_or_") as tmp:
        wd = Path(tmp)
        synth_v = wd / "synth_mapped.v"
        sdc = wd / "design.sdc"

        _write_sdc(sdc)

        if logic_form == "sop":
            top = _yosys_map_nangate(yosys, liberty, path, synth_v)
        else:
            if path.suffix.lower() not in {".v", ".sv", ".blif"}:
                raise OpenroadMetricsError("ESOP flow needs a .v, .sv, or .blif starting point.")
            pla_path = _materialize_esop_pla(suite_key, category, circuit, path)
            esop_blif_raw = wd / "from_esop_raw.blif"
            esop_blif = wd / "from_esop.blif"
            _abc_pla_to_blif(abc, pla_path, esop_blif_raw)
            _normalize_blif_top(esop_blif_raw, esop_blif)
            top = _yosys_map_nangate(yosys, liberty, esop_blif, synth_v)

        core = _openroad_run_place_route(
            wd,
            root=root,
            ng=ng,
            openroad=openroad,
            synth_v=synth_v,
            sdc=sdc,
            top=top,
            t0=t0,
            suite=suite_key,
            category=category,
            circuit=circuit,
            logic_form=logic_form,
            source_file=str(path),
        )
        return {
            "suite": suite_key,
            "category": category,
            "circuit": circuit,
            "source_file": path.name,
            "logic_form": logic_form,
            **core,
        }


__all__ = [
    "OpenroadMetricsError",
    "openroad_test_root",
    "ReversibleRealization",
    "run_openroad_reversible_gate_metrics",
    "run_openroad_sop_esop_metrics",
]
