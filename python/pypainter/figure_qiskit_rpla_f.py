#!/usr/bin/env python3
"""Bennett-style reversible embedding of sample function F (Eq. boolean_functions).

Two exports:
  * qiskit_func_f_circuit.{pdf,png} — ESOP multi-controlled X (compact).
  * qiskit_func_f_umg_feynman.{pdf,png} — AND plane via UMG/UNG macros, XOR via Feynman (CNOT).

Run: python3 qiskit_rpla_func_f.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit.library import UnitaryGate
from qiskit.quantum_info import Statevector

OUT_DIR = Path(__file__).resolve().parent / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _umg_classic(q0: int, q1: int, q2: int) -> tuple[int, int, int]:
    """Classical map for UMG on wires (q0,q1,q2) = (a,b,c): (p,q,r)=(a, b⊕c, ab⊕a'c)."""
    a, b, c = q0, q1, q2
    p, q, r = a, b ^ c, (a & b) ^ ((1 - a) & c)
    return p, q, r


def _ung_classic(q0: int, q1: int, q2: int) -> tuple[int, int, int]:
    """UNG: (p,q,r)=(a, b, (a∨b)⊕c)."""
    a, b, c = q0, q1, q2
    p, q, r = a, b, ((a | b) & 1) ^ c
    return p, q, r


def _perm_matrix_3q(f_classic) -> np.ndarray:
    """8×8 permutation for three qubits with index i = q0 + 2*q1 + 4*q2 (Qiskit tensor order)."""
    p = np.zeros((8, 8), dtype=complex)
    for i in range(8):
        b0, b1, b2 = i & 1, (i >> 1) & 1, (i >> 2) & 1
        o0, o1, o2 = f_classic(b0, b1, b2)
        j = o0 + 2 * o1 + 4 * o2
        p[j, i] = 1.0
    return p


UMG_MATRIX = _perm_matrix_3q(_umg_classic)
UNG_MATRIX = _perm_matrix_3q(_ung_classic)


def umg_gate() -> UnitaryGate:
    return UnitaryGate(UMG_MATRIX, label="UMG")


def ung_gate() -> UnitaryGate:
    return UnitaryGate(UNG_MATRIX, label="UNG")


def build_func_f_circuit() -> QuantumCircuit:
    """ESOP form with multi-controlled X (same semantics as earlier version)."""
    ra = QuantumRegister(1, "|a⟩")
    rb = QuantumRegister(1, "|b⟩")
    rc = QuantumRegister(1, "|c⟩")
    outs = QuantumRegister(5, "f")
    qc = QuantumCircuit(ra, rb, rc, outs, name="F (ESOP mcx)")
    a, b, c = ra[0], rb[0], rc[0]
    f = list(outs)

    qc.mcx([a, b, c], f[0], ctrl_state=1)
    for cs in (5, 7, 4):
        qc.mcx([a, b, c], f[1], ctrl_state=cs)
    qc.mcx([a, b, c], f[2], ctrl_state=1)
    qc.mcx([b, c], f[2], ctrl_state=1)
    for cs in (5, 7):
        qc.mcx([a, b, c], f[3], ctrl_state=cs)
    for cs in (2, 1, 3, 7):
        qc.mcx([a, b, c], f[4], ctrl_state=cs)

    return qc


def _prepare_literal(qc: QuantumCircuit, src, anc, positive: bool) -> None:
    qc.cx(src, anc)
    if not positive:
        qc.x(anc)


def _unprepare_literal(qc: QuantumCircuit, src, anc, positive: bool) -> None:
    if not positive:
        qc.x(anc)
    qc.cx(src, anc)


def _minterm_polarities(m_idx: int) -> tuple[bool, bool, bool]:
    """Minterm index m = a + 2b + 4c (Qiskit ctrl_state order); return want positive literal on each wire."""
    a, b, c = m_idx & 1, (m_idx >> 1) & 1, (m_idx >> 2) & 1
    return bool(a), bool(b), bool(c)


def build_func_f_umg_feynman() -> QuantumCircuit:
    """
    Bennett-style: for each active minterm, copy literals, build the product on ancillae
    with UMG (and UNG for the a'b' factor in minterm 4 via (a∨b)' = a'b' with XOR-1),
    XOR into outputs with CNOT (Feynman), then uncompute.

    Minterm index m = a + 2b + 4c matches multi-controlled X ctrl_state in the ESOP circuit.
    """
    ra = QuantumRegister(1, "|a⟩")
    rb = QuantumRegister(1, "|b⟩")
    rc = QuantumRegister(1, "|c⟩")
    r_la = QuantumRegister(1, "L_a")
    r_lb = QuantumRegister(1, "L_b")
    r_lc = QuantumRegister(1, "L_c")
    r_p1 = QuantumRegister(1, "p1")
    r_p2 = QuantumRegister(1, "p2")
    outs = QuantumRegister(5, "f")

    qc = QuantumCircuit(ra, rb, rc, r_la, r_lb, r_lc, r_p1, r_p2, outs, name="F (UMG+FG)")
    a, b, c = ra[0], rb[0], rc[0]
    la, lb, lc = r_la[0], r_lb[0], r_lc[0]
    p1, p2 = r_p1[0], r_p2[0]
    f = list(outs)

    umg = umg_gate()
    umg_dg = umg_gate().inverse()
    ung = ung_gate()
    ung_dg = ung_gate().inverse()
    # minterm_index m = a + 2b + 4c -> XOR into these output lines (0-based f_1..f_5)
    xor_map: dict[int, list[int]] = {
        1: [0, 2, 4],
        2: [2, 4],
        3: [2, 4],
        4: [1],
        5: [1, 3],
        7: [1, 3, 4],
    }

    for m_idx in sorted(xor_map.keys()):
        if m_idx == 4:
            # a'b'c: (a∨b)' = a'b' with UNG(La,Lb,p1), p1 starts |1⟩; then UMG(p1,Lc,p2) for ∧c.
            qc.cx(a, la)
            qc.cx(b, lb)
            qc.cx(c, lc)
            qc.x(p1)
            qc.append(ung, [la, lb, p1])
            qc.append(umg, [p1, lc, p2])
            for j in xor_map[m_idx]:
                qc.cx(p2, f[j])
            qc.append(umg_dg, [p1, lc, p2])
            qc.append(ung_dg, [la, lb, p1])
            qc.x(p1)
            qc.cx(c, lc)
            qc.cx(b, lb)
            qc.cx(a, la)
            continue

        pa, pb, pc = _minterm_polarities(m_idx)
        _prepare_literal(qc, a, la, pa)
        _prepare_literal(qc, b, lb, pb)
        _prepare_literal(qc, c, lc, pc)

        qc.append(umg, [la, lb, p1])
        qc.append(umg, [p1, lc, p2])

        for j in xor_map[m_idx]:
            qc.cx(p2, f[j])

        qc.append(umg_dg, [p1, lc, p2])
        qc.append(umg_dg, [la, lb, p1])

        _unprepare_literal(qc, a, la, pa)
        _unprepare_literal(qc, b, lb, pb)
        _unprepare_literal(qc, c, lc, pc)

    return qc


def _check_f_circuit(qc: QuantumCircuit, num_inputs: int = 3) -> None:
    """Assert computational-basis I/O matches reference F on first 3 + last 5 qubits."""

    def ref_f(aa: int, bb: int, cc: int) -> tuple[int, ...]:
        f1 = (aa & (1 - bb)) ^ ((aa & (1 - bb)) & cc)
        f2 = (aa & cc) ^ ((1 - aa) & (1 - bb) & cc)
        f3 = f1 ^ (bb & (1 - cc))
        f4 = aa & cc
        f5 = (aa & (1 - bb)) ^ (aa & cc) ^ (bb & (1 - cc))
        return (f1, f2, f3, f4, f5)

    n = qc.num_qubits
    for bits in range(2**num_inputs):
        prep = QuantumCircuit(n)
        if bits & 1:
            prep.x(0)
        if bits & 2:
            prep.x(1)
        if bits & 4:
            prep.x(2)
        circ = prep.compose(qc)
        sv = Statevector.from_instruction(circ)
        idx = int(np.argmax(np.abs(sv.data) ** 2))
        ob = [(idx >> j) & 1 for j in range(n)]
        aa, bb, cc = ob[0], ob[1], ob[2]
        outs = ob[n - 5 :]
        exp = list(ref_f(aa, bb, cc))
        assert outs == exp, (bits, outs, exp, idx)


def _draw(qc: QuantumCircuit, stem: str) -> None:
    is_umg_panel = "umg" in stem
    # Keep UMG/Feynman view as one continuous circuit (no segmented folds).
    fold = -1 if is_umg_panel else 64
    scale = 0.56 if is_umg_panel else 0.70
    fig = qc.draw(
        output="mpl",
        fold=fold,
        scale=scale,
        style="iqp",
        cregbundle=False,
        plot_barriers=False,
        justify="left",
    )
    # For Fig. 11(a) (ESOP), compress figure height to reduce inter-wire spacing.
    if not is_umg_panel:
        w, h = fig.get_size_inches()
        fig.set_size_inches(w, h * 0.82, forward=True)
    # Tighten canvas so qubit labels and gates share one consistent left margin (Fig.~12).
    fig.subplots_adjust(left=0.06, right=0.99, top=0.94, bottom=0.06)
    for ext in ("pdf", "png"):
        fig.savefig(
            str(OUT_DIR / f"{stem}.{ext}"),
            bbox_inches="tight",
            pad_inches=0.06,
            dpi=150 if ext == "png" else None,
        )
    plt.close(fig)


def main() -> None:
    qc_mcx = build_func_f_circuit()
    qc_umg = build_func_f_umg_feynman()
    _check_f_circuit(qc_mcx)
    _check_f_circuit(qc_umg)

    _draw(qc_mcx, "qiskit_func_f_circuit")
    _draw(qc_umg, "qiskit_func_f_umg_feynman")
    print("Wrote", OUT_DIR / "qiskit_func_f_circuit.pdf")
    print("Wrote", OUT_DIR / "qiskit_func_f_umg_feynman.pdf")


if __name__ == "__main__":
    main()
