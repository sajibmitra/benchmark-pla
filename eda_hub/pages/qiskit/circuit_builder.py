"""Build a Qiskit QuantumCircuit from an ESOP/RPLA AND/XOR plane."""
from __future__ import annotations

from typing import Any, Literal

from ._util import QiskitRealizationError, ensure_qiskit

AndStyle = Literal["toffoli", "umg_ung"]


def _primary_input_count(rpla: Any) -> int:
    if getattr(rpla, "totalLiterals", 0):
        return int(rpla.totalLiterals)
    widths = [len(getattr(p, "bitPattern", "") or "") for p in (rpla.products or [])]
    return max(widths) if widths else 0


def _product_literal_controls(product: Any) -> list[tuple[int, bool]]:
    """Return (input_index, needs_x_for_complemented) for each defined literal."""
    pattern = getattr(product, "bitPattern", "") or ""
    controls: list[tuple[int, bool]] = []
    for idx, ch in enumerate(pattern):
        if ch == "1":
            controls.append((idx, False))
        elif ch == "0":
            controls.append((idx, True))
    return controls


def _layout_sizes(rpla: Any) -> tuple[int, int, int, int, int]:
    n_in = _primary_input_count(rpla)
    products = list(rpla.products or [])
    functions = list(rpla.functions or [])
    n_prod = len(products)
    n_out = len(functions)
    if n_in <= 0 or n_prod <= 0 or n_out <= 0:
        raise QiskitRealizationError("ESOP plane is empty; cannot build Qiskit circuit")
    max_and_temps = 0
    for product in products:
        size = len(_product_literal_controls(product))
        max_and_temps = max(max_and_temps, max(0, size - 2))
    n_qubits = n_in + n_prod + n_out + max_and_temps
    return n_in, n_prod, n_out, max_and_temps, n_qubits


def _append_and_plane(
    qc: Any,
    *,
    rpla: Any,
    style: AndStyle,
    q_in0: int,
    q_prod0: int,
    q_temp0: int,
) -> dict[str, int]:
    """Map each ESOP product onto AND-plane gates (CCX or UMG/UNG)."""
    from .unitaries import umg_gate, ung_gate

    products = list(rpla.products or [])
    n_x = n_cx = n_ccx = n_umg = n_ung = intermediate_garbage = 0
    umg = umg_gate() if style == "umg_ung" else None
    ung = ung_gate() if style == "umg_ung" else None

    for pi, product in enumerate(products):
        controls = _product_literal_controls(product)
        prod_q = q_prod0 + pi
        if not controls:
            qc.x(prod_q)
            n_x += 1
            continue

        flipped: list[int] = []
        for lit_idx, complemented in controls:
            if complemented:
                qc.x(q_in0 + lit_idx)
                n_x += 1
                flipped.append(q_in0 + lit_idx)

        # Prefer UNG when every literal is complemented (NOR of positives after flips).
        use_ung = style == "umg_ung" and all(c for _, c in controls) and len(controls) >= 2

        def _and2(c0: int, c1: int, tgt: int) -> None:
            nonlocal n_ccx, n_umg, n_ung
            if style == "toffoli":
                qc.ccx(c0, c1, tgt)
                n_ccx += 1
            elif use_ung and ung is not None:
                qc.append(ung, [c0, c1, tgt])
                n_ung += 1
            else:
                assert umg is not None
                qc.append(umg, [c0, c1, tgt])
                n_umg += 1

        if len(controls) == 1:
            qc.cx(q_in0 + controls[0][0], prod_q)
            n_cx += 1
        else:
            c0 = q_in0 + controls[0][0]
            c1 = q_in0 + controls[1][0]
            if len(controls) == 2:
                _and2(c0, c1, prod_q)
            else:
                t0 = q_temp0
                _and2(c0, c1, t0)
                intermediate_garbage += 1
                cur = t0
                for k, (lit_idx, _) in enumerate(controls[2:], start=0):
                    nxt = prod_q if k == len(controls) - 3 else (q_temp0 + k + 1)
                    if nxt != prod_q:
                        intermediate_garbage += 1
                    _and2(cur, q_in0 + lit_idx, nxt)
                    cur = nxt

        for q in reversed(flipped):
            qc.x(q)
            n_x += 1

    return {
        "x_gates": n_x,
        "cnot_gates": n_cx,
        "toffoli_gates": n_ccx,
        "umg_templates": n_umg,
        "ung_templates": n_ung,
        "intermediate_garbage": intermediate_garbage,
    }


def _append_xor_plane(
    qc: Any,
    *,
    rpla: Any,
    q_prod0: int,
    q_out0: int,
    n_prod: int,
) -> int:
    n_cx = 0
    for fi, function in enumerate(rpla.functions or []):
        out_q = q_out0 + fi
        for prod_idx in getattr(function, "productsList", []) or []:
            if 0 <= int(prod_idx) < n_prod:
                qc.cx(q_prod0 + int(prod_idx), out_q)
                n_cx += 1
    return n_cx


def build_esop_cnot_toffoli_circuit(rpla: Any):
    """Realize AND/XOR planes as a Qiskit circuit with X, CX, and CCX only."""
    ensure_qiskit()
    from qiskit import QuantumCircuit

    n_in, n_prod, n_out, max_and_temps, n_qubits = _layout_sizes(rpla)
    q_in0 = 0
    q_prod0 = n_in
    q_out0 = n_in + n_prod
    q_temp0 = n_in + n_prod + n_out
    qc = QuantumCircuit(n_qubits, name="esop_cnot_toffoli")

    and_stats = _append_and_plane(
        qc,
        rpla=rpla,
        style="toffoli",
        q_in0=q_in0,
        q_prod0=q_prod0,
        q_temp0=q_temp0,
    )
    n_cx = and_stats["cnot_gates"] + _append_xor_plane(
        qc, rpla=rpla, q_prod0=q_prod0, q_out0=q_out0, n_prod=n_prod
    )

    meta = {
        "num_qubits": n_qubits,
        "num_inputs": n_in,
        "num_products": n_prod,
        "num_outputs": n_out,
        "num_and_temps": max_and_temps,
        "ancilla_inputs": n_prod + n_out + max_and_temps,
        "garbages": n_prod + and_stats["intermediate_garbage"],
        "x_gates": and_stats["x_gates"],
        "cnot_gates": n_cx,
        "toffoli_gates": and_stats["toffoli_gates"],
        "umg_templates": 0,
        "ung_templates": 0,
        "and_style": "toffoli",
    }
    return qc, meta


def build_esop_umg_ung_circuit(rpla: Any):
    """Realize AND/XOR planes with UMG/UNG templates + Feynman (CX) XOR."""
    ensure_qiskit()
    from qiskit import QuantumCircuit

    n_in, n_prod, n_out, max_and_temps, n_qubits = _layout_sizes(rpla)
    q_in0 = 0
    q_prod0 = n_in
    q_out0 = n_in + n_prod
    q_temp0 = n_in + n_prod + n_out
    qc = QuantumCircuit(n_qubits, name="esop_umg_ung")

    and_stats = _append_and_plane(
        qc,
        rpla=rpla,
        style="umg_ung",
        q_in0=q_in0,
        q_prod0=q_prod0,
        q_temp0=q_temp0,
    )
    n_cx = and_stats["cnot_gates"] + _append_xor_plane(
        qc, rpla=rpla, q_prod0=q_prod0, q_out0=q_out0, n_prod=n_prod
    )

    meta = {
        "num_qubits": n_qubits,
        "num_inputs": n_in,
        "num_products": n_prod,
        "num_outputs": n_out,
        "num_and_temps": max_and_temps,
        "ancilla_inputs": n_prod + n_out + max_and_temps,
        "garbages": n_prod + and_stats["intermediate_garbage"],
        "x_gates": and_stats["x_gates"],
        "cnot_gates": n_cx,
        "toffoli_gates": 0,
        "umg_templates": and_stats["umg_templates"],
        "ung_templates": and_stats["ung_templates"],
        "and_style": "umg_ung",
    }
    return qc, meta


def circuit_to_qiskit_source(qc: Any, *, max_lines: int = 400) -> str:
    """Render a QuantumCircuit as importable Qiskit Python (truncated if huge)."""
    ensure_qiskit()
    lines = [
        "from qiskit import QuantumCircuit",
        "from qiskit.circuit.library import UnitaryGate",
        f"qc = QuantumCircuit({qc.num_qubits}, name={qc.name!r})",
    ]
    truncated = False
    for idx, item in enumerate(qc.data):
        if idx >= max_lines:
            truncated = True
            break
        op = item.operation
        qs = ", ".join(str(qc.find_bit(q).index) for q in item.qubits)
        name = op.name
        if name == "x":
            lines.append(f"qc.x({qs})")
        elif name == "cx":
            lines.append(f"qc.cx({qs})")
        elif name == "ccx":
            lines.append(f"qc.ccx({qs})")
        elif name == "swap":
            lines.append(f"qc.swap({qs})")
        elif name in {"umg", "ung"}:
            lines.append(f"qc.append({name}_gate(), [{qs}])  # template")
        else:
            lines.append(f"qc.append({name!r}, [{qs}])")
    if truncated:
        lines.append(f"# … truncated ({len(qc.data) - max_lines} more instructions)")
    lines.append(f"# depth={qc.depth()}  ops={dict(qc.count_ops())}")
    return "\n".join(lines) + "\n"

