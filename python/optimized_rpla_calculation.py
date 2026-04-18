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
        # ordering_products_alg3() is called in andPlane (Algorithm 4)
        
        # Initialize F_Q (set of processed functions) and xdot counter
        f_q = set()
        xdot = 0
        
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
                            self._keep_product_copy(i)
                            self._decrement_product_frequency(i)
                        f_q.add(j)
                    else:
                        # Function already processed, use XOR (λ)
                        self._xor_product_to_function(i, j)
                elif self._is_complemented_product_in_function(i, j):
                    # Use △ (keep complemented copy)
                    self._keep_complemented_product_copy(i)
        
        # Update statistics
        self.xorTDOT = xdot
        total_xor_operations = sum(f.getSize() - 1 for f in self.functions)
        self.gates = total_xor_operations + len(self.functions) - xdot
        self.garbages = len(self.products) - xdot
        self.quantumCost = self.gates
        
        # Print results
        if not self.quiet:
            print("==========================================================")
            print("             Calculation of EX-OR Plane")
            print("==========================================================")
            print(f"Total EXOR Operations : {total_xor_operations}")
            print(f"TDOT                  : {self.xorTDOT}")
            print(f"Feynman Gate          : {self.gates}")
            print(f"Garbage, GB           : {self.garbages}")
            print("==========================================================")

    def andPlane(self, plane_banner="Optimized RPLA"):
        """
        Algorithm 4: ConstructANDPlane(Iv, Pv)
        Build AND plane using UMG and UNG gates with literal reordering.
        """

        # if not self.quiet:
        #     print("==========================================================")
        #     print(f"                {plane_banner}")
        #     print("==========================================================")
        #     print("                Before Ordering Products ")
        #     self.showFunctions()
        #     print("----------------------------------------------------------")
        #     self.showProducts()
        #     print("==========================================================")
            
        # Call Algorithm 3: OrderingProducts as specified in Algorithm 4
        self.ordering_products_alg3()
        
        if not self.quiet:
            print("==========================================================")
            print("                After Ordering Products ")
            # self.showFunctions()
            # print("----------------------------------------------------------")
            self.showProducts()
            print("==========================================================")
        
        # Initialize P_QG (garbage products), ndot counter, and template counters
        p_qg = set()
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
                    if self._product_contains_literals(i, [g, h]):
                        swap_flag += 1
                
                if swap_flag > 0:
                    # Process products with size > 1
                    for i in range(len(self.products)):
                        if self.products[i].getSize() > 1:
                            if i in p_qg:
                                p_qg.remove(i)
                            else:
                                if self._product_contains_literals(i, [g, h]):
                                    swap_flag -= 1
                                la = self._signed_literal_from_product(i, g)
                                lb = self._signed_literal_from_product(i, h)
                                pivot_p, template = self._op_and(la, lb, swap_flag)
                                template_counts[template] += 1

                                if self.products[i].getSize() > 2:
                                    p_g = None
                                    for j in range(h + 1, self._opt_total_literals):
                                        if self._product_contains_literal(i, j):
                                            p_g = pivot_p
                                            lj = self._signed_literal_from_product(i, j)
                                            pivot_p, template = self._op_and(
                                                pivot_p, lj, False
                                            )
                                            template_counts[template] += 1
                                    if p_g is not None:
                                        p_qg.add(p_g)
                        else:
                            # Algorithm 4 line 29: SizeOf(P_i) <= 1 → ndot (•)
                            ndot += 1
                # else:
                #     # Algorithm 4 line 32: no product contains both I_g and I_h
                #     self.swap_literals_alg2(g, h)
        # Calculate AND plane statistics
        and_tdot = ndot
        total_and_operations = sum(p.getSize() - 1 for p in self.products if p.getSize() > 0)
        total_garbages = total_and_operations + self._opt_total_literals - and_tdot
        
        # Update quantum cost and other metrics (no XOR operations in AND plane)
        self.quantumCost += total_and_operations * 4
        # For Optimized RPLA: Total number of Gates = Total number of Templates
        self.gates = sum(template_counts.values())
        self.garbages += total_garbages
        self.ancilla_input_count = self._opt_total_literals - and_tdot
        
        # Calculate delay (AND plane only)
        self.delay = 0
        for product in self.products:
            self.delay = max(self.delay, product.delayCountAND)
        
        # Print results
        if not self.quiet:
            print("==========================================================")
            print("               Rearranged PRODUCTS ")
            self.showProducts()
            print("==========================================================")
            print(f"Total AND Operations: {total_and_operations}")
            print(f"TDOT                : {and_tdot}")
            print("Templates {α, β, γ, π} and {α′, β′, γ′, π′}")
            print(f"Total Templates α  : {template_counts['α']}")
            print(f"Total Templates β  : {template_counts['β']}")
            print(f"Total Templates γ  : {template_counts['γ']}")
            print(f"Total Templates π  : {template_counts['π']}")
            print(f"Total Templates α′ : {template_counts['α_prime']}")
            print(f"Total Templates β′ : {template_counts['β_prime']}")
            print(f"Total Templates γ′ : {template_counts['γ_prime']}")
            print(f"Total Templates π′ : {template_counts['π_prime']}")
            print(f"Garbage, GB         : {total_garbages}")
            print("==========================================================")
            print("                  Delay ")
            print("==========================================================")
            print("    Delay (AND) |  Delay (EXOR)   = Total Delay")
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

    def _signed_literal_from_product(self, product_idx: int, column_idx: int) -> int:
        """
        Map cube column `column_idx` in product `product_idx` to OpAND literal form:
        +k  = uncomplemented variable on line k
        -k  = complemented variable on line k
        where k = column_idx + 1 (1-based line id, matches abs() in _apply_template_and).

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

    def _op_and(self, lit_a: int, lit_b: int, swap_flag: int) -> tuple:
        """
        Algorithm 1: OpAND(p, q, swapFlag)
        Return result of AND operation and the template used.

        Templates {α, β, γ, π} and their complements {α', β', γ', π'} are used
        based on the complement status of literals p and q.

        Args lit_a, lit_b: signed 1-based line ids from the current product cube
        (_signed_literal_from_product) or intermediate results from _apply_template_and:
        positive = uncomplemented, negative = complemented.
        swap_flag selects the primed vs unprimed template family.
        """
        is_p_complemented = lit_a < 0
        is_q_complemented = lit_b < 0

        # Apply Algorithm 1 logic to select template
        if is_p_complemented:
            if is_q_complemented:
                # Both complemented
                template = 'π_prime' if swap_flag == 0 else 'π'
            else:
                # p complemented, q not complemented
                template = 'β_prime' if swap_flag == 0 else 'β'
        else:
            if is_q_complemented:
                # p not complemented, q complemented
                template = 'α_prime' if swap_flag == 0 else 'α'
            else:
                # Neither complemented
                template = 'γ_prime' if swap_flag == 0 else 'γ'

        # Apply the selected template operation
        # Since the actual template operations aren't specified in detail,
        # we implement a basic AND operation that considers complementation
        result = self._apply_template_and(lit_a, lit_b, template)

        return result, template

    def _apply_template_and(self, lit_a: int, lit_b: int, template: str) -> int:
        """
        Apply the selected template for AND operation.
        Since templates {α, β, γ, π} and their complements aren't fully specified,
        we implement based on logical AND semantics in RPLA context.
        """
        # Get absolute values for comparison
        abs_a = abs(lit_a)
        abs_b = abs(lit_b)

        # Basic AND logic: if same variable, result depends on complementation
        if abs_a == abs_b:
            # Same variable: AND of x and x = x, AND of x and ~x = 0 (impossible)
            # AND of ~x and ~x = ~x
            if lit_a == lit_b:
                # Both same sign: x ∧ x = x, ~x ∧ ~x = ~x
                return lit_a
            else:
                # Different signs: x ∧ ~x = 0 (contradiction)
                # In RPLA, this might indicate an invalid combination
                return 0  # Representing contradiction
        else:
            # Different variables: standard AND operation
            # For different variables, the result depends on the template
            if template in ['α', 'α_prime', 'β', 'β_prime']:
                # These templates might handle specific ordering
                if template in ['α', 'β']:
                    # Prefer certain ordering
                    return min(abs_a, abs_b) if lit_a > 0 and lit_b > 0 else -max(abs_a, abs_b)
                else:  # α', β'
                    return max(abs_a, abs_b) if lit_a < 0 and lit_b < 0 else -min(abs_a, abs_b)
            else:  # γ, γ', π, π'
                # Standard AND: combine literals
                # For simplicity, return the first literal (this would need refinement)
                return lit_a
