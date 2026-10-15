"""Gaur2024 resource vector on a Qiskit CX/CCX circuit.

Table I of Gaur and Thapliyal, TVLSI 2024, reports CNOT count, CNOT depth,
Toffoli count, Toffoli depth, and qubit width for the modulo-(2^n+1) adders.
Fig. 5 defines FOM = circuit width × Toffoli depth. NMED is a device
measurement and is not computed here. The QMA1–QMA4 adder is not rebuilt;
these factors are read from the same ESOP CX/CCX netlist.
"""
from __future__ import annotations

from typing import Any

from ._util import gate_depth_for_names, ops_count, snapshot_rpla, total_gates
from .circuit_builder import build_esop_cnot_toffoli_circuit


def calculate_gaur2024_cost(rpla: Any) -> dict[str, Any]:
    """
    Realization 3: Gaur2024 resource accounting (TVLSI 2024, Table I and Fig. 5).

    Builds a Qiskit X/CX/CCX circuit and reports CNOT count, CNOT depth,
    Toffoli count, Toffoli depth, qubit width, and the derived
    FOM = qubit_width × Toffoli_depth. ``quantum_cost`` is that FOM.
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
                "Gaur Table I factors on the Qiskit X/CX/CCX ESOP circuit: "
                "CNOT count, CNOT depth, Toffoli count, Toffoli depth, and width. "
                "FOM = width × Toffoli_depth (Fig. 5). NMED is not measured."
            ),
        },
        "qiskit_layout": layout_meta,
        "qiskit_num_qubits": width,
        "qiskit_circuit_depth": int(qc.depth()),
    }
