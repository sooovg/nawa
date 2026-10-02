"""Exact calculator tool (ROADMAP P6-02, ADR-0008).

Evaluates arithmetic on exact rationals (:class:`fractions.Fraction`). Never calls ``eval``/``exec``: the expression is
parsed with :mod:`ast` and only an allowlist of node types is interpreted. Anything else is refused with a reason.

Accepted: integer and decimal literals (``0.1`` is exactly 1/10, never a binary float), ``+ - * / // % **``, unary
``+ -``, parentheses, Arabic-Indic digits (normalised with :func:`nawa.evaluation.normalize.normalize_digits`), the
Arabic decimal separator ``٫``, and the signs ``×`` and ``÷``.

Refused: names, calls, attributes, subscripts, comparisons, strings, complex/scientific/hex literals, an exponent that is
not an integer, an exponent beyond ``MAX_EXPONENT``, an expression longer than ``MAX_CHARS``, an AST deeper than
``MAX_DEPTH``, any intermediate result with more than ``MAX_DIGITS`` digits in its numerator or denominator, and
division or modulo by zero. Limits are checked *before* computing a power, so a huge power cannot exhaust memory.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from fractions import Fraction

from nawa.evaluation.normalize import normalize_digits

MAX_CHARS = 512
MAX_DEPTH = 64
MAX_EXPONENT = 1024
MAX_DIGITS = 4096
_LITERAL = re.compile(r"(\d+(\.\d*)?|\.\d+)\Z")


class CalcError(ValueError):
    """The expression is refused or cannot be evaluated; ``code`` is a stable reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class CalcResult:
    value: Fraction

    @property
    def exact(self) -> str:
        """``"7"`` or ``"-1/3"``."""
        v = self.value
        return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"

    def decimal(self, places: int = 12) -> str:
        """Decimal rendering, rounded half away from zero to ``places`` places (exact arithmetic, no floats)."""
        if not isinstance(places, int) or isinstance(places, bool) or not 0 <= places <= 100:
            raise ValueError("places must be an int in 0..100")
        v = self.value
        sign = "-" if v < 0 else ""
        scaled = abs(v) * 10 ** places
        q, r = divmod(scaled.numerator, scaled.denominator)
        if 2 * r >= scaled.denominator:
            q += 1
        s = str(q).rjust(places + 1, "0")
        body = s if places == 0 else f"{s[:-places]}.{s[-places:]}"
        if places:
            body = body.rstrip("0").rstrip(".")
        return "0" if set(body) <= {"0", "."} else sign + body


def _check_size(v: Fraction) -> Fraction:
    if len(str(abs(v.numerator))) > MAX_DIGITS or len(str(v.denominator)) > MAX_DIGITS:
        raise CalcError("too_large", f"intermediate result exceeds {MAX_DIGITS} digits")
    return v


def _normalise(expr: str) -> str:
    return normalize_digits(expr).replace("٫", ".").replace("×", "*").replace("÷", "/").replace("−", "-")


def _eval(node: ast.AST, depth: int, src: str) -> Fraction:
    if depth > MAX_DEPTH:
        raise CalcError("too_deep", f"expression nesting exceeds {MAX_DEPTH}")
    if isinstance(node, ast.Expression):
        return _eval(node.body, depth + 1, src)
    if isinstance(node, ast.Constant):
        text = ast.get_source_segment(src, node) or ""
        if type(node.value) not in (int, float) or not _LITERAL.match(text):
            raise CalcError("bad_literal", f"literal {text!r} is not a plain integer or decimal")
        return _check_size(Fraction(text))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval(node.operand, depth + 1, src)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp):
        a = _eval(node.left, depth + 1, src)
        b = _eval(node.right, depth + 1, src)
        op = node.op
        if isinstance(op, ast.Add):
            return _check_size(a + b)
        if isinstance(op, ast.Sub):
            return _check_size(a - b)
        if isinstance(op, ast.Mult):
            return _check_size(a * b)
        if isinstance(op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if b == 0:
                raise CalcError("division_by_zero", "division or modulo by zero")
            if isinstance(op, ast.Div):
                return _check_size(a / b)
            return _check_size(Fraction(a // b) if isinstance(op, ast.FloorDiv) else a % b)
        if isinstance(op, ast.Pow):
            if b.denominator != 1:
                raise CalcError("non_integer_exponent", "exponent must be an integer (no roots: results stay exact)")
            e = b.numerator
            if abs(e) > MAX_EXPONENT:
                raise CalcError("too_large", f"|exponent| exceeds {MAX_EXPONENT}")
            if a == 0 and e < 0:
                raise CalcError("division_by_zero", "zero to a negative power")
            bound = max(len(str(abs(a.numerator))), len(str(a.denominator))) * abs(e)
            if bound > MAX_DIGITS + abs(e):
                raise CalcError("too_large", f"power would exceed {MAX_DIGITS} digits")
            return _check_size(a ** e)
    raise CalcError("not_allowed", f"{type(node).__name__} is not allowed in a calculation")


def calculate(expr: str) -> CalcResult:
    """Evaluate ``expr`` exactly, or raise :class:`CalcError` with a stable ``code``."""
    if not isinstance(expr, str):
        raise CalcError("bad_input", "expression must be a string")
    if len(expr) > MAX_CHARS:
        raise CalcError("too_long", f"expression longer than {MAX_CHARS} characters")
    src = _normalise(expr).strip()
    if not src:
        raise CalcError("bad_input", "empty expression")
    try:
        tree = ast.parse(src, mode="eval")
    except (SyntaxError, ValueError) as e:
        raise CalcError("syntax", str(e).splitlines()[0]) from None
    except RecursionError:
        raise CalcError("too_deep", f"expression nesting exceeds {MAX_DEPTH}") from None
    return CalcResult(_eval(tree, 0, src))
