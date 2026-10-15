"""Parse and validate Boolean expressions for custom reversible gates (A–D, &, |, ^, ~)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_MAX_EXPR_LEN = 512
_MAX_LINES = 4  # max output lines (1×1 … 4×4)

CUSTOM_OUTPUT_LABELS = ("P", "Q", "R", "S")

_VAR_SPI = {"A": "va", "B": "vb", "C": "vc", "D": "vd"}


class CustomExprError(ValueError):
    pass


@dataclass(frozen=True)
class Const:
    v: int


@dataclass(frozen=True)
class Var:
    name: str  # "A", "B", "C", "D"


@dataclass(frozen=True)
class Not:
    x: Any  # Node


@dataclass(frozen=True)
class And:
    a: Any
    b: Any


@dataclass(frozen=True)
class Or:
    a: Any
    b: Any


@dataclass(frozen=True)
class Xor:
    a: Any
    b: Any


Node = Const | Var | Not | And | Or | Xor


def _tok(s: str) -> list[str]:
    s = re.sub(r"\s+", "", s)
    if len(s) > _MAX_EXPR_LEN:
        raise CustomExprError(f"Expression too long (max {_MAX_EXPR_LEN} non-space chars)")
    out: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c in "()&|^~!":
            out.append(c)
            i += 1
            continue
        if c.isalpha():
            j = i
            while j < len(s) and s[j].isalpha():
                j += 1
            word = s[i:j].upper()
            out.append(word)
            i = j
            continue
        if c.isdigit():
            out.append(c)
            i += 1
            continue
        raise CustomExprError(f"Invalid character {c!r} in expression")
    return out


class _Parser:
    def __init__(self, tokens: list[str], allowed_vars: frozenset[str]) -> None:
        self.t = tokens
        self.i = 0
        self.allowed_vars = allowed_vars

    def peek(self) -> str | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def eat(self, expected: str | None = None) -> str:
        tok = self.peek()
        if tok is None:
            raise CustomExprError("Unexpected end of expression")
        if expected is not None and tok != expected:
            raise CustomExprError(f"Expected {expected!r}, got {tok!r}")
        self.i += 1
        return tok

    def parse(self) -> Node:
        n = self.parse_or()
        if self.peek() is not None:
            raise CustomExprError("Unexpected trailing tokens")
        return n

    def parse_or(self) -> Node:
        n = self.parse_xor()
        while self.peek() == "|":
            self.eat("|")
            n = Or(n, self.parse_xor())
        return n

    def parse_xor(self) -> Node:
        n = self.parse_and()
        while self.peek() == "^":
            self.eat("^")
            n = Xor(n, self.parse_and())
        return n

    def parse_and(self) -> Node:
        n = self.parse_unary()
        while self.peek() == "&":
            self.eat("&")
            n = And(n, self.parse_unary())
        return n

    def parse_unary(self) -> Node:
        if self.peek() in ("!", "~"):
            self.eat()
            return Not(self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> Node:
        tok = self.peek()
        if tok == "(":
            self.eat("(")
            n = self.parse_or()
            self.eat(")")
            return n
        if tok in ("0", "1"):
            self.eat()
            return Const(int(tok))
        if tok in ("TRUE", "FALSE"):
            self.eat()
            return Const(1 if tok == "TRUE" else 0)
        if tok in self.allowed_vars:
            self.eat()
            return Var(tok)
        raise CustomExprError(f"Expected variable ({', '.join(sorted(self.allowed_vars))}), constant, or '('")


def _allowed_vars_for_width(width: int) -> frozenset[str]:
    if width == 1:
        return frozenset({"A"})
    if width == 2:
        return frozenset({"A", "B"})
    if width == 3:
        return frozenset({"A", "B", "C"})
    if width == 4:
        return frozenset({"A", "B", "C", "D"})
    raise CustomExprError(f"Invalid custom gate width {width} (expected 1–4)")


def parse_expression(expr: str, width: int) -> Node:
    toks = _tok(expr)
    if not toks:
        raise CustomExprError("Empty expression")
    return _Parser(toks, _allowed_vars_for_width(width)).parse()


def eval_node(n: Node, bits: tuple[int, ...]) -> int:
    idx = {"A": 0, "B": 1, "C": 2, "D": 3}
    if isinstance(n, Const):
        return n.v & 1
    if isinstance(n, Var):
        i = idx[n.name]
        if i >= len(bits):
            raise ValueError("eval_node: bits too short for variable")
        return bits[i] & 1
    if isinstance(n, Not):
        return 1 - eval_node(n.x, bits)
    if isinstance(n, And):
        return eval_node(n.a, bits) & eval_node(n.b, bits)
    if isinstance(n, Or):
        return eval_node(n.a, bits) | eval_node(n.b, bits)
    if isinstance(n, Xor):
        return eval_node(n.a, bits) ^ eval_node(n.b, bits)
    raise TypeError(n)


def compile_node_to_verilog(n: Node) -> str:
    """Emit a Verilog expression using ports ``a``…``d`` (matches reversible-gate RTL)."""

    def inner(node: Node) -> str:
        if isinstance(node, Const):
            return "1'b0" if node.v == 0 else "1'b1"
        if isinstance(node, Var):
            m = {"A": "a", "B": "b", "C": "c", "D": "d"}
            return m[node.name]
        if isinstance(node, Not):
            return f"(~{inner(node.x)})"
        if isinstance(node, And):
            return f"({inner(node.a)} & {inner(node.b)})"
        if isinstance(node, Or):
            return f"({inner(node.a)} | {inner(node.b)})"
        if isinstance(node, Xor):
            return f"({inner(node.a)} ^ {inner(node.b)})"
        raise TypeError(node)

    return inner(n)


def compile_to_ngspice_logic(n: Node) -> str:
    """Emit 0/1-valued subexpression for use as v(vdd)*(...). Uses ngspice u() step."""

    def inner(node: Node) -> str:
        if isinstance(node, Const):
            return "1" if node.v else "0"
        if isinstance(node, Var):
            vn = _VAR_SPI[node.name]
            return f"u(v({vn})-0.9*v(vdd))"
        if isinstance(node, Not):
            return f"(1-({inner(node.x)}))"
        if isinstance(node, And):
            return f"(({inner(node.a)})*({inner(node.b)}))"
        if isinstance(node, Or):
            a, b = inner(node.a), inner(node.b)
            return f"u(({a})+({b})-0.5)"
        if isinstance(node, Xor):
            a, b = inner(node.a), inner(node.b)
            return f"abs(({a})-({b}))"
        raise TypeError(node)

    return inner(n)


def validate_reversible_permutation(nodes: list[Node], width: int) -> None:
    seen: set[tuple[int, ...]] = set()
    for k in range(1 << width):
        bits = tuple((k >> i) & 1 for i in range(width))
        key = tuple(eval_node(node, bits) for node in nodes)
        if key in seen:
            raise CustomExprError(
                f"Mapping is not reversible: duplicate output {''.join(str(x) for x in key)} "
                f"for distinct inputs (need a bijection)."
            )
        seen.add(key)
    if len(seen) != (1 << width):
        raise CustomExprError("Internal validation failed for permutation")


def eval_outputs_tuple(nodes: list[Node], bits: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(eval_node(n, bits) for n in nodes)


def build_custom_behavioral_body(nodes: list[Node], vdd: float) -> str:
    """B-sources for vp, vq, vr[, vs] from expressions (ideal; u() threshold @ 0.9*vdd)."""
    _ = vdd
    outs = ["vp", "vq", "vr", "vs"][: len(nodes)]
    lines = []
    for outn, node in zip(outs, nodes):
        logic = compile_to_ngspice_logic(node)
        lines.append(f"B{outn} {outn} 0 V = v(vdd)*({logic})")
    return "\n".join(lines) + "\n"


def normalize_custom_expressions(raw: list[str]) -> list[str]:
    exprs = [x.strip() for x in raw if x.strip()]
    if len(exprs) not in (1, 2, 3, 4):
        raise CustomExprError(
            "Provide 1, 2, 3, or 4 non-empty output expressions (one per line). "
            "Line 1 = P only for a 1×1 gate (e.g. ~A); then Q, R, S for wider reversibles."
        )
    return exprs


__all__ = [
    "CUSTOM_OUTPUT_LABELS",
    "CustomExprError",
    "Node",
    "parse_expression",
    "eval_node",
    "eval_outputs_tuple",
    "validate_reversible_permutation",
    "compile_node_to_verilog",
    "build_custom_behavioral_body",
    "normalize_custom_expressions",
]
