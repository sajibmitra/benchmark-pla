"""Qiskit page (/qiskit) — four realization cost methodologies."""
from .gaur2024 import calculate_gaur2024_cost
from .standard_quantum import calculate_standard_quantum_cost
from .umg_ung import calculate_umg_ung_cost
from .zhou2026 import calculate_zhou2026_cost

QUANTUM_COST_FORMULA = {
    "standard_quantum": "Σ(CNOT) + Σ(Toffoli) — unit weight per native Qiskit gate",
    "umg_ung": "Σ(CNOT) + 5 × Σ(UMG + UNG templates)",
    "gaur2024": "FOM = qubit_width × Toffoli_depth — from Qiskit QuantumCircuit (Gaur2024)",
    "zhou2026": "C = T_adj + W_error×E — LNN-routed Qiskit circuit (Zhou2026 EDDQC)",
}

__all__ = [
    "QUANTUM_COST_FORMULA",
    "calculate_gaur2024_cost",
    "calculate_standard_quantum_cost",
    "calculate_umg_ung_cost",
    "calculate_zhou2026_cost",
]
