"""Zhou2026 EDDQC strategy selection on a Qiskit CX/CCX circuit.

Algorithm 1 of Zhou et al., TVLSI 2026, chooses, for each interaction, the
cheapest of a SWAP path, a quantum-switch interaction, and gate teleportation.
On a line the least-cost SWAP path is the unique interval, which is what
Dijkstra returns. Operation times and error rates are Table I of that paper.
The combined cost of one operation is

    C = T_adj + W_error * E,    T_adj = T / (1 - E).

The paper does not publish a numeric W_error. W_error = 1 keeps C in the
microseconds of Table I. There is no circuit-level error clamp.

Qubits sit on one LNN line split into QPUs of 10. Experiment 2 of the paper
treats 20% of each QPU as dangling communication qubits; two endpoints of a
10-qubit segment are that share. A SWAP whose edge crosses a segment boundary
uses the cross-group SWAP row. CCX has no Table I time, so a local Toffoli
adds no microseconds; its routing decision is still scored.
"""
from __future__ import annotations

from typing import Any

from ._util import ensure_qiskit, ops_count, snapshot_rpla, total_gates
from .circuit_builder import build_esop_cnot_toffoli_circuit

# Table I, Zhou et al., TVLSI 2026. Time in microseconds, error per operation.
_TABLE_I = {
    "swap": (0.235, 0.007),
    "cross_swap": (0.5, 0.035),
    "move": (0.1, 0.003),
    "teleport_state": (0.5, 0.020),
    "teleport_gate": (0.6, 0.018),
    "switch": (0.4, 0.015),
    "cx": (0.235, 0.007),
    "rz": (0.02, 0.0001),
}
# Unpublished in the paper; unit weight so C stays in microseconds.
_ZHOU_W_ERROR = 1.0
# Two endpoints / 10 qubits = 20% dangling share (Zhou Experiment 2).
_QPU_WIDTH = 10
_ZHOU_LNN_GATE_LIMIT = 8000
_ZHOU_LNN_QUBIT_LIMIT = 96


def _linear_coupling(n: int) -> list[list[int]]:
    edges: list[list[int]] = []
    for i in range(n - 1):
        edges.append([i, i + 1])
        edges.append([i + 1, i])
    return edges


def _op_cost(kind: str) -> tuple[float, float, float]:
    """Return (C, T_adj, E) for one Table I operation."""
    time_us, error = _TABLE_I[kind]
    t_adj = time_us / (1.0 - error)
    cost = t_adj + _ZHOU_W_ERROR * error
    return cost, t_adj, error


def _crosses_group(left: int) -> bool:
    """True when the LNN edge between ``left`` and ``left + 1`` leaves a QPU."""
    return left // _QPU_WIDTH != (left + 1) // _QPU_WIDTH


def _swap_path(qubits: list[int]) -> tuple[float, float, int, int]:
    """SWAP cost to pack ``qubits`` into a contiguous LNN block.

    Returns (C, T_adj, n_swap, n_cross).
    """
    lo = min(qubits)
    hi = max(qubits)
    occupied = set(qubits)
    cost = 0.0
    t_adj = 0.0
    n_swap = 0
    n_cross = 0
    for pos in range(lo + 1, hi):
        if pos in occupied:
            continue
        kind = "cross_swap" if _crosses_group(pos - 1) else "swap"
        c, ta, _e = _op_cost(kind)
        cost += c
        t_adj += ta
        n_swap += 1
        if kind == "cross_swap":
            n_cross += 1
    return cost, t_adj, n_swap, n_cross


def _empty_account() -> dict[str, float]:
    return {
        "C": 0.0,
        "T_adj": 0.0,
        "n_swap": 0.0,
        "n_cross": 0.0,
        "n_switch": 0.0,
        "n_teleport": 0.0,
        "added_depth": 0.0,
        "n_cx": 0.0,
        "n_ccx": 0.0,
    }


def _add_native(acc: dict[str, float], name: str) -> None:
    if name == "cx":
        c, ta, _e = _op_cost("cx")
        acc["C"] += c
        acc["T_adj"] += ta
        acc["n_cx"] += 1
    elif name == "ccx":
        acc["n_ccx"] += 1


def account_eddqc(qc: Any) -> dict[str, Any]:
    """Algorithm 1 accounting on the logical circuit, without inserting gates.

    For every multi-qubit gate that is not already a contiguous block, compare
    the LNN SWAP path with one switch interaction and one gate teleportation
    and keep the minimum. Local CX gates add the CX* row.
    """
    acc = _empty_account()
    base_gates = total_gates(ops_count(qc))
    base_depth = int(qc.depth())
    for item in qc.data:
        name = item.operation.name
        qubits = [qc.find_bit(q).index for q in item.qubits]
        if len(qubits) < 2:
            continue
        span = max(qubits) - min(qubits)
        if span <= len(qubits) - 1:
            _add_native(acc, name)
            continue
        swap_c, swap_ta, n_swap, n_cross = _swap_path(qubits)
        switch_c, switch_ta, _e = _op_cost("switch")
        tele_c, tele_ta, _e = _op_cost("teleport_gate")
        choice = min(
            (("swap", swap_c, swap_ta), ("switch", switch_c, switch_ta), ("teleport", tele_c, tele_ta)),
            key=lambda row: row[1],
        )
        kind, cost, t_adj = choice
        acc["C"] += cost
        acc["T_adj"] += t_adj
        if kind == "swap":
            acc["n_swap"] += n_swap
            acc["n_cross"] += n_cross
            acc["added_depth"] += n_swap
        elif kind == "switch":
            acc["n_switch"] += 1
            acc["added_depth"] += 1
        else:
            acc["n_teleport"] += 1
            acc["added_depth"] += 1
        _add_native(acc, name)
    return _pack(acc, base_gates=base_gates, base_depth=base_depth, routed=False)


def score_routed_circuit(qc: Any) -> dict[str, Any]:
    """Score a circuit already routed onto the LNN line, using Table I per gate.

    Adjacent SWAPs use the Swap or Cross-Group Swap row. No error is clamped.
    """
    acc = _empty_account()
    for item in qc.data:
        name = item.operation.name
        qubits = [qc.find_bit(q).index for q in item.qubits]
        if name == "swap" and len(qubits) == 2:
            left = min(qubits)
            kind = "cross_swap" if abs(qubits[0] - qubits[1]) == 1 and _crosses_group(left) else "swap"
            if abs(qubits[0] - qubits[1]) != 1 and qubits[0] // _QPU_WIDTH != qubits[1] // _QPU_WIDTH:
                kind = "cross_swap"
            c, ta, _e = _op_cost(kind)
            acc["C"] += c
            acc["T_adj"] += ta
            acc["n_swap"] += 1
            if kind == "cross_swap":
                acc["n_cross"] += 1
            continue
        if name == "cx" and len(qubits) == 2 and abs(qubits[0] - qubits[1]) != 1:
            # A non-adjacent CX that routing left in place still needs a decision.
            swap_c, swap_ta, n_swap, n_cross = _swap_path(qubits)
            switch_c, switch_ta, _e = _op_cost("switch")
            tele_c, tele_ta, _e = _op_cost("teleport_gate")
            kind, cost, t_adj = min(
                (("swap", swap_c, swap_ta), ("switch", switch_c, switch_ta), ("teleport", tele_c, tele_ta)),
                key=lambda row: row[1],
            )
            acc["C"] += cost
            acc["T_adj"] += t_adj
            if kind == "swap":
                acc["n_swap"] += n_swap
                acc["n_cross"] += n_cross
                acc["added_depth"] += n_swap
            elif kind == "switch":
                acc["n_switch"] += 1
                acc["added_depth"] += 1
            else:
                acc["n_teleport"] += 1
                acc["added_depth"] += 1
        _add_native(acc, name)
    return _pack(
        acc,
        base_gates=total_gates(ops_count(qc)),
        base_depth=int(qc.depth()),
        routed=True,
    )


def _pack(
    acc: dict[str, float],
    *,
    base_gates: int,
    base_depth: int,
    routed: bool,
) -> dict[str, Any]:
    extra = int(acc["n_swap"] + acc["n_switch"] + acc["n_teleport"])
    # Routed circuits already contain their SWAPs in ``base_gates``.
    gates = base_gates if routed else base_gates + extra
    depth = base_depth if routed else base_depth + int(acc["added_depth"])
    if routed:
        depth = base_depth + int(acc["added_depth"])
    return {
        "gates": int(gates),
        "depth": int(depth),
        "swap_gates": int(acc["n_swap"]),
        "cross_group_swaps": int(acc["n_cross"]),
        "switch_ops": int(acc["n_switch"]),
        "teleport_ops": int(acc["n_teleport"]),
        "cnot_gates": int(acc["n_cx"]),
        "toffoli_gates": int(acc["n_ccx"]),
        "C": round(acc["C"], 4),
        "T_adj": round(acc["T_adj"], 4),
        "W_error": _ZHOU_W_ERROR,
        "routed": routed,
    }


def _result_from_account(
    account: dict[str, Any],
    layout_meta: dict[str, Any],
    *,
    note: str,
) -> dict[str, Any]:
    return {
        "framework_id": "zhou2026_edqqc",
        "label": "Zhou2026 EDDQC (Qiskit)",
        "gates": int(account["gates"]),
        "garbages": int(layout_meta.get("garbages", 0)),
        "ancilla_inputs": int(layout_meta.get("ancilla_inputs", 0)),
        "quantum_cost": int(round(account["C"])),
        "gate_mix": {
            "cnot_gates": int(account["cnot_gates"]),
            "toffoli_gates": int(account["toffoli_gates"]),
            "swap_gates": int(account["swap_gates"]),
            "cross_group_swaps": int(account["cross_group_swaps"]),
            "switch_ops": int(account["switch_ops"]),
            "teleport_ops": int(account["teleport_ops"]),
            "circuit_depth": int(account["depth"]),
            "lnn_transpile": bool(account["routed"]),
            "T_adj": account["T_adj"],
            "W_error": account["W_error"],
            "C": account["C"],
            "qubit_width": int(layout_meta.get("num_qubits", 0)),
            "note": note,
        },
        "qiskit_layout": layout_meta,
        "qiskit_num_qubits": int(layout_meta.get("num_qubits", 0)),
        "qiskit_circuit_depth": int(account["depth"]),
    }


def calculate_zhou2026_cost(rpla: Any) -> dict[str, Any]:
    """
    Realization 4: Zhou2026 EDDQC (TVLSI 2026, Algorithm 1 and Table I).

    Small circuits are routed with ``qiskit.transpile`` on the LNN coupling
    map and scored gate by gate. Larger circuits use the swap-versus-switch
    decision on the logical line. ``quantum_cost`` is round(C) in microseconds.
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
            try:
                routed = transpile(
                    qc,
                    coupling_map=_linear_coupling(n),
                    basis_gates=["cx", "ccx", "x", "swap"],
                    optimization_level=1,
                    seed_transpiler=42,
                )
            except Exception:
                decomposed = transpile(
                    qc,
                    basis_gates=["x", "cx", "h", "t", "tdg", "swap"],
                    optimization_level=1,
                    seed_transpiler=42,
                )
                routed = transpile(
                    decomposed,
                    coupling_map=_linear_coupling(n),
                    basis_gates=["x", "cx", "h", "t", "tdg", "swap"],
                    optimization_level=1,
                    seed_transpiler=42,
                )
            account = score_routed_circuit(routed)
            return _result_from_account(
                account,
                layout_meta,
                note=(
                    "qiskit.transpile on the LNN map, then Table I costs per gate. "
                    "C = T/(1-E) + W_error×E with W_error = 1."
                ),
            )
        except Exception:
            pass
    account = account_eddqc(qc)
    return _result_from_account(
        account,
        layout_meta,
        note=(
            "Algorithm 1 on the LNN line: min(SWAP path, switch, gate teleportation). "
            "Table I times; W_error = 1; no error clamp."
        ),
    )
