"""Reversible gate definitions with input-output mappings and truth tables."""
from typing import TypedDict


class GateMapping(TypedDict):
    """Definition of a reversible gate with its input-output characteristics."""
    name: str
    shortname: str
    description: str
    inputs: int
    outputs: int
    input_labels: list[str]
    output_labels: list[str]
    equations: list[str]
    truth_table: list[tuple[int, ...]]  # Each tuple is (input_bits..., output_bits...)


# Truth tables: (A, B, C, P, Q, R)
GATE_DEFINITIONS: dict[str, GateMapping] = {
    "NOT": {
        "name": "NOT Gate",
        "shortname": "NOT",
        "description": "1×1 unitary reversible gate: single line with output P = ¬A",
        "inputs": 1,
        "outputs": 1,
        "input_labels": ["A"],
        "output_labels": ["P"],
        "equations": ["P = ¬A"],
        "truth_table": [
            (0, 1),
            (1, 0),
        ],
    },
    "FG": {
        "name": "Feynman Gate",
        "shortname": "FG",
        "description": "2×2 reversible gate: P = A (buffer), Q = A ⊕ B (controlled NOT)",
        "inputs": 2,
        "outputs": 2,
        "input_labels": ["A", "B"],
        "output_labels": ["P", "Q"],
        "equations": ["P = A", "Q = A ⊕ B"],
        "truth_table": [
            (0, 0, 0, 0),
            (0, 1, 0, 1),
            (1, 0, 1, 1),
            (1, 1, 1, 0),
        ],
    },
    "TG": {
        "name": "Toffoli Gate",
        "shortname": "TG",
        "description": "3×3 reversible gate: P = A, Q = B, R = C ⊕ (A ∧ B)",
        "inputs": 3,
        "outputs": 3,
        "input_labels": ["A", "B", "C"],
        "output_labels": ["P", "Q", "R"],
        "equations": ["P = A", "Q = B", "R = C ⊕ (A ∧ B)"],
        "truth_table": [
            (0, 0, 0, 0, 0, 0),
            (0, 0, 1, 0, 0, 1),
            (0, 1, 0, 0, 1, 0),
            (0, 1, 1, 0, 1, 1),
            (1, 0, 0, 1, 0, 0),
            (1, 0, 1, 1, 0, 1),
            (1, 1, 0, 1, 1, 1),
            (1, 1, 1, 1, 1, 0),
        ],
    },
    "FRG": {
        "name": "Fredkin Gate",
        "shortname": "FRG",
        "description": "3×3 reversible gate: P = A, Q and R are conditionally swapped based on A",
        "inputs": 3,
        "outputs": 3,
        "input_labels": ["A", "B", "C"],
        "output_labels": ["P", "Q", "R"],
        "equations": [
            "P = A",
            "Q = (¬A ∧ B) ∨ (A ∧ C)",
            "R = (¬A ∧ C) ∨ (A ∧ B)",
        ],
        "truth_table": [
            (0, 0, 0, 0, 0, 0),
            (0, 0, 1, 0, 1, 0),
            (0, 1, 0, 0, 0, 1),
            (0, 1, 1, 0, 1, 1),
            (1, 0, 0, 1, 0, 0),
            (1, 0, 1, 1, 1, 0),
            (1, 1, 0, 1, 0, 1),
            (1, 1, 1, 1, 1, 1),
        ],
    },
    "PG": {
        "name": "Peres Gate",
        "shortname": "PG",
        "description": "3×3 reversible gate: P = A, Q = A ⊕ B, R = C ⊕ (A ∧ B)",
        "inputs": 3,
        "outputs": 3,
        "input_labels": ["A", "B", "C"],
        "output_labels": ["P", "Q", "R"],
        "equations": ["P = A", "Q = A ⊕ B", "R = C ⊕ (A ∧ B)"],
        "truth_table": [
            (0, 0, 0, 0, 0, 0),
            (0, 0, 1, 0, 0, 1),
            (0, 1, 0, 0, 1, 0),
            (0, 1, 1, 0, 1, 1),
            (1, 0, 0, 1, 1, 0),
            (1, 0, 1, 1, 1, 1),
            (1, 1, 0, 1, 0, 1),
            (1, 1, 1, 1, 0, 0),
        ],
    },
    "MUX": {
        "name": "Multiplexer Gate",
        "shortname": "MUX",
        "description": "3×3 reversible gate: P = A, Q = A ⊕ B ⊕ C, R = (¬A ∧ C) ⊕ (A ∧ B)",
        "inputs": 3,
        "outputs": 3,
        "input_labels": ["A", "B", "C"],
        "output_labels": ["P", "Q", "R"],
        "equations": ["P = A", "Q = A ⊕ B ⊕ C", "R = (¬A ∧ C) ⊕ (A ∧ B)"],
        "truth_table": [
            (0, 0, 0, 0, 0, 0),
            (0, 0, 1, 0, 1, 1),
            (0, 1, 0, 0, 1, 0),
            (0, 1, 1, 0, 0, 1),
            (1, 0, 0, 1, 1, 0),
            (1, 0, 1, 1, 0, 0),
            (1, 1, 0, 1, 0, 1),
            (1, 1, 1, 1, 1, 1),
        ],
    },
    "UMG": {
        "name": "Universal Multiplexer Gate",
        "shortname": "UMG",
        "description": "3×3 reversible gate: line A is preserved on P; Q = B ⊕ C; R = (¬A ∧ C) ⊕ (A ∧ B)",
        "inputs": 3,
        "outputs": 3,
        "input_labels": ["A", "B", "C"],
        "output_labels": ["P", "Q", "R"],
        "equations": ["P = A", "Q = B ⊕ C", "R = (¬A ∧ C) ⊕ (A ∧ B)"],
        "truth_table": [
            (0, 0, 0, 0, 0, 0),
            (0, 0, 1, 0, 1, 1),
            (0, 1, 0, 0, 1, 0),
            (0, 1, 1, 0, 0, 1),
            (1, 0, 0, 1, 0, 0),
            (1, 0, 1, 1, 1, 0),
            (1, 1, 0, 1, 1, 1),
            (1, 1, 1, 1, 0, 1),
        ],
    },
    "UNG": {
        "name": "Universal NOR Gate",
        "shortname": "UNG",
        "description": "3×3 reversible gate: P = A, Q = B, R = (A ∨ B) ⊕ C",
        "inputs": 3,
        "outputs": 3,
        "input_labels": ["A", "B", "C"],
        "output_labels": ["P", "Q", "R"],
        "equations": ["P = A", "Q = B", "R = (A ∨ B) ⊕ C"],
        "truth_table": [
            (0, 0, 0, 0, 0, 0),
            (0, 0, 1, 0, 0, 1),
            (0, 1, 0, 0, 1, 1),
            (0, 1, 1, 0, 1, 0),
            (1, 0, 0, 1, 0, 1),
            (1, 0, 1, 1, 0, 0),
            (1, 1, 0, 1, 1, 1),
            (1, 1, 1, 1, 1, 0),
        ],
    },
    "NMG": {
        "name": "NMG Gate",
        "shortname": "NMG",
        "description": "3×3 reversible gate: P = A ⊕ B, Q = (B ∧ ¬C) ⊕ (A ∧ C), R = (¬B ∧ C) ⊕ (A ∧ ¬C)",
        "inputs": 3,
        "outputs": 3,
        "input_labels": ["A", "B", "C"],
        "output_labels": ["P", "Q", "R"],
        "equations": [
            "P = A ⊕ B",
            "Q = (B ∧ ¬C) ⊕ (A ∧ C)",
            "R = (¬B ∧ C) ⊕ (A ∧ ¬C)",
        ],
        "truth_table": [
            (0, 0, 0, 0, 0, 0),
            (0, 0, 1, 0, 0, 1),
            (0, 1, 0, 1, 1, 0),
            (0, 1, 1, 1, 0, 0),
            (1, 0, 0, 1, 0, 1),
            (1, 0, 1, 1, 1, 1),
            (1, 1, 0, 0, 1, 1),
            (1, 1, 1, 0, 1, 0),
        ],
    },
}


def get_gate_mapping(gate: str) -> GateMapping | None:
    """Get the definition and truth table for a reversible gate."""
    return GATE_DEFINITIONS.get(gate.upper())


def get_all_gates() -> dict[str, GateMapping]:
    """Get all gate definitions."""
    return GATE_DEFINITIONS


__all__ = [
    "GateMapping",
    "GATE_DEFINITIONS",
    "get_gate_mapping",
    "get_all_gates",
]
