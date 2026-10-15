"""Repository and EDA root path helpers."""
from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Root of the calculate-rpla-cost repository (contains eda_hub/)."""
    return Path(__file__).resolve().parents[1]


def eda_root() -> Path:
    """
    Parent Data/eda tree that hosts tools (abc, yosys, ngspice, OpenROAD, …).

    Override with EDA_ROOT. Default: parent of calculate-rpla-cost.
    """
    raw = os.environ.get("EDA_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return repo_root().parent.resolve()


def benchmarks_root() -> Path:
    """Benchmark circuit tree (MCNC / classic / EPFL)."""
    raw = os.environ.get("EDA_BENCHMARKS_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    calc = os.environ.get("EDA_CALCULATE_RPLA_COST_ROOT", "").strip()
    if calc:
        return (Path(calc).expanduser() / "benchmarks").resolve()
    return (repo_root() / "benchmarks").resolve()


def python_compat_root() -> Path:
    """Legacy ``python/`` shim directory (kept for importlib compatibility)."""
    return repo_root() / "python"
