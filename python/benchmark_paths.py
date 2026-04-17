"""
Canonical paths under <repo>/benchmarks/.

On-disk layout (after download_data.sh or a manual checkout):

  benchmarks/epfl/          — EPFL combinational suite (BLIF, etc.)
  benchmarks/mcnc/          — MCNC (Combinational/, Sequential/, …)
  benchmarks/classic/classic/ — small classic ESOP PLAs

Older snapshots used benchmarks/eda/{epfl,mcnc,classic/classic}; helpers
below prefer the new layout and fall back to benchmarks/eda/ when present.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def benchmarks_root() -> Path:
    return repo_root() / "benchmarks"


def _prefer_dir(primary: Path, legacy: Path) -> Path:
    if primary.is_dir():
        return primary
    return legacy


def epfl_benchmark_root() -> Path:
    b = benchmarks_root()
    return _prefer_dir(b / "epfl", b / "eda" / "epfl")


def mcnc_benchmark_root() -> Path:
    b = benchmarks_root()
    return _prefer_dir(b / "mcnc", b / "eda" / "mcnc")


def classic_esop_benchmark_dir() -> Path:
    b = benchmarks_root()
    return _prefer_dir(b / "classic" / "classic", b / "eda" / "classic" / "classic")


def epfl_arithmetic_dir() -> Path:
    """EPFL arithmetic BLIF subset (batch_convert_arithmetic_smart)."""
    return epfl_benchmark_root() / "arithmetic"
