"""Standalone four-methodology Qiskit realization comparison (no mit-panel)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from eda_hub.pages.benchmarks.benchmark_index import build_index
from eda_hub.pages.benchmarks.esop_cost import (
    EsopCostError,
    _resolve_esop_file,
    _safe_load_rpla_from_esop,
)
from eda_hub.shared.function import Function
from eda_hub.shared.product import Product
from eda_hub.shared.rpla import RPLA

from .transpile_study import QUANTUM_COST_FORMULA, run_transpile_comparative_study

_PREFERRED_BENCHMARK_EXTENSIONS = ("esop", "pla", "blif", "v", "sv", "vhd", "vhdl")


def preferred_benchmark_filename(files: dict[str, str]) -> str | None:
    for ext in _PREFERRED_BENCHMARK_EXTENSIONS:
        if ext in files:
            return files[ext]
    return None


def load_rpla_from_esop_file(esop_file: Path) -> RPLA:
    """Parse a local .esop/.pla into an RPLA instance."""
    path = Path(esop_file).expanduser().resolve()
    if not path.is_file():
        raise EsopCostError(f"Benchmark source file not found: {path}")
    if path.suffix.lower() not in {".esop", ".pla"}:
        raise EsopCostError(f"Expected .esop or .pla, got {path.suffix or '(none)'}")

    rpla = RPLA()
    rpla.functions = []
    rpla.products = []
    rpla.patternsOfProduct = []
    rpla.totalLiterals = 0
    rpla.totalProducts = 0
    rpla.totalOutputs = 0

    _safe_load_rpla_from_esop(
        esop_file=path,
        rpla=rpla,
        RPLA=RPLA,
        Function=Function,
        Product=Product,
    )
    if not rpla.products or not rpla.functions:
        raise EsopCostError(f"Unable to parse ESOP data from {path.name}")
    return rpla


def compare_rpla(
    rpla: RPLA,
    *,
    source: str = "",
    circuit: str = "",
    optimization_level: int = 2,
) -> dict[str, Any]:
    """
    Comparative study: convert the benchmark ESOP into optimized transpiled
    Qiskit circuits for all four realization methodologies.
    """
    study = run_transpile_comparative_study(rpla, optimization_level=optimization_level)
    realizations = study["realizations"]

    # Shared layout hint from the CX/CCX family (standard / gaur / zhou share topology).
    std = realizations["standard_quantum"]
    return {
        "circuit": circuit or Path(source).stem,
        "source": source or getattr(rpla, "esopFileName", ""),
        "realizations": realizations,
        "qiskit_realization": {
            "num_qubits": int(std.get("qiskit_num_qubits") or 0),
            "circuit_depth": int(std.get("qiskit_circuit_depth") or 0),
            "optimization_level": study["optimization_level"],
        },
        "transpile_study": {
            "optimization_level": study["optimization_level"],
            "summary": study["summary"],
        },
        "calculation_report": "",
        "quantum_cost_formula": dict(QUANTUM_COST_FORMULA),
    }


def compare_esop_file(
    esop_file: Path | str,
    *,
    optimization_level: int = 2,
) -> dict[str, Any]:
    """Compare four realizations for a local ESOP/PLA file."""
    path = Path(esop_file)
    rpla = load_rpla_from_esop_file(path)
    return compare_rpla(
        rpla,
        source=path.name,
        circuit=path.stem,
        optimization_level=optimization_level,
    )


def compare_benchmark_circuit(
    *,
    suite: str,
    category: str,
    circuit: str,
    filename: str | None = None,
    optimization_level: int = 2,
) -> dict[str, Any]:
    """Compare four realizations for one indexed benchmark circuit."""
    requested = filename
    if not requested:
        circuits_map = (
            build_index().get("suites", {}).get(suite.lower().strip(), {}).get(category.strip())
        )
        if not circuits_map or circuit not in circuits_map:
            raise EsopCostError(f"No benchmark circuits found for {suite}/{category}/{circuit}")
        requested = preferred_benchmark_filename(circuits_map[circuit])
        if not requested:
            raise EsopCostError(f"No supported source file for {circuit}")

    esop_file = _resolve_esop_file(suite, category, circuit, requested)
    rpla = load_rpla_from_esop_file(esop_file)
    out = compare_rpla(
        rpla,
        source=esop_file.name,
        circuit=circuit,
        optimization_level=optimization_level,
    )
    out["suite"] = suite.lower().strip()
    out["category"] = category
    return out


def compare_benchmark_category(
    *,
    suite: str,
    category: str,
    optimization_level: int = 2,
) -> dict[str, Any]:
    """Compare all four realization costs for every circuit in a category."""
    suite_key = suite.lower().strip()
    category_key = category.strip()
    circuits_map = build_index().get("suites", {}).get(suite_key, {}).get(category_key)
    if not circuits_map:
        raise EsopCostError(f"No benchmark circuits found for {suite_key}/{category_key}")

    formula: dict[str, str] = {}
    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for circuit_name in sorted(circuits_map.keys(), key=lambda name: name.lower()):
        files = circuits_map[circuit_name]
        filename = preferred_benchmark_filename(files)
        if not filename:
            skipped.append({"circuit": circuit_name, "error": "No supported source file"})
            continue
        try:
            entry = compare_benchmark_circuit(
                suite=suite_key,
                category=category_key,
                circuit=circuit_name,
                filename=filename,
                optimization_level=optimization_level,
            )
            formula = entry.get("quantum_cost_formula") or formula
            entries.append(entry)
        except EsopCostError as exc:
            skipped.append(
                {
                    "circuit": circuit_name,
                    "filename": filename,
                    "error": str(exc),
                }
            )

    if not entries and skipped:
        raise EsopCostError(
            f"Unable to compute realization comparison for any circuit in {suite_key}/{category_key}"
        )

    return {
        "suite": suite_key,
        "category": category_key,
        "circuit_count": len(circuits_map),
        "computed_count": len(entries),
        "skipped": skipped,
        "entries": entries,
        "quantum_cost_formula": formula,
    }


__all__ = [
    "QUANTUM_COST_FORMULA",
    "compare_benchmark_category",
    "compare_benchmark_circuit",
    "compare_esop_file",
    "compare_rpla",
    "load_rpla_from_esop_file",
    "preferred_benchmark_filename",
]
