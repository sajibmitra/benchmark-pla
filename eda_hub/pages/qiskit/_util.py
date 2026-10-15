"""Shared helpers for Qiskit realization cost modules."""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


class QiskitRealizationError(Exception):
    """Raised when a Qiskit realization cost calculation cannot complete."""


def _qiskit_site_candidates() -> list[str]:
    """Optional site-packages hints for workstations that keep a dedicated Qiskit venv."""
    candidates: list[str] = []
    env = os.environ.get("EDA_QISKIT_SITE_PACKAGES", "").strip()
    if env:
        candidates.append(env)
    ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    home = Path.home()
    candidates.extend(
        [
            str(home / "venvs" / "qiskit" / "lib" / f"python{ver}" / "site-packages"),
            str(home / ".venvs" / "qiskit" / "lib" / f"python{ver}" / "site-packages"),
            str(home / ".local" / "share" / "venvs" / "qiskit" / "lib" / f"python{ver}" / "site-packages"),
        ]
    )
    return candidates


def ensure_qiskit() -> None:
    """Import Qiskit from the active environment, or from optional site-packages hints."""
    try:
        from qiskit import QuantumCircuit  # noqa: F401

        return
    except ImportError:
        pass
    for site in _qiskit_site_candidates():
        if site and Path(site).is_dir() and site not in sys.path:
            sys.path.insert(0, site)
            try:
                from qiskit import QuantumCircuit  # noqa: F401

                return
            except ImportError:
                continue
    raise QiskitRealizationError(
        "Qiskit is required for this realization. "
        "On any workstation: pip install -e '.[qiskit]' "
        "(or set EDA_QISKIT_SITE_PACKAGES to a Qiskit site-packages directory)."
    )


def snapshot_rpla(rpla: Any, *, include_total_literals: bool = False) -> SimpleNamespace:
    """Deep-copy functions/products so plane calculators can mutate safely."""
    snap = SimpleNamespace(
        functions=copy.deepcopy(rpla.functions),
        products=copy.deepcopy(rpla.products),
    )
    if include_total_literals:
        snap.totalLiterals = int(getattr(rpla, "totalLiterals", 0) or 0)
    return snap


def ops_count(qc) -> dict[str, int]:
    return {str(k): int(v) for k, v in qc.count_ops().items()}


def total_gates(ops: dict[str, int]) -> int:
    skip = {"barrier", "measure", "delay", "snapshot"}
    return sum(v for k, v in ops.items() if k not in skip)


def gate_depth_for_names(qc, names: set[str]) -> int:
    from qiskit import QuantumCircuit

    filtered = QuantumCircuit(qc.num_qubits)
    for item in qc.data:
        op = item.operation
        if op.name in names:
            filtered.append(op, item.qubits)
    return int(filtered.depth())
