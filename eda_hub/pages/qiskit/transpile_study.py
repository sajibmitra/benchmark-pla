"""Comparative Qiskit transpile study for all four realization methodologies."""
from __future__ import annotations

from typing import Any

from ._util import (
    QiskitRealizationError,
    ensure_qiskit,
    gate_depth_for_names,
    ops_count,
    snapshot_rpla,
    total_gates,
)
from .circuit_builder import (
    build_esop_cnot_toffoli_circuit,
    build_esop_umg_ung_circuit,
    circuit_to_qiskit_source,
)
from .unitaries import umg_gate, ung_gate
from .zhou2026 import _linear_coupling, _zhou_cost

_DEFAULT_OPT_LEVEL = 2
_MAX_QUBITS_FULL_TRANSPILE = 96
_MAX_GATES_FULL_TRANSPILE = 8000
_MAX_QUBITS_LNN_TRANSPILE = 48
_MAX_GATES_LNN_TRANSPILE = 2000
_MAX_SOURCE_LINES = 250

QUANTUM_COST_FORMULA = {
    "standard_quantum": (
        "Σ(CX)+Σ(CCX) after qiskit.transpile(basis=[x,cx,ccx], optimization_level=2)"
    ),
    "umg_ung": (
        "Σ(CX)+5×Σ(UMG+UNG) after qiskit.transpile keeping UMG/UNG templates "
        "(optimization_level=2)"
    ),
    "gaur2024": (
        "FOM = qubit_width × Toffoli_depth on transpiled CX/CCX circuit "
        "(Gaur & Thapliyal, TVLSI 2024)"
    ),
    "zhou2026": (
        "C = T_adj + W_error×E on LNN-routed qiskit.transpile "
        "(Zhou et al., TVLSI 2026 EDDQC)"
    ),
}


def _can_full_transpile(qc: Any) -> bool:
    return (
        int(qc.num_qubits) <= _MAX_QUBITS_FULL_TRANSPILE
        and total_gates(ops_count(qc)) <= _MAX_GATES_FULL_TRANSPILE
    )


def _transpile_cx_ccx(qc: Any, *, optimization_level: int):
    from qiskit import transpile

    return transpile(
        qc,
        basis_gates=["x", "cx", "ccx", "swap"],
        optimization_level=optimization_level,
        seed_transpiler=42,
    )


def _transpile_umg_ung(qc: Any, *, optimization_level: int):
    from qiskit import transpile
    from qiskit.transpiler import Target

    n = int(qc.num_qubits)
    target = Target.from_configuration(
        basis_gates=["x", "cx", "umg", "ung", "swap"],
        num_qubits=n,
        custom_name_mapping={"umg": umg_gate(), "ung": ung_gate()},
    )
    return transpile(
        qc,
        target=target,
        optimization_level=optimization_level,
        seed_transpiler=42,
    )


def _transpile_lnn(qc: Any, *, optimization_level: int):
    from qiskit import transpile

    n = int(qc.num_qubits)
    return transpile(
        qc,
        coupling_map=_linear_coupling(n),
        basis_gates=["x", "cx", "ccx", "swap"],
        optimization_level=max(1, min(optimization_level, 2)),
        seed_transpiler=42,
    )


def _base_entry(
    *,
    framework_id: str,
    label: str,
    qc: Any,
    layout_meta: dict[str, Any],
    quantum_cost: int,
    gate_mix: dict[str, Any],
    transpile_note: str,
    optimization_level: int,
    transpiled: bool,
) -> dict[str, Any]:
    ops = ops_count(qc)
    return {
        "framework_id": framework_id,
        "label": label,
        "gates": total_gates(ops),
        "garbages": int(layout_meta.get("garbages", 0)),
        "ancilla_inputs": int(layout_meta.get("ancilla_inputs", 0)),
        "quantum_cost": int(quantum_cost),
        "gate_mix": gate_mix,
        "qiskit_num_qubits": int(qc.num_qubits),
        "qiskit_circuit_depth": int(qc.depth()),
        "qiskit_ops": ops,
        "qiskit_source": circuit_to_qiskit_source(qc, max_lines=_MAX_SOURCE_LINES),
        "transpile": {
            "applied": transpiled,
            "optimization_level": optimization_level,
            "note": transpile_note,
        },
    }


def _study_standard(qc0: Any, layout: dict[str, Any], *, opt: int) -> dict[str, Any]:
    transpiled = False
    qc = qc0
    note = "Logical CX/CCX ESOP circuit (transpile skipped: circuit too large)."
    if _can_full_transpile(qc0):
        try:
            qc = _transpile_cx_ccx(qc0, optimization_level=opt)
            transpiled = True
            note = (
                f"qiskit.transpile(basis_gates=[x,cx,ccx,swap], "
                f"optimization_level={opt}, seed_transpiler=42)."
            )
        except Exception as exc:  # noqa: BLE001
            note = f"Transpile failed ({exc}); reporting logical CX/CCX circuit."

    ops = ops_count(qc)
    cx = int(ops.get("cx", 0))
    ccx = int(ops.get("ccx", 0))
    return _base_entry(
        framework_id="standard_quantum",
        label="CNOT/Toffoli mapping (Qiskit transpile)",
        qc=qc,
        layout_meta=layout,
        quantum_cost=cx + ccx,
        gate_mix={
            "cnot_gates": cx,
            "toffoli_gates": ccx,
            "swap_gates": int(ops.get("swap", 0)),
            "circuit_depth": int(qc.depth()),
            "qubit_width": int(qc.num_qubits),
            "note": "Quantum cost = CX + CCX on the optimized Qiskit circuit.",
        },
        transpile_note=note,
        optimization_level=opt,
        transpiled=transpiled,
    )


def _study_umg_ung(qc0: Any, layout: dict[str, Any], *, opt: int) -> dict[str, Any]:
    transpiled = False
    qc = qc0
    note = "Logical UMG/UNG + CX circuit (transpile skipped: circuit too large)."
    if _can_full_transpile(qc0):
        try:
            qc = _transpile_umg_ung(qc0, optimization_level=opt)
            transpiled = True
            note = (
                f"qiskit.transpile with Target basis [x,cx,umg,ung,swap], "
                f"optimization_level={opt}, seed_transpiler=42."
            )
        except Exception as exc:  # noqa: BLE001
            note = f"Template-preserving transpile failed ({exc}); reporting logical circuit."

    ops = ops_count(qc)
    cx = int(ops.get("cx", 0))
    umg = int(ops.get("umg", 0))
    ung = int(ops.get("ung", 0))
    return _base_entry(
        framework_id="umg_ung_mapping",
        label="UMG-UNG mapping (Qiskit transpile)",
        qc=qc,
        layout_meta=layout,
        quantum_cost=cx + 5 * (umg + ung),
        gate_mix={
            "cnot_gates": cx,
            "umg_templates": umg,
            "ung_templates": ung,
            "swap_gates": int(ops.get("swap", 0)),
            "circuit_depth": int(qc.depth()),
            "qubit_width": int(qc.num_qubits),
            "note": "Quantum cost = CX×1 + (UMG+UNG)×5 on the optimized Qiskit circuit.",
        },
        transpile_note=note,
        optimization_level=opt,
        transpiled=transpiled,
    )


def _study_gaur(qc0: Any, layout: dict[str, Any], *, opt: int) -> dict[str, Any]:
    transpiled = False
    qc = qc0
    note = "Logical CX/CCX circuit for Gaur2024 FOM (transpile skipped: too large)."
    if _can_full_transpile(qc0):
        try:
            qc = _transpile_cx_ccx(qc0, optimization_level=opt)
            transpiled = True
            note = (
                f"qiskit.transpile(basis_gates=[x,cx,ccx,swap], "
                f"optimization_level={opt}) then FOM = width × Toffoli_depth."
            )
        except Exception as exc:  # noqa: BLE001
            note = f"Transpile failed ({exc}); FOM from logical circuit."

    ops = ops_count(qc)
    width = int(qc.num_qubits)
    toffoli_depth = gate_depth_for_names(qc, {"ccx"})
    cnot_depth = gate_depth_for_names(qc, {"cx"})
    fom = width * toffoli_depth
    return _base_entry(
        framework_id="gaur2024_qma",
        label="Gaur2024 CNOT/Toffoli FOM (Qiskit transpile)",
        qc=qc,
        layout_meta=layout,
        quantum_cost=int(fom),
        gate_mix={
            "cnot_gates": int(ops.get("cx", 0)),
            "toffoli_gates": int(ops.get("ccx", 0)),
            "cnot_depth": cnot_depth,
            "toffoli_depth": toffoli_depth,
            "qubit_width": width,
            "fom": fom,
            "circuit_depth": int(qc.depth()),
            "swap_gates": int(ops.get("swap", 0)),
            "note": "FOM = qubit_width × Toffoli_depth on the optimized Qiskit circuit.",
        },
        transpile_note=note,
        optimization_level=opt,
        transpiled=transpiled,
    )


def _bounded_lnn_swap_estimate(qc: Any) -> tuple[int, int]:
    """Distance-based LNN SWAP estimate with a hard cap to avoid pathological blow-ups."""
    from .zhou2026 import _estimate_lnn_swap_overhead

    swap_est, extra_depth = _estimate_lnn_swap_overhead(qc)
    n = max(1, int(qc.num_qubits))
    g = max(1, total_gates(ops_count(qc)))
    # At most ~n SWAPs per multi-qubit op on average for a linear map.
    cap = n * g
    if swap_est > cap:
        swap_est = cap
        extra_depth = min(extra_depth, cap)
    return int(swap_est), int(extra_depth)


def _zhou_entry(
    qc: Any,
    layout: dict[str, Any],
    *,
    opt: int,
    transpiled: bool,
    note: str,
) -> dict[str, Any]:
    ops = ops_count(qc)
    depth = int(qc.depth())
    two_q = int(ops.get("cx", 0)) + int(ops.get("ccx", 0)) + 3 * int(ops.get("swap", 0))
    cost = _zhou_cost(depth, two_q)
    return _base_entry(
        framework_id="zhou2026_edqqc",
        label="Zhou2026 EDDQC LNN (Qiskit transpile)",
        qc=qc,
        layout_meta=layout,
        quantum_cost=int(round(cost["C"])),
        gate_mix={
            "cnot_gates": int(ops.get("cx", 0)),
            "toffoli_gates": int(ops.get("ccx", 0)),
            "swap_gates": int(ops.get("swap", 0)),
            "circuit_depth": depth,
            "lnn_transpile": transpiled,
            "T_adj": round(cost["T_adj"], 4),
            "E": round(cost["E"], 6),
            "C": round(cost["C"], 4),
            "qubit_width": int(qc.num_qubits),
            "note": "C = T_adj + W_error×E on the LNN-routed Qiskit circuit.",
        },
        transpile_note=note,
        optimization_level=opt,
        transpiled=transpiled,
    )


def _study_zhou(qc0: Any, layout: dict[str, Any], *, opt: int) -> dict[str, Any]:
    from qiskit import transpile

    can_lnn = (
        int(qc0.num_qubits) <= _MAX_QUBITS_LNN_TRANSPILE
        and total_gates(ops_count(qc0)) <= _MAX_GATES_LNN_TRANSPILE
    )
    if not can_lnn:
        swap_est, extra_depth = _bounded_lnn_swap_estimate(qc0)
        ops = ops_count(qc0)
        ops["swap"] = int(ops.get("swap", 0)) + swap_est
        depth = int(qc0.depth()) + extra_depth
        two_q = int(ops.get("cx", 0)) + int(ops.get("ccx", 0)) + 3 * int(ops.get("swap", 0))
        cost = _zhou_cost(depth, two_q)
        return _base_entry(
            framework_id="zhou2026_edqqc",
            label="Zhou2026 EDDQC LNN (Qiskit)",
            qc=qc0,
            layout_meta=layout,
            quantum_cost=int(round(cost["C"])),
            gate_mix={
                "cnot_gates": int(ops.get("cx", 0)),
                "toffoli_gates": int(ops.get("ccx", 0)),
                "swap_gates": int(ops.get("swap", 0)),
                "circuit_depth": depth,
                "lnn_transpile": False,
                "T_adj": round(cost["T_adj"], 4),
                "E": round(cost["E"], 6),
                "C": round(cost["C"], 4),
                "qubit_width": int(qc0.num_qubits),
                "note": "Circuit exceeds full-transpile limits; LNN SWAP estimate applied.",
            },
            transpile_note="Skipped coupling-map transpile (size limit); distance-based SWAP estimate.",
            optimization_level=opt,
            transpiled=False,
        )

    # Prefer LNN routing on CX/CCX; if that fails, decompose CCX→CX then route.
    level = max(1, min(opt, 2))
    try:
        routed = _transpile_lnn(qc0, optimization_level=level)
        return _zhou_entry(
            routed,
            layout,
            opt=opt,
            transpiled=True,
            note=(
                f"qiskit.transpile(coupling_map=LNN, basis_gates=[x,cx,ccx,swap], "
                f"optimization_level={level}, seed_transpiler=42)."
            ),
        )
    except Exception:
        pass

    try:
        n = int(qc0.num_qubits)
        decomposed = transpile(
            qc0,
            basis_gates=["x", "cx", "h", "t", "tdg", "swap"],
            optimization_level=level,
            seed_transpiler=42,
        )
        routed = transpile(
            decomposed,
            coupling_map=_linear_coupling(n),
            basis_gates=["x", "cx", "h", "t", "tdg", "swap"],
            optimization_level=level,
            seed_transpiler=42,
        )
        return _zhou_entry(
            routed,
            layout,
            opt=opt,
            transpiled=True,
            note=(
                f"CCX decomposed then qiskit.transpile(coupling_map=LNN, "
                f"basis_gates=[x,cx,h,t,tdg,swap], optimization_level={level})."
            ),
        )
    except Exception:
        swap_est, extra_depth = _bounded_lnn_swap_estimate(qc0)
        ops = ops_count(qc0)
        ops["swap"] = int(ops.get("swap", 0)) + swap_est
        depth = int(qc0.depth()) + extra_depth
        two_q = int(ops.get("cx", 0)) + int(ops.get("ccx", 0)) + 3 * int(ops.get("swap", 0))
        cost = _zhou_cost(depth, two_q)
        return _base_entry(
            framework_id="zhou2026_edqqc",
            label="Zhou2026 EDDQC LNN (Qiskit)",
            qc=qc0,
            layout_meta=layout,
            quantum_cost=int(round(cost["C"])),
            gate_mix={
                "cnot_gates": int(ops.get("cx", 0)),
                "toffoli_gates": int(ops.get("ccx", 0)),
                "swap_gates": int(ops.get("swap", 0)),
                "circuit_depth": depth,
                "lnn_transpile": False,
                "T_adj": round(cost["T_adj"], 4),
                "E": round(cost["E"], 6),
                "C": round(cost["C"], 4),
                "qubit_width": int(qc0.num_qubits),
                "note": "Estimated LNN SWAP overhead; C = T_adj + W_error×E.",
            },
            transpile_note="LNN coupling-map transpile failed; used distance-based SWAP estimate.",
            optimization_level=opt,
            transpiled=False,
        )


def run_transpile_comparative_study(
    rpla: Any,
    *,
    optimization_level: int = _DEFAULT_OPT_LEVEL,
) -> dict[str, Any]:
    """
    Build Qiskit circuits for all four methodologies, run ``qiskit.transpile``,
    and return comparable metrics + Qiskit source for each.
    """
    ensure_qiskit()
    opt = max(0, min(3, int(optimization_level)))
    snap = snapshot_rpla(rpla, include_total_literals=True)

    try:
        qc_cx, layout_cx = build_esop_cnot_toffoli_circuit(snap)
        qc_umg, layout_umg = build_esop_umg_ung_circuit(snap)
    except QiskitRealizationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise QiskitRealizationError(f"Failed to build ESOP Qiskit circuits: {exc}") from exc

    standard = _study_standard(qc_cx, layout_cx, opt=opt)
    umg = _study_umg_ung(qc_umg, layout_umg, opt=opt)
    gaur = _study_gaur(qc_cx, layout_cx, opt=opt)
    zhou = _study_zhou(qc_cx, layout_cx, opt=opt)

    return {
        "optimization_level": opt,
        "quantum_cost_formula": dict(QUANTUM_COST_FORMULA),
        "realizations": {
            "standard_quantum": standard,
            "umg_ung": umg,
            "gaur2024": gaur,
            "zhou2026": zhou,
        },
        "summary": {
            "qubits": {
                "standard_quantum": standard["qiskit_num_qubits"],
                "umg_ung": umg["qiskit_num_qubits"],
                "gaur2024": gaur["qiskit_num_qubits"],
                "zhou2026": zhou["qiskit_num_qubits"],
            },
            "depth": {
                "standard_quantum": standard["qiskit_circuit_depth"],
                "umg_ung": umg["qiskit_circuit_depth"],
                "gaur2024": gaur["qiskit_circuit_depth"],
                "zhou2026": zhou["qiskit_circuit_depth"],
            },
            "quantum_cost": {
                "standard_quantum": standard["quantum_cost"],
                "umg_ung": umg["quantum_cost"],
                "gaur2024": gaur["quantum_cost"],
                "zhou2026": zhou["quantum_cost"],
            },
        },
    }


__all__ = [
    "QUANTUM_COST_FORMULA",
    "run_transpile_comparative_study",
]
