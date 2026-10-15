"""Gaur2024 CNOT/Toffoli FOM — measured from a realized Qiskit QuantumCircuit."""
from __future__ import annotations

from typing import Any

from ._util import gate_depth_for_names, ops_count, snapshot_rpla, total_gates
from .circuit_builder import build_esop_cnot_toffoli_circuit


def calculate_gaur2024_cost(rpla: Any) -> dict[str, Any]:
    """
    Realization 3: Gaur2024 methodology (TVLSI 2024).

    Builds a Qiskit X/CX/CCX circuit for the ESOP planes and reports
    quantum_cost = FOM = qubit_width × Toffoli_depth.
    """
    snap = snapshot_rpla(rpla, include_total_literals=True)
    qc, layout_meta = build_esop_cnot_toffoli_circuit(snap)
    ops = ops_count(qc)
    cnot = int(ops.get("cx", 0))
    toffoli = int(ops.get("ccx", 0))
    width = int(qc.num_qubits)
    toffoli_depth = gate_depth_for_names(qc, {"ccx"})
    cnot_depth = gate_depth_for_names(qc, {"cx"})
    fom = width * toffoli_depth

    return {
        "framework_id": "gaur2024_qma",
        "label": "Gaur2024 CNOT/Toffoli FOM (Qiskit)",
        "gates": total_gates(ops),
        "garbages": int(layout_meta.get("garbages", 0)),
        "ancilla_inputs": int(layout_meta.get("ancilla_inputs", 0)),
        "quantum_cost": int(fom),
        "gate_mix": {
            "cnot_gates": cnot,
            "toffoli_gates": toffoli,
            "cnot_depth": cnot_depth,
            "toffoli_depth": toffoli_depth,
            "qubit_width": width,
            "fom": fom,
            "circuit_depth": int(qc.depth()),
            "note": (
                "Qiskit QuantumCircuit (X/CX/CCX) realizing the ESOP AND/XOR planes. "
                "Quantum cost = FOM = qubit_width × Toffoli_depth (Gaur & Thapliyal, TVLSI 2024)."
            ),
        },
        "qiskit_layout": layout_meta,
        "qiskit_num_qubits": width,
        "qiskit_circuit_depth": int(qc.depth()),
    }
