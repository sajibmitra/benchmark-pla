"""Canonical 3-qubit UMG / UNG permutation unitaries (Mitverse RPLA templates)."""
from __future__ import annotations

import numpy as np

from ._util import ensure_qiskit


def _perm_matrix(mapping: dict[int, int]) -> np.ndarray:
    mat = np.zeros((8, 8), dtype=complex)
    for src, dst in mapping.items():
        mat[dst, src] = 1.0
    return mat


def umg_permutation_matrix() -> np.ndarray:
    """UMG: P=A, Q=B⊕C, R=(¬A∧C)⊕(A∧B)."""
    mapping: dict[int, int] = {}
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                src = (a << 2) | (b << 1) | c
                p = a
                q = b ^ c
                r = ((1 - a) & c) ^ (a & b)
                dst = (p << 2) | (q << 1) | r
                mapping[src] = dst
    return _perm_matrix(mapping)


def ung_permutation_matrix() -> np.ndarray:
    """UNG: P=A, Q=B, R=(A∨B)⊕C."""
    mapping: dict[int, int] = {}
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                src = (a << 2) | (b << 1) | c
                p = a
                q = b
                r = ((a | b) ^ c)
                dst = (p << 2) | (q << 1) | r
                mapping[src] = dst
    return _perm_matrix(mapping)


def umg_gate():
    """Qiskit Gate named ``umg`` with unitary definition."""
    ensure_qiskit()
    from qiskit.circuit import Gate, QuantumCircuit
    from qiskit.circuit.library import UnitaryGate

    class UMGGate(Gate):
        def __init__(self) -> None:
            super().__init__("umg", 3, [])

        def _define(self) -> None:
            qc = QuantumCircuit(3, name="umg")
            qc.append(UnitaryGate(umg_permutation_matrix(), label="umg"), [0, 1, 2])
            self.definition = qc

    return UMGGate()


def ung_gate():
    """Qiskit Gate named ``ung`` with unitary definition."""
    ensure_qiskit()
    from qiskit.circuit import Gate, QuantumCircuit
    from qiskit.circuit.library import UnitaryGate

    class UNGGate(Gate):
        def __init__(self) -> None:
            super().__init__("ung", 3, [])

        def _define(self) -> None:
            qc = QuantumCircuit(3, name="ung")
            qc.append(UnitaryGate(ung_permutation_matrix(), label="ung"), [0, 1, 2])
            self.definition = qc

    return UNGGate()
