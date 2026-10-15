"""ESOP realization cost bridge for benchmark circuits."""
from __future__ import annotations

import asyncio
import contextlib
import copy
import io
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from eda_hub.pages.benchmarks.benchmark_index import resolve_benchmark_file
from eda_hub.pages.benchmarks.cost_calculation import CostCalculation
from eda_hub.pages.benchmarks.existing_calculation import show_mitra2012_optimized_final
from eda_hub.pages.benchmarks.mitra2016_calculation import Mitra2016Calculation
from eda_hub.pages.benchmarks.optimized_rpla_calculation import OptimizedRPLACalculation
from eda_hub.pages.benchmarks.tara2016_calculation import Tara2016Calculation
from eda_hub.pages.cost_metric.table import (
    ALLOWED_COST_METRIC_TECHNOLOGIES,
    TECHNOLOGY_LABELS,
    build_cost_metrics_table,
)
from eda_hub.shared.function import Function
from eda_hub.shared.product import Product
from eda_hub.shared.rpla import RPLA


class EsopCostError(RuntimeError):
    """Raised when ESOP cost calculation cannot be completed."""


# PTL layout metrics (Nangate45 flow: Yosys, OpenROAD, OpenSTA, ngspice; VDD=1.8 V).
# Areas in µm², wire length in µm, power column in table is ×10⁻⁴ W, delay max(rise,fall) in ps.
_PTL = {
    "feynman": {"area": 63.0, "wire_um": 42.0, "power_1e4_w": 0.77452, "delay_ps": 2.3442},
    "mux": {"area": 66.0, "wire_um": 313.0, "power_1e4_w": 2.1578, "delay_ps": 1.6},
    "umg": {"area": 65.0, "wire_um": 210.0, "power_1e4_w": 1.4402, "delay_ps": 1.6},
    "ung": {"area": 64.0, "wire_um": 179.0, "power_1e4_w": 1.4619, "delay_ps": 1.6},
}


def _power_w(power_1e4: float) -> float:
    return power_1e4 * 1e-4


def _mitra_ptl(*, n_mux: int, n_feynman: int) -> dict[str, float | int]:
    m, f = _PTL["mux"], _PTL["feynman"]
    area = n_mux * m["area"] + n_feynman * f["area"]
    wire = n_mux * m["wire_um"] + n_feynman * f["wire_um"]
    power = n_mux * _power_w(m["power_1e4_w"]) + n_feynman * _power_w(f["power_1e4_w"])
    return {"area_um2": area, "wire_um": wire, "power_w": power}


def _tara_ptl(*, n_tb: int, n_f2g: int, n_feynman: int) -> dict[str, float | int]:
    """TB AND gates scale as MUX; F2G copies and Feynman XOR as Feynman (catalog proxies)."""
    m, f = _PTL["mux"], _PTL["feynman"]
    n_fg = n_f2g + n_feynman
    area = n_tb * m["area"] + n_fg * f["area"]
    wire = n_tb * m["wire_um"] + n_fg * f["wire_um"]
    power = n_tb * _power_w(m["power_1e4_w"]) + n_fg * _power_w(f["power_1e4_w"])
    return {"area_um2": area, "wire_um": wire, "power_w": power}


def _optimized_ptl(*, n_umg: int, n_ung: int, n_feynman: int) -> dict[str, float | int]:
    u, n, f = _PTL["umg"], _PTL["ung"], _PTL["feynman"]
    area = n_umg * u["area"] + n_ung * n["area"] + n_feynman * f["area"]
    wire = n_umg * u["wire_um"] + n_ung * n["wire_um"] + n_feynman * f["wire_um"]
    power = (
        n_umg * _power_w(u["power_1e4_w"])
        + n_ung * _power_w(n["power_1e4_w"])
        + n_feynman * _power_w(f["power_1e4_w"])
    )
    return {"area_um2": area, "wire_um": wire, "power_w": power}


def _critical_delay_ps(depth: int) -> float:
    """Conservative ps bound: depth × max tabulated gate delay (Feynman t_max)."""
    if depth <= 0:
        return 0.0
    return float(depth) * _PTL["feynman"]["delay_ps"]


def _optimized_critical_depth(optimized: Any) -> int:
    """AND-plane depth plus longest XOR-chain across outputs (template flow)."""
    xor_chain = 0
    if getattr(optimized, "functions", None):
        xor_chain = max((fn.getSize() - 1) for fn in optimized.functions)
    return max(int(getattr(optimized, "delay", 0)), int(xor_chain))


async def _load_all_technology_gate_rows() -> dict[str, dict[str, dict[str, Any]]]:
    """Prefer mit-panel DB cache when available; else compute tables in-process."""
    load_cost_metrics_table = None
    try:
        from app.services.eda_cost_metrics_store import load_cost_metrics_table as _load

        load_cost_metrics_table = _load
    except Exception:
        load_cost_metrics_table = None

    out: dict[str, dict[str, dict[str, Any]]] = {}
    for tech in ALLOWED_COST_METRIC_TECHNOLOGIES:
        rows = None
        if load_cost_metrics_table is not None:
            data = await load_cost_metrics_table(tech)
            rows = (data or {}).get("rows")
        if not rows:
            rows = build_cost_metrics_table(tech).get("rows") or []
        out[tech] = {str(r["gate_key"]): r for r in rows}
    return out


def _load_all_technology_gate_rows_sync() -> dict[str, dict[str, dict[str, Any]]]:
    try:
        return asyncio.run(_load_all_technology_gate_rows())
    except RuntimeError:
        return {
            tech: {str(r["gate_key"]): r for r in (build_cost_metrics_table(tech).get("rows") or [])}
            for tech in ALLOWED_COST_METRIC_TECHNOLOGIES
        }


def _metric_value(row: dict[str, Any] | None, field: str) -> float | None:
    if not row:
        return None
    value = row.get(field)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scale_gate_mix(
    rows: dict[str, dict[str, Any]],
    weights: list[tuple[str, int]],
) -> dict[str, float | int | None]:
    fields = (
        "area_um2",
        "wirelength_um",
        "avg_power_1e4_w",
        "hpwl_um",
        "t_plh_ps",
        "t_phl_ps",
    )
    scaled: dict[str, float | int | None] = {field: None for field in fields}
    for field in fields:
        total = 0.0
        seen = False
        for gate_key, count in weights:
            if count <= 0:
                continue
            value = _metric_value(rows.get(gate_key), field)
            if value is None:
                continue
            total += count * value
            seen = True
        if seen:
            scaled[field] = round(total, 5 if field == "avg_power_1e4_w" else 4)
    return scaled


def _max_gate_delay_ps(rows: dict[str, dict[str, Any]], gate_keys: list[str]) -> float:
    best = 0.0
    for gate_key in gate_keys:
        row = rows.get(gate_key) or {}
        for field in ("t_plh_ps", "t_phl_ps"):
            value = _metric_value(row, field)
            if value is not None:
                best = max(best, value)
    return best


def _attach_critical_delay(
    metrics: dict[str, float | int | None],
    *,
    depth: int,
    rows: dict[str, dict[str, Any]],
    gate_keys: list[str],
) -> dict[str, float | int | None]:
    out = dict(metrics)
    out["critical_path_depth"] = depth
    per_level = _max_gate_delay_ps(rows, gate_keys)
    out["critical_delay_ps"] = round(float(depth) * per_level, 4) if depth > 0 and per_level > 0 else 0.0
    return out


def _build_technology_costs(
    *,
    gate_rows_by_tech: dict[str, dict[str, dict[str, Any]]],
    n_mux: int,
    n_fey_mitra: int,
    n_umg_m16: int,
    n_ung_m16: int,
    n_fey_m16: int,
    n_tb_tara: int,
    n_f2g_tara: int,
    n_fey_tara: int,
    n_umg: int,
    n_ung: int,
    n_fey_opt: int,
    depth_mitra: int,
    depth_m16: int,
    depth_tara: int,
    depth_opt: int,
) -> dict[str, Any]:
    mitra_weights = [("MUX", n_mux), ("FG", n_fey_mitra)]
    m16_weights = [("UMG", n_umg_m16), ("UNG", n_ung_m16), ("FG", n_fey_m16)]
    tara_weights = [("MUX", n_tb_tara), ("FG", n_f2g_tara + n_fey_tara)]
    opt_weights = [("UMG", n_umg), ("UNG", n_ung), ("FG", n_fey_opt)]
    mitra_gate_keys = [key for key, count in mitra_weights if count > 0]
    m16_gate_keys = [key for key, count in m16_weights if count > 0]
    tara_gate_keys = [key for key, count in tara_weights if count > 0]
    opt_gate_keys = [key for key, count in opt_weights if count > 0]

    technologies: dict[str, Any] = {}
    for tech in ALLOWED_COST_METRIC_TECHNOLOGIES:
        rows = gate_rows_by_tech.get(tech) or {}
        mitra = _scale_gate_mix(rows, mitra_weights)
        mitra2016 = _scale_gate_mix(rows, m16_weights)
        tara2016 = _scale_gate_mix(rows, tara_weights)
        optimized = _scale_gate_mix(rows, opt_weights)
        technologies[tech] = {
            "technology": tech,
            "technology_label": TECHNOLOGY_LABELS[tech],
            "mitra2012": _attach_critical_delay(
                mitra,
                depth=depth_mitra,
                rows=rows,
                gate_keys=mitra_gate_keys or ["FG", "MUX"],
            ),
            "mitra2016": _attach_critical_delay(
                mitra2016,
                depth=depth_m16,
                rows=rows,
                gate_keys=m16_gate_keys or ["FG", "UMG", "UNG"],
            ),
            "tara2016": _attach_critical_delay(
                tara2016,
                depth=depth_tara,
                rows=rows,
                gate_keys=tara_gate_keys or ["FG", "MUX"],
            ),
            "optimized": _attach_critical_delay(
                optimized,
                depth=depth_opt,
                rows=rows,
                gate_keys=opt_gate_keys or ["FG", "UMG", "UNG"],
            ),
        }
    return technologies


def _calc_repo_root() -> Path:
    raw = os.environ.get("EDA_CALCULATE_RPLA_COST_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    from eda_hub.paths import repo_root
    return repo_root()


def _resolve_esop_file(suite: str, category: str, circuit: str, filename: str) -> Path:
    suite_key = suite.lower().strip()
    category_key = category.strip()
    requested = filename.strip()
    candidate = resolve_benchmark_file(suite_key, f"{category_key}/{requested}")
    if candidate is not None and candidate.suffix.lower() in {".esop", ".pla"}:
        return candidate
    for ext in (".esop", ".pla"):
        fallback = resolve_benchmark_file(suite_key, f"{category_key}/{circuit.strip()}{ext}")
        if fallback is not None:
            return fallback
    if candidate is None:
        raise EsopCostError("Benchmark source file not found")
    raise EsopCostError("No ESOP/PLA file found for selected benchmark circuit")


def _safe_load_rpla_from_esop(
    *,
    esop_file: Path,
    rpla: Any,
    RPLA: Any,
    Function: Any,
    Product: Any,
) -> None:
    """
    Parse PLA/ESOP rows robustly and populate the given RPLA instance.

    Some benchmark files have rows where output vectors are shorter than `.o`.
    Upstream parser can crash with "string index out of range"; this loader pads or
    truncates rows safely while preserving circuit semantics as much as possible.
    """
    try:
        lines = [ln.strip() for ln in esop_file.read_text(encoding="utf-8").splitlines()]
    except OSError as exc:
        raise EsopCostError(f"Failed to read ESOP file {esop_file.name}: {exc}") from exc

    total_literals = 0
    total_outputs = 0
    product_rows: list[tuple[str, str]] = []

    for raw in lines:
        if not raw:
            continue
        if raw.startswith("#"):
            continue
        if raw.startswith("."):
            parts = raw.split()
            tag = parts[0].lower()
            if tag == ".i" and len(parts) >= 2:
                total_literals = max(0, int(parts[1]))
            elif tag == ".o" and len(parts) >= 2:
                total_outputs = max(0, int(parts[1]))
            elif tag == ".e":
                break
            continue
        parts = raw.split()
        if len(parts) < 2:
            continue
        cube, outs = parts[0], parts[1]
        product_rows.append((cube, outs))

    if total_literals <= 0 or total_outputs <= 0:
        raise EsopCostError(f"Invalid ESOP header in {esop_file.name}; missing .i/.o")
    if not product_rows:
        raise EsopCostError(f"No product rows found in {esop_file.name}")

    rpla.functions = [Function(i) for i in range(total_outputs)]
    rpla.products = []
    rpla.patternsOfProduct = []
    rpla.totalLiterals = total_literals
    rpla.totalOutputs = total_outputs
    rpla.totalProducts = 0
    rpla.esopFileName = str(esop_file)
    RPLA.totalLiterals = total_literals
    RPLA.totalOutputs = total_outputs

    product_map: dict[str, int] = {}

    for cube_raw, out_raw in product_rows:
        cube = (cube_raw[:total_literals]).ljust(total_literals, "-")
        out_vec = (out_raw[:total_outputs]).ljust(total_outputs, "0")

        if cube in product_map:
            product_idx = product_map[cube]
            product = rpla.products[product_idx]
        else:
            product_idx = len(rpla.products)
            product = Product(product_idx, cube)
            # Initialize function position vector with "not used".
            for _ in range(total_outputs):
                product.addFunction(-1)
            rpla.products.append(product)
            product_map[cube] = product_idx

        for out_idx, bit in enumerate(out_vec):
            if bit != "1":
                continue
            if product.functions[out_idx] != -1:
                continue
            pos = rpla.functions[out_idx].addProduct(product_idx)
            product.functions[out_idx] = pos

    # Match rpla.py inputFormat: Product.addFunction(pos) increments frequency when
    # linking a cube to an output; assigning functions[out_idx] directly leaves
    # frequency at 0 and breaks OptimizedRPLACalculation (Algorithm 5).
    for product in rpla.products:
        product.frequency = sum(1 for pos in product.functions if pos != -1)

    rpla.totalProducts = len(rpla.products)
    if rpla.totalProducts == 0:
        raise EsopCostError(f"No valid products parsed in {esop_file.name}")


def calculate_benchmark_esop_cost(
    *,
    suite: str,
    category: str,
    circuit: str,
    filename: str,
    gate_rows_by_tech: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Compute benchmark ESOP / technology costs (no miteda cache lookup)."""
    return _compute_benchmark_esop_cost(
        suite=suite,
        category=category,
        circuit=circuit,
        filename=filename,
        gate_rows_by_tech=gate_rows_by_tech,
    )


def _compute_benchmark_esop_cost(
    *,
    suite: str,
    category: str,
    circuit: str,
    filename: str,
    gate_rows_by_tech: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """
    Return Mitra2012, Mitra2016, Tara2016, and Optimized (template-driven) metrics for one ESOP file.
    Technology scaling uses eda_cost_metric_rows when gate_rows_by_tech is supplied.
    """
    esop_file = _resolve_esop_file(suite, category, circuit, filename)

    try:
        rpla = RPLA()
        rpla.functions = []
        rpla.products = []
        rpla.patternsOfProduct = []
        rpla.totalLiterals = 0
        rpla.totalProducts = 0
        rpla.totalOutputs = 0

        _safe_load_rpla_from_esop(
            esop_file=esop_file,
            rpla=rpla,
            RPLA=RPLA,
            Function=Function,
            Product=Product,
        )
        if not rpla.products or not rpla.functions:
            raise EsopCostError(f"Unable to parse ESOP data from {esop_file.name}")

        snapshot = SimpleNamespace(
            functions=copy.deepcopy(rpla.functions),
            products=copy.deepcopy(rpla.products),
        )
        snapshot_m16 = SimpleNamespace(
            functions=copy.deepcopy(rpla.functions),
            products=copy.deepcopy(rpla.products),
        )
        snapshot_tara = SimpleNamespace(
            functions=copy.deepcopy(rpla.functions),
            products=copy.deepcopy(rpla.products),
        )

        report_buffer = io.StringIO()
        with contextlib.redirect_stdout(report_buffer):
            print(f"Enter File (.esop) Name: {esop_file.stem}")
            proposed = CostCalculation(rpla, quiet=False)
            proposed.xorPlane()
            proposed.andPlane()

            # Mitra2016: paper Algorithms 4 then 5.
            mitra2016 = Mitra2016Calculation(snapshot_m16, rpla.totalLiterals, quiet=False)
            mitra2016.andPlane()
            mitra2016.xorPlane()

            # Tara2016: journal Algorithms 1–2 (TB AND + Feynman XOR).
            tara2016 = Tara2016Calculation(snapshot_tara, rpla.totalLiterals, quiet=False)
            tara2016.andPlane()
            tara2016.xorPlane()

            # Optimized: template-driven prefix reuse (Alg. 4/5 variant).
            optimized = OptimizedRPLACalculation(snapshot, rpla.totalLiterals, quiet=False)
            optimized.andPlane()
            optimized.xorPlane()

            show_mitra2012_optimized_final(
                rpla,
                proposed,
                optimized,
                mitra2016_calc=mitra2016,
                tara2016_calc=tara2016,
            )

        calculation_report = report_buffer.getvalue().strip()

        n_mux = int(getattr(proposed, "mux_and_gates", 0))
        n_fey_mitra = int(getattr(proposed, "feynman_xor_plane_gates", 0)) + int(
            getattr(proposed, "feynman_and_plane_gates", 0)
        )
        mitra_ptl = _mitra_ptl(n_mux=n_mux, n_feynman=n_fey_mitra)
        depth_mitra = int(getattr(proposed, "delay", 0))
        mitra_ptl["critical_path_depth"] = depth_mitra
        mitra_ptl["critical_delay_ps"] = _critical_delay_ps(depth_mitra)

        n_umg_m16 = int(getattr(mitra2016, "umg_template_gates", 0))
        n_ung_m16 = int(getattr(mitra2016, "ung_template_gates", 0))
        n_fey_m16 = int(getattr(mitra2016, "feynman_xor_plane_gates", 0))
        m16_ptl = _optimized_ptl(n_umg=n_umg_m16, n_ung=n_ung_m16, n_feynman=n_fey_m16)
        depth_m16 = _optimized_critical_depth(mitra2016)
        m16_ptl["critical_path_depth"] = depth_m16
        m16_ptl["critical_delay_ps"] = _critical_delay_ps(depth_m16)

        n_tb_tara = int(getattr(tara2016, "tb_gates", 0))
        n_f2g_tara = int(getattr(tara2016, "f2g_gates", 0))
        n_fey_tara = int(getattr(tara2016, "feynman_xor_plane_gates", 0))
        tara_ptl = _tara_ptl(n_tb=n_tb_tara, n_f2g=n_f2g_tara, n_feynman=n_fey_tara)
        depth_tara = _optimized_critical_depth(tara2016)
        tara_ptl["critical_path_depth"] = depth_tara
        tara_ptl["critical_delay_ps"] = _critical_delay_ps(depth_tara)

        n_umg = int(getattr(optimized, "umg_template_gates", 0))
        n_ung = int(getattr(optimized, "ung_template_gates", 0))
        n_fey_opt = int(getattr(optimized, "feynman_xor_plane_gates", 0))
        opt_ptl = _optimized_ptl(n_umg=n_umg, n_ung=n_ung, n_feynman=n_fey_opt)
        depth_opt = _optimized_critical_depth(optimized)
        opt_ptl["critical_path_depth"] = depth_opt
        opt_ptl["critical_delay_ps"] = _critical_delay_ps(depth_opt)

        gate_rows = gate_rows_by_tech if gate_rows_by_tech is not None else _load_all_technology_gate_rows_sync()
        technology_costs = _build_technology_costs(
            gate_rows_by_tech=gate_rows,
            n_mux=n_mux,
            n_fey_mitra=n_fey_mitra,
            n_umg_m16=n_umg_m16,
            n_ung_m16=n_ung_m16,
            n_fey_m16=n_fey_m16,
            n_tb_tara=n_tb_tara,
            n_f2g_tara=n_f2g_tara,
            n_fey_tara=n_fey_tara,
            n_umg=n_umg,
            n_ung=n_ung,
            n_fey_opt=n_fey_opt,
            depth_mitra=depth_mitra,
            depth_m16=depth_m16,
            depth_tara=depth_tara,
            depth_opt=depth_opt,
        )

        return {
            "suite": suite.lower().strip(),
            "category": category,
            "circuit": circuit,
            "source": esop_file.name,
            "algorithms": {
                "proposed": {
                    "gates": int(proposed.gates),
                    "garbages": int(proposed.garbages),
                    "ancilla_inputs": int(proposed.ancilla_input_count),
                    "quantum_cost": int(proposed.quantumCost),
                },
                "mitra2016": {
                    "gates": int(mitra2016.gates),
                    "garbages": int(mitra2016.garbages),
                    "ancilla_inputs": int(mitra2016.ancilla_input_count),
                    "quantum_cost": int(mitra2016.quantumCost),
                },
                "tara2016": {
                    "gates": int(tara2016.gates),
                    "garbages": int(tara2016.garbages),
                    "ancilla_inputs": int(tara2016.ancilla_input_count),
                    "quantum_cost": int(tara2016.quantumCost),
                },
                "optimized": {
                    "gates": int(optimized.gates),
                    "garbages": int(optimized.garbages),
                    "ancilla_inputs": int(optimized.ancilla_input_count),
                    "quantum_cost": int(optimized.quantumCost),
                },
            },
            "ptl_gate_mix": {
                "mitra2012": {
                    "mux_gates": n_mux,
                    "feynman_gates": n_fey_mitra,
                    "note": "MUX (Sayem09) for AND plane; Feynman for XOR and AND-plane XOR steps.",
                },
                "mitra2016": {
                    "umg_templates": n_umg_m16,
                    "ung_templates": n_ung_m16,
                    "feynman_gates": n_fey_m16,
                    "note": (
                        "Mitra2016 paper Algorithms 1–5: exact P_QG reuse, UMG/UNG AND templates "
                        "(π/π′ → UNG; α,β,γ and primed → UMG), Feynman XOR plane."
                    ),
                },
                "tara2016": {
                    "tb_gates": n_tb_tara,
                    "f2g_gates": n_f2g_tara,
                    "feynman_gates": n_fey_tara,
                    "note": (
                        "Tara2016 journal Algorithms 1–2: TB AND plane with 2-literal sub-product sharing, "
                        "F2G copies, Feynman XOR plane."
                    ),
                },
                "optimized": {
                    "umg_templates": n_umg,
                    "ung_templates": n_ung,
                    "feynman_gates": n_fey_opt,
                    "note": "Template-driven prefix-cube reuse on Algorithm 4; UMG/UNG + Feynman XOR.",
                },
            },
            "ptl_pass_transistor": {
                "mitra2012": mitra_ptl,
                "mitra2016": m16_ptl,
                "tara2016": tara_ptl,
                "optimized": opt_ptl,
                "technology": "Nangate45, VDD=1.8 V",
                "toolchain": "Yosys, OpenROAD, OpenSTA, ngspice",
                "critical_delay_note": (
                    "Critical delay (ps) is depth × 2.3442 ps (conservative per-level bound using max tabulated "
                    "Feynman transition time). Path depth merges AND and XOR stages from the cost model."
                ),
            },
            "technology_costs": technology_costs,
            "calculation_report": calculation_report,
        }
    except EsopCostError:
        raise
    except Exception as exc:
        raise EsopCostError(f"ESOP cost calculation failed: {exc}") from exc
