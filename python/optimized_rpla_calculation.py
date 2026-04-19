"""
Optimized RPLA cost model guided by algorithm.txt in this package.

- Algorithm 3 (OrderingProducts): reorder products by descending cube size, then
  by a literal-by-literal sweep (Iv), remapping function→product indices.
- EXOR and AND planes use the same realization as CostCalculation (Mitra2012 Design):
  Sorted FUNCTIONS, Rearranged PRODUCTS, EX-OR Plane, AND Plane, Delay — only the
  main banner reads "Optimized RPLA".
"""

from cost_calculation import CostCalculation


class OptimizedRPLACalculation(CostCalculation):
    def __init__(self, rpla_snap, total_literals: int, quiet=False):
        super().__init__(rpla_snap, quiet=quiet)
        self._opt_total_literals = total_literals

    def ordering_products_alg3(self) -> None:
        """
        Algorithm 3: OrderingProducts(Iv, Pv)
        Sort by |Pi| descending, then for each literal position add products that
        contain that literal, each product at most once in PQ.
        """
        old_products = list(self.products)
        n_literals = self._opt_total_literals
        if n_literals <= 0:
            return

        sorted_by_size = sorted(old_products, key=lambda p: p.getSize(), reverse=True)
        p_q = []
        seen_ids = set()
        for lit_i in range(n_literals):
            for pj in sorted_by_size:
                if lit_i < len(pj.bitPattern) and pj.bitPattern[lit_i] in ("0", "1"):
                    if pj.id not in seen_ids:
                        p_q.append(pj)
                        seen_ids.add(pj.id)
        for pj in sorted_by_size:
            if pj.id not in seen_ids:
                p_q.append(pj)
                seen_ids.add(pj.id)

        id_to_new = {p.id: i for i, p in enumerate(p_q)}
        for fn in self.functions:
            fn.productsList = [
                id_to_new[old_products[idx].id] for idx in fn.productsList
            ]

        self.products.clear()
        self.products.extend(p_q)

    def _refresh_product_literals(self, product) -> None:
        """Recompute length and literals[] from bitPattern after pattern edits."""
        product.literals.clear()
        product.length = 0
        for idx, ch in enumerate(product.bitPattern):
            if ch in ("0", "1"):
                product.length += 1
                product.literals.append(idx)

    def swap_literals_alg2(self, line_i: int, line_j: int) -> None:
        """
        Algorithm 2: SwapLiterals(L_i, L_j)
        Exchange input signals on lines L_i and L_j: swap cube columns i and j
        in every product (PLA bit string).
        """
        if line_i == line_j:
            return
        n = max(self._opt_total_literals, line_i + 1, line_j + 1)
        for p in self.products:
            bp = list(p.bitPattern)
            while len(bp) < n:
                bp.append("-")
            bp[line_i], bp[line_j] = bp[line_j], bp[line_i]
            p.bitPattern = "".join(bp)
            self._refresh_product_literals(p)

    def xorPlane(self):
        """
        Algorithm 5: ConstructXORplane(Pv, Fv)
        EX-OR plane generates final outputs from products.
        Note: Products should already be ordered by andPlane (Algorithm 4).
        """
        
        # Initialize F_Q (set of processed functions) and xdot counter
        f_q = set()
        xdot = 0
        # Algorithm 5 template counts (excluding • / xdot)
        count_nabla = 0   # ∇ — keep a copy of P_i
        count_lambda = 0  # λ — XOR P_i onto function line
        count_triangle = 0  # △ — keep complemented copy of P_i

        # Process each product
        for i in range(len(self.products)):
            product = self.products[i]
            for j in range(len(self.functions)):
                function = self.functions[j]
                
                # Check if product belongs to this function
                if i in function.productsList:
                    if j not in f_q:
                        # First time seeing this function
                        if self._get_product_frequency(i) == 1:
                            # Use TDOT (•)
                            xdot += 1
                        else:
                            # Use ∇ (keep copy)
                            count_nabla += 1
                            self._keep_product_copy(i)
                            self._decrement_product_frequency(i)
                        f_q.add(j)
                    else:
                        # Function already processed, use XOR (λ)
                        count_lambda += 1
                        self._xor_product_to_function(i, j)
                        self._decrement_product_frequency(i)
                elif self._is_complemented_product_in_function(i, j):
                    # Use △ (keep complemented copy)
                    count_triangle += 1
                    self._keep_complemented_product_copy(i)
                    self._decrement_product_frequency(i)
        
        # Update statistics
        self.xorTDOT = xdot
        total_xor_operations = sum(f.getSize() - 1 for f in self.functions)
        total_fg_gates = total_xor_operations + len(self.functions) - xdot
        total_garbages = len(self.products) - xdot
        # total_ancilla_input_count= total_garbages + len(self.functions) - len(self.products)
        total_ancilla_input_count= count_nabla + count_triangle
        total_quantum_cost = total_fg_gates
        
        self.quantumCost += total_quantum_cost
        self.gates += total_fg_gates
        self.garbages+=total_garbages
        self.ancilla_input_count+=total_ancilla_input_count

        # Print results
        if not self.quiet:
            print("==========================================================")
            print("             Calculation of EX-OR Plane")
            print("==========================================================")
            print(f"Total EXOR Operations : {total_xor_operations}")
            print(f"TDOT                  : {self.xorTDOT}")
            print(
                "Algorithm 5 templates  "
                f"∇ (COPY): {count_nabla}   "
                f"λ (XOR): {count_lambda}   "
                f"△ (NOT): {count_triangle}"
            )
            print(f"Feynman Gate          : {total_fg_gates}")
            print(f"Garbage, GB           : {total_garbages}")
            print(f"Ancilla, AI           : {total_ancilla_input_count}")
            print(f"Quantum Cost          : {total_quantum_cost}")
            print("==========================================================")

    def andPlane(self, plane_banner="Proposed Optimized RPLA"):
        """
        Algorithm 4: ConstructANDPlane(Iv, Pv)
        Build AND plane using UMG and UNG gates with literal reordering.
        """

        # Call Algorithm 3: OrderingProducts as specified in Algorithm 4
        self.ordering_products_alg3()
        
        # P_QG: garbage cubes (canonical minterm keys) → how often each prefix was used
        # in the prefix-match / _op_and_garbage branch (new pivots are inserted with setdefault).
        p_qg: dict[str, int] = {}
        # Products whose cube matched P_QG (already generated): skip further AND ops for them
        skipped_generated_product_idx: set[int] = set()
        ndot = 0
        template_counts = {
            'α': 0, 'β': 0, 'γ': 0, 'π': 0,
            'α_prime': 0, 'β_prime': 0, 'γ_prime': 0, 'π_prime': 0
        }
        
        # Process each pair of literals
        for g in range(self._opt_total_literals - 1):
            for h in range(g + 1, self._opt_total_literals):
                swap_flag = 0
                
                # Count products containing both literals I_g and I_h
                for i in range(len(self.products)):
                    if i in skipped_generated_product_idx:
                        continue
                    if self._product_contains_literals(i, [g, h]):
                        swap_flag += 1
                
                if swap_flag > 0:
                    # Process products with size > 1
                    for i in range(len(self.products)):
                        if self.products[i].getSize() > 1:
                            bp_i = self._canonical_bit_pattern(self.products[i].bitPattern)
                            if i in skipped_generated_product_idx:
                                continue
                            if bp_i in p_qg:
                            # p_qg.remove(bp_i)
                                skipped_generated_product_idx.add(i)    # add to skipped_generated_product_idx to skip further operations for this product
                                continue

                            if self._p_qg_contains_prefix_of_bp(p_qg, bp_i):
                                if self._product_contains_literal(i, h):
                                    gq = self._p_qg_find_matching_prefix_cube(p_qg, bp_i)
                                    if gq is not None:
                                        if len(gq.rstrip("-"))-1 < h:
                                            lj = self._signed_literal_from_product(i, h)
                                            pivot_p, template = self._op_and_garbage(gq, lj, swap_flag)
                                            template_counts[template] += 1
                                            # print(f"PREFIX-ANDING-Templates: {template}-({template_counts[template]}) - g:{gq} -- pvort: {pivot_p} ---P:{bp_i}")
                                            p_qg[gq] += 1
                                            if pivot_p is not None:
                                                p_qg.setdefault(
                                                    self._canonical_bit_pattern(pivot_p), 0
                                                )
                                continue
                            if self._product_contains_literals(i, [g, h]):
                                swap_flag -= 1
                                la = self._signed_literal_from_product(i, g)
                                lb = self._signed_literal_from_product(i, h)
                                pivot_p, template = self._op_and(la, lb, swap_flag)
                                template_counts[template] += 1
                                # print(f"LIT-ANDING-Templates: {template}-({template_counts[template]}) - g:{la},{lb} -- pvort: {pivot_p} ---P:{self.products[i].bitPattern}")
                                if pivot_p is not None:
                                    p_qg.setdefault(
                                        self._canonical_bit_pattern(pivot_p), 0
                                    )
                            # if self.products[i].getSize() > 2:
                            #     p_g = None
                            #     for j in range(h + 1, self._opt_total_literals):
                            #         if self._product_contains_literal(i, j):
                            #             p_g = pivot_p
                            #             lj = self._signed_literal_from_product(i, j)
                            #             pivot_p, template = self._op_and(pivot_p, lj, False)
                            #             template_counts[template] += 1
                        if self.products[i].getSize() == 1:
                            if self._product_contains_literal(i, h):
                                if i in skipped_generated_product_idx:
                                    continue
                                else:
                                    skipped_generated_product_idx.add(i)
                                    ndot += 1
                # else:
                #     # Algorithm 4 line 32: no product contains both I_g and I_h
                #     self.swap_literals_alg2(g, h)
        # Calculate AND plane statistics
        total_and_operations = sum(p.getSize() - 1 for p in self.products if p.getSize() > 1)
        and_tdot = ndot
        total_skipped_and_operations_due_to_p_qg = sum(
            v for v in p_qg.values() if v >= 2
        )
        total_gates = sum(template_counts.values()) - total_skipped_and_operations_due_to_p_qg
        total_quantum_cost = total_gates * 5
        # each gates has 1 ancilla 
        total_ancilla_input_count = total_gates 
        total_garbages = (
            total_ancilla_input_count
            + self._opt_total_literals
            - and_tdot
            - len(self.products)
        )
        # Update quantum cost and other metrics (no XOR operations in AND plane)
        self.quantumCost += total_quantum_cost
        # For Optimized RPLA: Total number of Gates = Total number of Templates
        self.gates += total_gates
        self.garbages += total_garbages
        self.ancilla_input_count += total_ancilla_input_count
        
        # Calculate delay (AND plane only)
        self.delay = 0
        for product in self.products:
            self.delay = max(self.delay, product.delayCountAND)
        
        # Print results
        if not self.quiet:
            print("==========================================================")
            print(f"                {plane_banner}")
            print("==========================================================")
            print("==========================================================")
            print("               Dynamically Ordered PRODUCTS ")
            self.showProducts()
            print("==========================================================")
            print(f"Total AND Operations: {total_and_operations}")
            print(f"TDOT                : {and_tdot}")
            # print(f"P_QG: {p_qg}")
            # print(f"Total Skipped AND Operations Due to P_QG: {total_skipped_and_operations_due_to_p_qg}")
            # print(f"P_Generated : {skipped_generated_product_idx}")
            print(f"Templates [α-{template_counts['α']}, β-{template_counts['β']}, γ-{template_counts['γ']}, π-{template_counts['π']}] and [α′-{template_counts['α_prime']}, β′-{template_counts['β_prime']}, γ′-{template_counts['γ_prime']}, π′-{template_counts['π_prime']}]")
            print(f"Total Gates, GT     : {total_gates}")
            print(f"Garbage, GB         : {total_garbages}")
            print(f"Ancilla, AI         : {total_ancilla_input_count}")
            print(f"Quantum Cost        : {total_quantum_cost}")
            print("==========================================================")

    def _get_product_frequency(self, product_idx: int) -> int:
        """Get how many functions contain this product."""
        return self.products[product_idx].getFrequency()

    def _keep_product_copy(self, product_idx: int):
        """Mark product as kept (∇ operation)."""
        # Implementation: mark product as used in XOR plane
        self.products[product_idx].flag = True

    def _decrement_product_frequency(self, product_idx: int):
        """Decrement frequency counter for product."""
        self.products[product_idx].frequency -= 1

    def _xor_product_to_function(self, product_idx: int, function_idx: int):
        """XOR product to function line (λ operation)."""
        # Implementation: add product to function's product list if not already there
        if product_idx not in self.functions[function_idx].productsList:
            self.functions[function_idx].addProduct(product_idx)

    def _is_complemented_product_in_function(self, product_idx: int, function_idx: int) -> bool:
        """Check if complemented product belongs to function."""
        # This would require implementing complement logic
        # For now, return False as placeholder
        return False

    def _keep_complemented_product_copy(self, product_idx: int):
        """Keep complemented copy of product (△ operation)."""
        # Implementation: create complemented version of product
        pass  # Placeholder - would need complement logic

    def _product_contains_literals(self, product_idx: int, literals: list) -> bool:
        """Check if product contains all specified literals."""
        product = self.products[product_idx]
        for lit in literals:
            if lit >= len(product.bitPattern) or product.bitPattern[lit] not in ('0', '1'):
                return False
        return True

    def _product_contains_literal(self, product_idx: int, literal: int) -> bool:
        """Check if product contains specific literal."""
        product = self.products[product_idx]
        return (literal < len(product.bitPattern) and 
                product.bitPattern[literal] in ('0', '1'))

    def _canonical_bit_pattern(self, pat: str) -> str:
        """Normalize cube to length totalLiterals with '-' padding (for P_QG keys)."""
        n = self._opt_total_literals
        if not pat:
            return "-" * n
        if len(pat) >= n:
            return pat[:n]
        return pat + "-" * (n - len(pat))

    def _p_qg_find_matching_prefix_cube(self, q: dict[str, int], p_bp: str) -> str | None:
        """
        Return a cube key ``g`` from ``q`` that matches the start of canonical ``p_bp``,
        choosing among all matches the one whose stripped form ``s = g.rstrip('-')`` has
        maximum ``len(s)``; or None if no match.

        Cares in ``g`` must agree with ``p_bp``; ``-`` in ``g`` is wildcard. Only keys with
        ``2 <= len(s) < len(p_c)`` are considered, where ``p_c`` canonicalizes ``p_bp``.
        """
        p_c = self._canonical_bit_pattern(p_bp)
        best: str | None = None
        best_len = -1
        for g in q:
            s = g.rstrip("-")
            if len(s) < 2 or len(s) >= len(p_c):
                continue
            ok = True
            for i, ch in enumerate(s):
                if i >= len(p_c):
                    ok = False
                    break
                if ch in ("0", "1") and ch != p_c[i]:
                    ok = False
                    break
            if ok and len(s) > best_len:
                best_len = len(s)
                best = g
        return best

    def _p_qg_contains_prefix_of_bp(self, q: dict[str, int], p_bp: str) -> bool:
        """True iff ``_p_qg_find_matching_prefix_cube`` finds a matching cube in ``q``."""
        return self._p_qg_find_matching_prefix_cube(q, p_bp) is not None

    def _signed_pair_to_minterm(self, lit_a: int, lit_b: int) -> str | None:
        """
        AND of two signed literals as one PLA cube row (minterm form), length n.
        +k / -k use 1-based k = column index + 1.
        Returns None if contradiction (e.g. x ∧ ¬x on same line).
        """
        n = self._opt_total_literals
        if lit_a == 0 or lit_b == 0:
            return None
        if abs(lit_a) == abs(lit_b):
            if lit_a != lit_b:
                return None
            idx = abs(lit_a) - 1
            row = ["-"] * n
            row[idx] = "1" if lit_a > 0 else "0"
            return "".join(row)
        row = ["-"] * n
        for lit in (lit_a, lit_b):
            idx = abs(lit) - 1
            if idx < 0 or idx >= n:
                return None
            ch = "1" if lit > 0 else "0"
            if row[idx] != "-" and row[idx] != ch:
                return None
            row[idx] = ch
        return "".join(row)

    def _signed_literal_from_product(self, product_idx: int, column_idx: int) -> int:
        """
        Map cube column `column_idx` in product `product_idx` to OpAND literal form:
        +k  = uncomplemented variable on line k
        -k  = complemented variable on line k
        where k = column_idx + 1 (1-based line id).

        Cube encoding: '1' → positive literal, '0' → negative literal (see ESOP PLA convention).
        """
        p = self.products[product_idx]
        if column_idx >= len(p.bitPattern):
            return 0
        ch = p.bitPattern[column_idx]
        k = column_idx + 1
        if ch == "1":
            return k
        if ch == "0":
            return -k
        return 0

    def _op_and(self, lit_a: int, lit_b: int, swap_flag: int) -> tuple[str | None, str]:
        """
        Algorithm 1: OpAND(p, q, swapFlag)
        Returns (pivot_minterm, template) where pivot_minterm is a PLA cube string
        (length totalLiterals, e.g. '10-', '1-1', '001') or None on contradiction.

        Args lit_a, lit_b: signed 1-based line ids from the current product cube
        (_signed_literal_from_product). Positive = uncomplemented, negative = complemented.
        """
        is_p_complemented = lit_a < 0
        is_q_complemented = lit_b < 0

        if is_p_complemented:
            if is_q_complemented:
                template = "π_prime" if swap_flag == 0 else "π"
            else:
                template = "β_prime" if swap_flag == 0 else "β"
        else:
            if is_q_complemented:
                template = "α_prime" if swap_flag == 0 else "α"
            else:
                template = "γ_prime" if swap_flag == 0 else "γ"

        minterm = self._signed_pair_to_minterm(lit_a, lit_b)
        return minterm, template

    def _op_and_garbage(
        self, garbage_minterm: str, lit_b: int, swap_flag: int
    ) -> tuple[str | None, str]:
        """
        AND a garbage PLA cube (``garbage_minterm``) with one signed literal ``lit_b``,
        as in Algorithm 4 (``OpAND(pivotP, I_j, swapFlag)``) when ``pivotP`` is a cube.

        The template follows Algorithm 1 with the cube treated as the non-complemented
        left operand, so classification depends only on whether ``lit_b`` is complemented
        (α / α′) or positive (γ / γ′), selected by ``swap_flag``.
        """
        if lit_b == 0:
            return None, "γ_prime"

        if lit_b < 0:
            template = "α_prime" if swap_flag == 0 else "α"
        else:
            template = "γ_prime" if swap_flag == 0 else "γ"

        n = self._opt_total_literals
        row = list(self._canonical_bit_pattern(garbage_minterm))
        idx = abs(lit_b) - 1
        if idx < 0 or idx >= n:
            return None, template

        want = "1" if lit_b > 0 else "0"
        cur = row[idx]
        if cur in ("0", "1") and cur != want:
            return None, template
        row[idx] = want
        return "".join(row), template