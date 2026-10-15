"""UMG-UNG mapping (optimized RPLA) — template-weighted AND + Feynman XOR."""
from __future__ import annotations

import contextlib
import io
from typing import Any

from optimized_rpla_calculation import OptimizedRPLACalculation

from ._util import snapshot_rpla


def calculate_umg_ung_cost(
    rpla: Any,
    *,
    total_literals: int | None = None,
    quiet: bool = True,
) -> dict[str, Any]:
    """
    Realization 2: UMG/UNG + CNOT optimized RPLA mapping.

    Quantum cost = CNOT ×1 + (UMG + UNG templates) ×5.
    """
    snap = snapshot_rpla(rpla)
    n_lit = int(total_literals if total_literals is not None else getattr(rpla, "totalLiterals", 0) or 0)
    report = io.StringIO()
    with contextlib.redirect_stdout(report):
        calc = OptimizedRPLACalculation(snap, n_lit, quiet=quiet)
        calc.andPlane()
        calc.xorPlane()

    n_umg = int(getattr(calc, "umg_template_gates", 0))
    n_ung = int(getattr(calc, "ung_template_gates", 0))
    n_cnot = int(getattr(calc, "feynman_xor_plane_gates", 0))

    return {
        "framework_id": "umg_ung_mapping",
        "label": "UMG-UNG mapping (optimized RPLA)",
        "gates": int(calc.gates),
        "garbages": int(calc.garbages),
        "ancilla_inputs": int(calc.ancilla_input_count),
        "quantum_cost": int(calc.quantumCost),
        "gate_mix": {
            "umg_templates": n_umg,
            "ung_templates": n_ung,
            "cnot_gates": n_cnot,
            "note": (
                "Template-weighted UMG/UNG AND plane + Feynman (CNOT) XOR plane. "
                "Quantum cost = CNOT ×1 + (UMG + UNG) ×5."
            ),
        },
        "calculation_report": report.getvalue().strip(),
    }
