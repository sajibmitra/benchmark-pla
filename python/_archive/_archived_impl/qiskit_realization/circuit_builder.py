"""Build a Qiskit QuantumCircuit from an ESOP/RPLA AND/XOR plane."""
from __future__ import annotations

from typing import Any

from ._util import QiskitRealizationError, ensure_qiskit


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


def build_esop_cnot_toffoli_circuit(rpla: Any):
    """Realize AND/XOR planes as a Qiskit circuit with X, CX, and CCX only."""
    ensure_qiskit()
    from qiskit import QuantumCircuit

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

    q_in0 = 0
    q_prod0 = n_in
    q_out0 = n_in + n_prod
    q_temp0 = n_in + n_prod + n_out
    n_qubits = q_temp0 + max_and_temps
    qc = QuantumCircuit(n_qubits, name="esop_cnot_toffoli")

    n_x = n_cx = n_ccx = 0
    intermediate_garbage = 0

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

        if len(controls) == 1:
            qc.cx(q_in0 + controls[0][0], prod_q)
            n_cx += 1
        else:
            c0 = q_in0 + controls[0][0]
            c1 = q_in0 + controls[1][0]
            if len(controls) == 2:
                qc.ccx(c0, c1, prod_q)
                n_ccx += 1
            else:
                t0 = q_temp0
                qc.ccx(c0, c1, t0)
                n_ccx += 1
                intermediate_garbage += 1
                cur = t0
                for k, (lit_idx, _) in enumerate(controls[2:], start=0):
                    nxt = prod_q if k == len(controls) - 3 else (q_temp0 + k + 1)
                    if nxt != prod_q:
                        intermediate_garbage += 1
                    qc.ccx(cur, q_in0 + lit_idx, nxt)
                    n_ccx += 1
                    cur = nxt

        for q in reversed(flipped):
            qc.x(q)
            n_x += 1

    for fi, function in enumerate(functions):
        out_q = q_out0 + fi
        for prod_idx in getattr(function, "productsList", []) or []:
            if 0 <= int(prod_idx) < n_prod:
                qc.cx(q_prod0 + int(prod_idx), out_q)
                n_cx += 1

    meta = {
        "num_qubits": n_qubits,
        "num_inputs": n_in,
        "num_products": n_prod,
        "num_outputs": n_out,
        "num_and_temps": max_and_temps,
        "ancilla_inputs": n_prod + n_out + max_and_temps,
        "garbages": n_prod + intermediate_garbage,
        "x_gates": n_x,
        "cnot_gates": n_cx,
        "toffoli_gates": n_ccx,
    }
    return qc, meta
