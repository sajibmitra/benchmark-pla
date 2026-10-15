"""Zhou2026 EDDQC LNN cost — measured from a Qiskit LNN-routed circuit."""
from __future__ import annotations

from typing import Any

from ._util import ensure_qiskit, ops_count, snapshot_rpla, total_gates
from .circuit_builder import build_esop_cnot_toffoli_circuit

_ZHOU_W_ERROR = 100.0
_ZHOU_TWO_QUBIT_ERROR = 0.01
_ZHOU_LNN_GATE_LIMIT = 8000
_ZHOU_LNN_QUBIT_LIMIT = 96


def _linear_coupling(n: int) -> list[list[int]]:
    edges: list[list[int]] = []
    for i in range(n - 1):
        edges.append([i, i + 1])
        edges.append([i + 1, i])
    return edges


def _zhou_cost(depth: int, two_qubit_gates: int, w_error: float = _ZHOU_W_ERROR) -> dict[str, float]:
    """EDDQC combined cost C = T_adj + W_error × E with T_adj = T / (1 − E)."""
    e_gate = _ZHOU_TWO_QUBIT_ERROR
    survival = (1.0 - e_gate) ** max(0, two_qubit_gates)
    e_total = min(0.5, 1.0 - survival)
    t = float(max(1, depth))
    t_adj = t / max(1e-9, (1.0 - e_total))
    c = t_adj + w_error * e_total
    return {"T": t, "E": e_total, "T_adj": t_adj, "W_error": w_error, "C": c}


def _estimate_lnn_swap_overhead(qc) -> tuple[int, int]:
    swap_count = 0
    extra_depth = 0
    for item in qc.data:
        qubits = [qc.find_bit(q).index for q in item.qubits]
        if len(qubits) < 2:
            continue
        span = max(qubits) - min(qubits)
        needed = max(0, span - (len(qubits) - 1))
        swap_count += needed
        extra_depth += needed
    return swap_count, extra_depth


def _zhou_result(
    *,
    ops: dict[str, int],
    depth: int,
    layout_meta: dict[str, Any],
    lnn_transpile: bool,
    note: str,
) -> dict[str, Any]:
    two_q = int(ops.get("cx", 0)) + int(ops.get("ccx", 0)) + 3 * int(ops.get("swap", 0))
    cost = _zhou_cost(depth, two_q)
    return {
        "framework_id": "zhou2026_edqqc",
        "label": "Zhou2026 EDDQC LNN (Qiskit)",
        "gates": total_gates(ops),
        "garbages": int(layout_meta.get("garbages", 0)),
        "ancilla_inputs": int(layout_meta.get("ancilla_inputs", 0)),
        "quantum_cost": int(round(cost["C"])),
        "gate_mix": {
            "cnot_gates": int(ops.get("cx", 0)),
            "toffoli_gates": int(ops.get("ccx", 0)),
            "swap_gates": int(ops.get("swap", 0)),
            "circuit_depth": int(depth),
            "lnn_transpile": lnn_transpile,
            "T_adj": round(cost["T_adj"], 4),
            "E": round(cost["E"], 6),
            "C": round(cost["C"], 4),
            "note": note,
        },
        "qiskit_layout": layout_meta,
        "qiskit_num_qubits": int(layout_meta.get("num_qubits", 0)),
        "qiskit_circuit_depth": int(depth),
    }


def calculate_zhou2026_cost(rpla: Any) -> dict[str, Any]:
    """
    Realization 4: Zhou2026 EDDQC methodology (TVLSI 2026).

    Builds a Qiskit ESOP circuit, routes to LNN (transpile or SWAP estimate),
    and reports quantum_cost = round(C) where C = T_adj + W_error×E.
    """
    ensure_qiskit()
    from qiskit import transpile

    snap = snapshot_rpla(rpla, include_total_literals=True)
    qc, layout_meta = build_esop_cnot_toffoli_circuit(snap)
    ops0 = ops_count(qc)
    n = int(qc.num_qubits)
    can_transpile = n <= _ZHOU_LNN_QUBIT_LIMIT and total_gates(ops0) <= _ZHOU_LNN_GATE_LIMIT

    if can_transpile:
        try:
            routed = transpile(
                qc,
                coupling_map=_linear_coupling(n),
                basis_gates=["cx", "ccx", "x", "swap"],
                optimization_level=1,
                seed_transpiler=42,
            )
            return _zhou_result(
                ops=ops_count(routed),
                depth=int(routed.depth()),
                layout_meta=layout_meta,
                lnn_transpile=True,
                note=(
                    "Qiskit transpile onto linear nearest-neighbor coupling (EDDQC-style). "
                    "Quantum cost = round(C), C = T_adj + W_error×E (Zhou et al., TVLSI 2026)."
                ),
            )
        except Exception:
            pass

    swap_est, extra_depth = _estimate_lnn_swap_overhead(qc)
    ops = dict(ops0)
    ops["swap"] = int(ops.get("swap", 0)) + swap_est
    return _zhou_result(
        ops=ops,
        depth=int(qc.depth()) + extra_depth,
        layout_meta=layout_meta,
        lnn_transpile=False,
        note=(
            "Qiskit ESOP circuit with estimated LNN SWAP overhead. "
            "Quantum cost = round(C), C = T_adj + W_error×E (Zhou et al., TVLSI 2026 EDDQC)."
        ),
    )
