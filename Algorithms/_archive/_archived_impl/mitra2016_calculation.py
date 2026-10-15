"""
Mitra2016 RPLA cost model — Algorithms 1–5 from
"Reversible Programmable Logic Arrays" (Mitra & Rahman).

Distinct from OptimizedRPLACalculation:
- Exact Pi ∈ P_QG membership only (no prefix-cube chaining heuristic)
- AND-plane garbage follows Theorem 2: GB = p + totalLiterals − ndot − q
- Ancilla (AND) follows Theorem 1: AI = n − t (= realized UMG/UNG gates)
"""

from __future__ import annotations

from optimized_rpla_calculation import OptimizedRPLACalculation


class Mitra2016Calculation(OptimizedRPLACalculation):
    """Paper Mitra2016 (UMG/UNG AND plane + Feynman XOR plane)."""

    def andPlane(self, plane_banner="Mitra2016 (paper Algorithms 1–4)"):
        """
        Algorithm 4: ConstructANDPlane(Iv, Pv).

        Pairwise literal sweep as in the paper grid; exact P_QG hits skip further
        AND work for that product (Theorem 1 reuse). Intermediate pivots are
        recorded in P_QG for later exact matches.
        """
        self.ordering_products_alg3()

        p_qg: set[str] = set()
        skipped_generated_product_idx: set[int] = set()
        ndot = 0
        pqg_reuse_count = 0
        template_counts = {
            "α": 0,
            "β": 0,
            "γ": 0,
            "π": 0,
            "α_prime": 0,
            "β_prime": 0,
            "γ_prime": 0,
            "π_prime": 0,
        }

        n_lit = self._opt_total_literals
        for g in range(n_lit - 1):
            for h in range(g + 1, n_lit):
                swap_flag = 0
                for i in range(len(self.products)):
                    if i in skipped_generated_product_idx:
                        continue
                    if self._product_contains_literals(i, [g, h]):
                        swap_flag += 1

                if swap_flag <= 0:
                    # Alg. 4 line 32 — SwapLiterals when no mutual products.
                    # Deferred: global column swaps destabilize ESOP cubes in this
                    # host representation; paper Java grid tracks line signals separately.
                    continue

                for i in range(len(self.products)):
                    size_i = self.products[i].getSize()
                    if size_i > 1:
                        if i in skipped_generated_product_idx:
                            continue
                        bp_i = self._canonical_bit_pattern(self.products[i].bitPattern)
                        if bp_i in p_qg:
                            p_qg.discard(bp_i)
                            skipped_generated_product_idx.add(i)
                            pqg_reuse_count += 1
                            continue

                        if not self._product_contains_literals(i, [g, h]):
                            continue

                        swap_flag -= 1
                        la = self._signed_literal_from_product(i, g)
                        lb = self._signed_literal_from_product(i, h)
                        pivot_p, template = self._op_and(la, lb, swap_flag)
                        template_counts[template] += 1

                        if size_i > 2:
                            # Alg. 4 lines 18–25: finish remaining literals; store Pg
                            p_g = pivot_p
                            for j in range(h + 1, n_lit):
                                if self._product_contains_literal(i, j):
                                    p_g = pivot_p
                                    lj = self._signed_literal_from_product(i, j)
                                    pivot_p, template = self._op_and_garbage(
                                        pivot_p if pivot_p is not None else "",
                                        lj,
                                        swap_flag=1,  # false → non-zero → unprimed
                                    )
                                    template_counts[template] += 1
                            if p_g is not None:
                                p_qg.add(self._canonical_bit_pattern(p_g))
                            skipped_generated_product_idx.add(i)
                        else:
                            # Size == 2: product complete after one OpAND
                            if pivot_p is not None:
                                p_qg.add(self._canonical_bit_pattern(pivot_p))
                            skipped_generated_product_idx.add(i)
                    else:
                        # SizeOf(Pi) <= 1 → via (•); count once
                        if i in skipped_generated_product_idx:
                            continue
                        if self._product_contains_literal(i, h) or self._product_contains_literal(
                            i, g
                        ):
                            skipped_generated_product_idx.add(i)
                            ndot += 1

        total_gates = sum(template_counts.values())
        umg_raw = (
            template_counts["α"]
            + template_counts["β"]
            + template_counts["γ"]
            + template_counts["α_prime"]
            + template_counts["β_prime"]
            + template_counts["γ_prime"]
        )
        ung_raw = template_counts["π"] + template_counts["π_prime"]
        if total_gates > 0 and (umg_raw + ung_raw) > 0:
            self.umg_template_gates = int(round(total_gates * (umg_raw / (umg_raw + ung_raw))))
            self.ung_template_gates = int(total_gates) - int(self.umg_template_gates)
        else:
            self.umg_template_gates = 0
            self.ung_template_gates = 0
        self.and_template_gate_total = int(total_gates)

        # Theorem 1
        total_quantum_cost = total_gates * 5
        total_ancilla_input_count = total_gates

        # Theorem 2: GB = p + totalLiterals - ndot - q
        p_large = sum(1 for prod in self.products if prod.getSize() > 2)
        q = pqg_reuse_count
        total_garbages = p_large + n_lit - ndot - q

        self.quantumCost += total_quantum_cost
        self.gates += total_gates
        self.garbages += total_garbages
        self.ancilla_input_count += total_ancilla_input_count

        self.delay = 0
        for product in self.products:
            self.delay = max(self.delay, product.delayCountAND)

        if not self.quiet:
            print("==========================================================")
            print(f"                {plane_banner}")
            print("==========================================================")
            print("==========================================================")
            print("               Dynamically Ordered PRODUCTS ")
            self.showProducts()
            print("==========================================================")
            print("             Calculation of AND Plane (Mitra2016)")
            print("==========================================================")
            print(f"TDOT (ndot)             : {ndot}")
            print(f"P_QG reuses (q)         : {pqg_reuse_count}")
            print(
                "Templates "
                f"[α-{template_counts['α']}, β-{template_counts['β']}, "
                f"γ-{template_counts['γ']}, π-{template_counts['π']}] and "
                f"[α′-{template_counts['α_prime']}, β′-{template_counts['β_prime']}, "
                f"γ′-{template_counts['γ_prime']}, π′-{template_counts['π_prime']}]"
            )
            print(f"Total Gates, GT     : {total_gates}  (Theorem 1: n-t)")
            print(f"Garbage, GB         : {total_garbages}  (Theorem 2: p+L-ndot-q)")
            print(f"Ancilla, AI         : {total_ancilla_input_count}")
            print(f"Quantum Cost        : {total_quantum_cost}")
            print("==========================================================")


__all__ = ["Mitra2016Calculation"]
