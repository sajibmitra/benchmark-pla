"""
Tara–Babu 2016 RPLA cost model — Algorithms 1–2 from
"Synthesis of reversible PLA using products sharing"
(Tara & Babu, J. Comput. Electron.; journal counterpart of the NMG conference paper).

AND plane (Algorithm 1): frequency/index product sort, 2-literal sub-product
sharing, F2G copies, TB (quantum cost 4) ANDs.
XOR plane (Algorithm 2): Feynman (Gate 4) with DOT on a frequency-1 first
product; Theorems 3–4 for FG / garbage.

Distinct from Mitra2016 (UMG/UNG P_QG grid) and OptimizedRPLACalculation
(Prefix Cube tree).
"""

from __future__ import annotations

from cost_calculation import CostCalculation

QC_TB = 4
QC_F2G = 2
QC_FG = 1


class Tara2016Calculation(CostCalculation):
    """Journal Algorithms 1–2 (TB AND plane + Feynman XOR plane)."""

    def __init__(self, rpla_snap, total_literals: int, quiet=False):
        super().__init__(rpla_snap, quiet=quiet)
        self._total_literals = total_literals
        self.tb_gates = 0
        self.f2g_gates = 0
        self.and_ndot = 0
        self.xor_ndot = 0
        self.shared_two_prefixes = 0

    def andPlane(self, plane_banner="Tara2016 (paper Algorithms 1–2, AND)"):
        self._order_products_alg1()

        n_lit = self._total_literals
        signed_uses: dict[tuple[int, str], int] = {}
        for prod in self.products:
            for var, bit in self._product_lits(prod):
                signed_uses[(var, bit)] = signed_uses.get((var, bit), 0) + 1

        produced_two: set[tuple] = set()
        primary_line_used: set[tuple[int, str]] = set()
        tb = 0
        f2g = 0
        ndot = 0
        gbc_and = 0
        shared = 0

        for prod in self.products:
            lits = self._product_lits(prod)
            if not lits:
                continue

            first = lits[0]
            if signed_uses.get(first, 0) <= 1:
                ndot += 1
            elif first not in primary_line_used:
                # First consumption of a reused literal uses the primary track.
                primary_line_used.add(first)
                ndot += 1
            else:
                f2g += 1

            if len(lits) < 2:
                continue

            key = self._two_prefix_key(lits)
            dual = self._dual_two_prefix(key)
            if key in produced_two:
                ndot += 1
                shared += 1
            else:
                tb += 1
                produced_two.add(key)
                if dual is not None:
                    produced_two.add(dual)

            for _extra in lits[2:]:
                tb += 1
                gbc_and += 1

        self.tb_gates = tb
        self.f2g_gates = f2g
        self.and_ndot = ndot
        self.shared_two_prefixes = shared
        self.and_template_gate_total = tb
        self.umg_template_gates = tb
        self.ung_template_gates = 0

        # Theorem 2: GB_AND = i + q − DOT (q = realized TB ANDs).
        gb_and = max(0, n_lit + tb - ndot)
        qc_and = tb * QC_TB + f2g * QC_F2G
        gt_and = tb + f2g
        ai_and = tb  # one ancilla per TB (3×3)

        self.quantumCost += qc_and
        self.gates += gt_and
        self.garbages += gb_and
        self.ancilla_input_count += ai_and

        self.delay = 0
        for product in self.products:
            self.delay = max(self.delay, product.delayCountAND)

        if not self.quiet:
            print("==========================================================")
            print(f"                {plane_banner}")
            print("==========================================================")
            print("               Frequency-ordered PRODUCTS ")
            self.showProducts()
            print("==========================================================")
            print("             Calculation of AND Plane (Tara2016)")
            print("==========================================================")
            print(f"TDOT (ndot)             : {ndot}")
            print(f"Shared 2-prefixes       : {shared}")
            print(f"TB gates                : {tb}  (QC {QC_TB} each)")
            print(f"F2G copies              : {f2g}  (QC {QC_F2G} each)")
            print(f"Total Gates, GT     : {gt_and}")
            print(f"Garbage, GB         : {gb_and}  (Theorem 2: i+q-DOT)")
            print(f"Ancilla, AI         : {ai_and}")
            print(f"Quantum Cost        : {qc_and}")
            print("==========================================================")

    def xorPlane(self, plane_banner="Tara2016 (paper Algorithm 2, EX-OR)"):
        """
        Algorithm 2: single-product functions last; DOT if the first product of
        Fi has frequency 1; otherwise Feynman (Gate 4). Last share of a product
        also counts XOR garbage (Theorem 4: GB = p − DOT).
        """
        rest = [fn for fn in self.functions if fn.getSize() != 1]
        singles = [fn for fn in self.functions if fn.getSize() == 1]
        ordered_fns = rest + singles

        remaining = [prod.getFrequency() for prod in self.products]
        n_part = sum(remaining)
        gtc = 0
        gbc = 0
        ndot = 0

        for fn in ordered_fns:
            for k, pj in enumerate(fn.productsList):
                if pj < 0 or pj >= len(self.products):
                    continue
                if remaining[pj] <= 0:
                    continue
                is_last_share = remaining[pj] == 1
                if k == 0:
                    if remaining[pj] == 1:
                        ndot += 1
                    else:
                        gtc += 1
                elif is_last_share:
                    gtc += 1
                    gbc += 1
                else:
                    gtc += 1
                remaining[pj] -= 1

        # Theorems 3–4 (minima); simulation may differ slightly on DOT placement.
        p = len(self.products)
        fg = max(0, n_part - ndot)
        gb_xor = max(0, p - ndot)
        ai_xor = max(0, len(self.functions) + gb_xor - p)
        qc_xor = fg * QC_FG

        self.xor_ndot = ndot
        self.xorTDOT = ndot
        self.feynman_xor_plane_gates = int(fg)
        self.quantumCost += qc_xor
        self.gates += fg
        self.garbages += gb_xor
        self.ancilla_input_count += ai_xor

        if not self.quiet:
            print("==========================================================")
            print(f"                {plane_banner}")
            print("==========================================================")
            print("                Sorted FUNCTIONS ")
            self.showFunctions()
            print("==========================================================")
            print("             Calculation of EX-OR Plane (Tara2016)")
            print("==========================================================")
            print(f"Participations n        : {n_part}")
            print(f"TDOT                    : {ndot}")
            print(f"Simulated FG / GB       : {gtc} / {gbc}")
            print(f"Feynman Gate          : {fg}  (Theorem 3: n-DOT)")
            print(f"Garbage, GB           : {gb_xor}  (Theorem 4: p-DOT)")
            print(f"Ancilla, AI           : {ai_xor}")
            print(f"Quantum Cost          : {qc_xor}")
            print("==========================================================")

    def _order_products_alg1(self) -> None:
        """Algorithm 1 lines 2–4: frequency, index, adjacent swap, defer non-I0."""
        old = list(self.products)
        ordered = sorted(old, key=lambda p: (p.getFrequency(), p.id))
        ordered = self._adjacent_frequency_swap(ordered)
        if self._total_literals > 0:
            with_i0 = [p for p in ordered if self._contains_var(p, 0)]
            without_i0 = [p for p in ordered if not self._contains_var(p, 0)]
            ordered = with_i0 + without_i0

        id_to_new = {p.id: i for i, p in enumerate(ordered)}
        for fn in self.functions:
            fn.productsList = [id_to_new[old[idx].id] for idx in fn.productsList if idx < len(old)]

        self.products.clear()
        self.products.extend(ordered)

    def _adjacent_frequency_swap(self, ordered: list) -> list:
        """Realize Y before X when they are consecutive, same frequency, and Y is Op's second unique product."""
        by_id = {p.id: p for p in ordered}
        pos = {p.id: i for i, p in enumerate(ordered)}
        ids = sorted(by_id)
        for xid in ids:
            yid = xid + 1
            if yid not in by_id:
                continue
            x, y = by_id[xid], by_id[yid]
            if x.getFrequency() != y.getFrequency():
                continue
            if not self._swap_y_before_x(x, y):
                continue
            i, j = pos[xid], pos[yid]
            if i == j:
                continue
            ordered[i], ordered[j] = ordered[j], ordered[i]
            pos[xid], pos[yid] = j, i
        return ordered

    def _swap_y_before_x(self, x, y) -> bool:
        x_idx = next((i for i, p in enumerate(self.products) if p.id == x.id), None)
        y_idx = next((i for i, p in enumerate(self.products) if p.id == y.id), None)
        if x_idx is None or y_idx is None:
            return False
        n_fn = len(self.functions)
        for p, fn in enumerate(self.functions):
            plist = fn.productsList
            if x_idx not in plist or y_idx not in plist:
                continue
            if plist[0] != x_idx:
                continue
            if len(plist) < 2 or plist[1] != y_idx:
                continue
            y_shared_later = False
            for q in range(p + 1, n_fn):
                if y_idx in self.functions[q].productsList:
                    y_shared_later = True
                    break
            if not y_shared_later:
                return True
        return False

    @staticmethod
    def _product_lits(product) -> list[tuple[int, str]]:
        out = []
        for i, ch in enumerate(product.bitPattern):
            if ch in ("0", "1"):
                out.append((i, ch))
        return out

    @staticmethod
    def _contains_var(product, var: int) -> bool:
        bp = product.bitPattern
        return var < len(bp) and bp[var] in ("0", "1")

    @staticmethod
    def _two_prefix_key(lits: list[tuple[int, str]]) -> tuple:
        (v1, b1), (v2, b2) = lits[0], lits[1]
        return (v1, b1, v2, b2)

    @staticmethod
    def _dual_two_prefix(key: tuple) -> tuple | None:
        """NMG/TB Fig. 7(e): one gate emits BC' and B'C together."""
        if key is None or len(key) != 4:
            return None
        v1, b1, v2, b2 = key
        flip = {"0": "1", "1": "0"}
        return (v1, flip[b1], v2, flip[b2])


__all__ = ["Tara2016Calculation"]
