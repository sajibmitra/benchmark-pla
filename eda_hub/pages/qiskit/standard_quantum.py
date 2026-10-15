"""CNOT/Toffoli mapping (standard quantum) — ExistingCalculation plane cost."""
from __future__ import annotations

import contextlib
import io
from typing import Any

from eda_hub.pages.benchmarks.existing_calculation import ExistingCalculation

from ._util import snapshot_rpla


def calculate_standard_quantum_cost(rpla: Any, *, quiet: bool = True) -> dict[str, Any]:
    """
    Realization 1: CNOT/Toffoli standard quantum mapping.

    Runs ExistingCalculation XOR then AND planes. Quantum cost uses native
    Qiskit unit weights: each CNOT (Feynman) and Toffoli (CCX) counts as 1.
    """
    snap = snapshot_rpla(rpla)
    report = io.StringIO()
    with contextlib.redirect_stdout(report):
        calc = ExistingCalculation(snap, quiet=quiet)
        calc.xorPlane()
        calc.andPlane()

    n_cnot = int(calc.feynman_xor_plane_gates) + int(calc.feynman_and_plane_gates)
    n_toffoli = int(calc.toffoli_and_gates)
    quantum_cost = n_cnot + n_toffoli

    return {
        "framework_id": "standard_quantum",
        "label": "CNOT/Toffoli mapping (standard quantum)",
        "gates": int(calc.gates),
        "garbages": int(calc.garbages),
        "ancilla_inputs": int(calc.ancilla_input_count),
        "quantum_cost": quantum_cost,
        "gate_mix": {
            "cnot_gates": n_cnot,
            "toffoli_gates": n_toffoli,
            "note": (
                "XOR plane and AND-plane routing via Feynman (CNOT); "
                "AND products via Toffoli (CCX). Quantum cost = CNOT + Toffoli (×1 each)."
            ),
        },
        "calculation_report": report.getvalue().strip(),
    }
