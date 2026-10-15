#!/usr/bin/env python3
"""
Hierarchical ngspice scaffolding for a memristor-style RPLA realization of sample F.

Mirrors the Qiskit driver pattern (qiskit_rpla_func_f.py): one Python entry point
writes reproducible artifacts for the paper (Sec.~3).

Outputs (default: directory of this script):
  * memristor_func_f_rpla.sp   — top-level netlist + MEMXP switch + commented UMG/UNG hierarchy
  * memristor_func_f_bom.txt   — instance / minterm correspondence

Crosspoints use voltage-controlled switches as LRS/HRS stand-ins; bind to memristor
subcircuits from the technology deck (TEAM, Biolek, etc.) for signoff.

Run: python3 memristor_rpla_func_f.py
Optional: ngspice -b memristor_func_f_rpla.sp
"""
from __future__ import annotations

from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

XOR_MAP: dict[int, list[int]] = {
    1: [0, 2, 4],
    2: [2, 4],
    3: [2, 4],
    4: [1],
    5: [1, 3],
    7: [1, 3, 4],
}


def ref_f(a: int, b: int, c: int) -> tuple[int, ...]:
    f1 = (a & (1 - b)) ^ ((a & (1 - b)) & c)
    f2 = (a & c) ^ ((1 - a) & (1 - b) & c)
    f3 = f1 ^ (b & (1 - c))
    f4 = a & c
    f5 = (a & (1 - b)) ^ (a & c) ^ (b & (1 - c))
    return (f1, f2, f3, f4, f5)


def write_spice_main(path: Path) -> None:
    """Valid ngspice deck: stimulus + crosspoint model + commented RPLA(F) hierarchy."""
    lines: list[str] = [
        "* memristor_func_f_rpla.sp",
        "* RPLA(F): memristor crossbar realization using UMG/UNG reversible macros (Sec. 3).",
        "* Driver: python3 memristor_rpla_func_f.py",
        "* Simulate: ngspice -b memristor_func_f_rpla.sp",
        "*",
        "* AND plane: UMG (MUX-style paths) and UNG (OR then XOR on third wire) per Figs. 2–4;",
        "*         map each macro to memristor crosspoints as in Fig. postcmosungumg.",
        "* XOR plane: Feynman (FG) paths between product rows and f_j columns—see Table matric_proposed_gates.",
        "",
        ".title RPLA_memristor_F_scaffold",
        "",
        ".param Vdd=1.0 Ron=1e3 Roff=1e9 Vth=0.5",
        ".global gnd",
        "",
        "* Primary inputs (toggle 0 / {Vdd} V for truth-table experiments).",
        "Va a 0 DC 0",
        "Vb b 0 DC 0",
        "Vc c 0 DC 0",
        "",
        "*--------------------------------------------------------------------",
        "* Memristor crosspoint abstraction: controlled switch LRS vs HRS.",
        ".model swmem sw (vt={vth} vh=0.05 ron={ron} roff={roff})",
        ".subckt MEMXP ctrl n1 n2",
        "S1 n1 n2 ctrl 0 swmem",
        ".ends MEMXP",
        "",
        "*--------------------------------------------------------------------",
        "* Output sense nodes (high-Z until XOR plane netlist is bound).",
        "Rf0 f0 0 1G",
        "Rf1 f1 0 1G",
        "Rf2 f2 0 1G",
        "Rf3 f3 0 1G",
        "Rf4 f4 0 1G",
        "",
        "*--------------------------------------------------------------------",
        "* Bennett / ESOP schedule (same minterms as qiskit_rpla_func_f.py UMG+FG path).",
        "* Replace comment blocks with XUMG... / XUNG... plus row and column wires.",
        "",
    ]

    umg = 0
    ung = 0
    for m_idx in sorted(XOR_MAP.keys()):
        fj = ", ".join(f"f{j}" for j in XOR_MAP[m_idx])
        if m_idx == 4:
            ung += 1
            umg += 1
            lines.append(f"* m={m_idx} a'b'c: UNG{ung}(a,b,p1_ung{ung}) -> UMG{umg}(p1_ung{ung},c,p2) -> XOR->{fj}")
            lines.append(
                f"* XUNG{ung} a b p1_ung{ung} 0 0 0  UNG_MEM_STUB  "
                f"' six ports: tie unused p,q to bias per layout'"
            )
            lines.append(
                f"* XUMG{umg} p1_ung{ung} c p2_m{m_idx} 0 0 0  UMG_MEM_STUB"
            )
        else:
            umg += 2
            lines.append(
                f"* m={m_idx}: UMG{umg-1}(La,Lb,p1_m{m_idx}) UMG{umg}(p1_m{m_idx},Lc,p2_m{m_idx}) -> XOR->{fj}"
            )
            lines.append(f"* XUMG{umg-1} la_m{m_idx} lb_m{m_idx} p1_m{m_idx} 0 0 0  UMG_MEM_STUB")
            lines.append(f"* XUMG{umg} p1_m{m_idx} lc_m{m_idx} p2_m{m_idx} 0 0 0  UMG_MEM_STUB")

    lines += [
        "",
        "*--------------------------------------------------------------------",
        "* Stub 3x3 cells (replace with crossbar netlist; keeps ngspice parseable).",
        ".subckt UMG_MEM_STUB a b c p q r",
        "Rp p 0 1G",
        "Rq q 0 1G",
        "Rr r 0 1G",
        ".ends UMG_MEM_STUB",
        "",
        ".subckt UNG_MEM_STUB a b c p q r",
        "Rp2 p 0 1G",
        "Rq2 q 0 1G",
        "Rr2 r 0 1G",
        ".ends UNG_MEM_STUB",
        "",
        ".op",
        ".end",
    ]

    text = "\n".join(lines).format(vth=0.5, ron="1e3", roff="1e9", Vdd=1.0)
    path.write_text(text, encoding="utf-8")


def write_bom(path: Path) -> None:
    lines = [
        "Memristor RPLA(F) — logical bill of materials",
        "============================================",
        "",
        "Minterms m=a+2b+4c  ->  XOR into outputs (paper f1..f5 = nodes f0..f4):",
        "",
    ]
    for m in sorted(XOR_MAP.keys()):
        outs = ", ".join(f"f{j+1}" for j in XOR_MAP[m])
        lines.append(f"  m={m}  ->  {outs}")
    lines += [
        "",
        "AND plane macros (bind to memristor crossbars per Fig. postcmosungumg):",
        "  UMG: two instances per minterm except m=4 (UNG+UMG).",
        "  UNG: one instance for m=4 before chaining to UMG for ∧c.",
        "",
        "XOR plane: Feynman / FG-style routing from each product wire p2_* to f_j.",
        "",
        "Toolchain (parallel to Qiskit in Sec. 4):",
        "  1) python3 memristor_rpla_func_f.py",
        "  2) Edit .sp: uncomment X* lines, connect la_m*, lb_m*, lc_m* to Va,Vb,Vc trees",
        "  3) ngspice -b memristor_func_f_rpla.sp",
        "  4) Optional: Xschem for memristor symbols; OpenROAD for digital I/O if hybrid.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_truth() -> None:
    for bits in range(8):
        a, b, c = bits & 1, (bits >> 1) & 1, (bits >> 2) & 1
        got = [0] * 5
        for m, flist in XOR_MAP.items():
            ma, mb, mc = m & 1, (m >> 1) & 1, (m >> 2) & 1
            if a == ma and b == mb and c == mc:
                for j in flist:
                    got[j] ^= 1
        exp = list(ref_f(a, b, c))
        assert got == exp, (bits, got, exp)


def main() -> None:
    verify_truth()
    write_spice_main(OUT_DIR / "memristor_func_f_rpla.sp")
    write_bom(OUT_DIR / "memristor_func_f_bom.txt")
    print("Wrote", OUT_DIR / "memristor_func_f_rpla.sp")
    print("Wrote", OUT_DIR / "memristor_func_f_bom.txt")


if __name__ == "__main__":
    main()
