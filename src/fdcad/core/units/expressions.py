"""Expression evaluation for typed values (`FDEF_SPEC.md` section 12, DECISIONS D66).

A small hand written tokenizer and recursive descent parser. Nothing is ever
passed to Python's ``eval``, so opening a file can never run code.

Grammar (``juxt`` lets ``1' 3"`` and ``1ft 3in`` add up):

    expr    := sum [("<" | ">" | "<=" | ">=" | "==" | "!=") sum]
    sum     := term (("+" | "-") term)*
    term    := unary (("*" | "/") unary)*
    unary   := "-" unary | juxt
    juxt    := primary (literal)*        only between literals with length units
    primary := literal | "(" expr ")" | name | qname | name "(" args ")"
    literal := number [number "/" number | "/" number] [unit]
    number  := digits ["." [digits]] [exponent] | "." digits [exponent]
    exponent := ("e" | "E") ["+" | "-"] digits        (D2620)
    qname   := '"' any text but a quote '"'

Formulas (text starting with ``=``) may also hold quoted names such as
``"Width"`` or ``"depth@Extrude 1"`` (equations manager, DECISIONS D390). A
double quote right after a number is the inch symbol; anywhere else it opens
a quoted name. Comparisons give 1 (true) or 0 (false), and
``if(condition, then, else)`` picks a value (D390).
"""

from __future__ import annotations

import functools
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

from fdcad.core.units.errors import ExpressionError


class Kind(Enum):
    """What a field holds. Decides the unit of bare numbers and of the result."""

    LENGTH = "length"
    ANGLE = "angle"
    NUMBER = "number"


class UnitSystem(Enum):
    """The part's unit system, used for bare numbers in length fields."""

    MM = "mm"
    IN = "in"


#: The deepest nesting of brackets and signs a formula may have (D709).
MAX_DEPTH = 100
MM_PER_UNIT: dict[UnitSystem, float] = {UnitSystem.MM: 1.0, UnitSystem.IN: 25.4}

# Dimension as exponents of (length, angle).
_Dim = tuple[int, int]
_NUMBER: _Dim = (0, 0)
_LENGTH: _Dim = (1, 0)
_ANGLE: _Dim = (0, 1)
_KIND_DIM: dict[Kind, _Dim] = {Kind.LENGTH: _LENGTH, Kind.ANGLE: _ANGLE, Kind.NUMBER: _NUMBER}

_LENGTH_UNITS: dict[str, float] = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}
_ANGLE_UNITS: dict[str, float] = {"deg": math.pi / 180.0, "rad": 1.0}
_SYMBOL_UNITS: dict[str, str] = {'"': "in", "'": "ft"}

# A number may end in an exponent (2e6, 1.5E-3, D2620). The exponent needs its
# digits, so "2e" or "2em" still reads e as a unit name; no unit starts with e.
_TOKEN = re.compile(
    r"\s*(?:(?P<num>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<sym><=|>=|==|!=|[-+*/(),'\"<>]))"
)


@dataclass(frozen=True)
class _Tok:
    kind: str  # "num", "name", "qname", "sym" or "end"
    text: str
    pos: int


@dataclass(frozen=True)
class _Q:
    """An intermediate value with its dimension.

    ``bare`` marks a plain number the user typed without a unit, which may still
    take the part unit (outside formulas only).
    """

    value: float
    dim: _Dim
    bare: bool = False


def _describe(dim: _Dim) -> str:
    return {_NUMBER: "a plain number", _LENGTH: "a length", _ANGLE: "an angle"}.get(
        dim, "a combined unit"
    )


def _tokenize(text: str) -> list[_Tok]:
    tokens: list[_Tok] = []
    pos = 0
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        match = _TOKEN.match(text, pos)
        if match is None:
            bad = text[pos:].lstrip()[0]
            raise ExpressionError(f"Unexpected character '{bad}'. Remove it and try again.")
        kind = match.lastgroup or "sym"
        if kind == "sym" and match.group(kind) == '"' and (not tokens or tokens[-1].kind != "num"):
            start = match.start(kind)
            end = text.find('"', start + 1)
            if end < 0:
                raise ExpressionError("A quoted name has no closing quote. Add the quote.")
            tokens.append(_Tok("qname", text[start + 1 : end].strip(), start))
            pos = end + 1
            continue
        tokens.append(_Tok(kind, match.group(kind), match.start(kind)))
        pos = match.end()
    tokens.append(_Tok("end", "", len(text)))
    return tokens


_Func = Callable[[list[_Q]], _Q]


def _trig(fn: Callable[[float], float], name: str) -> _Func:
    def apply(args: list[_Q]) -> _Q:
        _arg_count(name, args, 1, 1)
        (arg,) = args
        if arg.dim not in (_NUMBER, _ANGLE):
            raise ExpressionError(
                f"{name}() needs an angle or a number, not {_describe(arg.dim)}. "
                "Change the argument."
            )
        return _Q(fn(arg.value), _NUMBER)

    return apply


def _arg_count(name: str, args: list[_Q], low: int, high: int | None) -> None:
    if len(args) < low or (high is not None and len(args) > high):
        want = str(low) if high == low else f"at least {low}"
        raise ExpressionError(
            f"{name}() needs {want} argument(s), got {len(args)}. Fix the argument list."
        )


def _sqrt(args: list[_Q]) -> _Q:
    _arg_count("sqrt", args, 1, 1)
    (arg,) = args
    if arg.dim != _NUMBER:
        raise ExpressionError(
            f"sqrt() needs a plain number, not {_describe(arg.dim)}. Remove the unit."
        )
    if arg.value < 0:
        raise ExpressionError(
            "sqrt() of a negative number is not defined. Use a number of zero or more."
        )
    return _Q(math.sqrt(arg.value), _NUMBER, arg.bare)


def _same_dim(name: str, args: list[_Q]) -> None:
    if any(a.dim != args[0].dim for a in args):
        raise ExpressionError(
            f"{name}() needs all arguments in the same kind of unit. Change the units to match."
        )


def _abs(args: list[_Q]) -> _Q:
    _arg_count("abs", args, 1, 1)
    return _Q(abs(args[0].value), args[0].dim, args[0].bare)


def _round(args: list[_Q]) -> _Q:
    _arg_count("round", args, 1, 1)
    return _Q(float(round(args[0].value)), args[0].dim, args[0].bare)


def _min(args: list[_Q]) -> _Q:
    _arg_count("min", args, 1, None)
    _same_dim("min", args)
    return min(args, key=lambda a: a.value)


def _max(args: list[_Q]) -> _Q:
    _arg_count("max", args, 1, None)
    _same_dim("max", args)
    return max(args, key=lambda a: a.value)


def _inverse_trig(fn: Callable[[float], float], name: str) -> _Func:
    def apply(args: list[_Q]) -> _Q:
        _arg_count(name, args, 1, 1)
        (arg,) = args
        if arg.dim != _NUMBER:
            raise ExpressionError(
                f"{name}() needs a plain number, not {_describe(arg.dim)}. Remove the unit."
            )
        try:
            return _Q(fn(arg.value), _ANGLE)
        except ValueError as exc:
            raise ExpressionError(
                f"{name}() needs a number between -1 and 1. Change the argument."
            ) from exc

    return apply


def _rounding(fn: Callable[[float], float], name: str) -> _Func:
    def apply(args: list[_Q]) -> _Q:
        _arg_count(name, args, 1, 1)
        return _Q(float(fn(args[0].value)), args[0].dim, args[0].bare)

    return apply


def _atan2(args: list[_Q]) -> _Q:
    _arg_count("atan2", args, 2, 2)
    _same_dim("atan2", args)
    return _Q(math.atan2(args[0].value, args[1].value), _ANGLE)


# TR89 (D937): exp, ln, log10, sign, trunc, mod, pow, random and hyperbolic functions.


def _plain(fn: Callable[[float], float], name: str, positive: bool = False) -> _Func:
    """A function of one plain number giving a plain number."""

    def apply(args: list[_Q]) -> _Q:
        _arg_count(name, args, 1, 1)
        (arg,) = args
        if arg.dim != _NUMBER:
            raise ExpressionError(
                f"{name}() needs a plain number, not {_describe(arg.dim)}. Remove the unit."
            )
        if positive and arg.value <= 0:
            raise ExpressionError(f"{name}() needs a number above zero. Change the argument.")
        return _Q(fn(arg.value), _NUMBER)

    return apply


def _sign(args: list[_Q]) -> _Q:
    _arg_count("sign", args, 1, 1)
    value = args[0].value
    return _Q(float((value > 0) - (value < 0)), _NUMBER)


def _mod(args: list[_Q]) -> _Q:
    _arg_count("mod", args, 2, 2)
    _same_dim("mod", args)
    a, b = args
    if b.value == 0:
        raise ExpressionError("mod() cannot divide by zero. Use a second number that is not 0.")
    # Floored remainder: the result takes the sign of the second argument.
    return _Q(a.value - b.value * math.floor(a.value / b.value), a.dim, a.bare and b.bare)


def _pow(args: list[_Q]) -> _Q:
    _arg_count("pow", args, 2, 2)
    base, power = args
    if power.dim != _NUMBER:
        raise ExpressionError(
            f"pow() needs a plain number as the power, not {_describe(power.dim)}. "
            "Remove the unit from the second argument."
        )
    whole = float(power.value).is_integer()
    if base.dim != _NUMBER and not whole:
        raise ExpressionError(
            "pow() can raise a length or angle only to a whole number. "
            "Use a whole power, or remove the unit."
        )
    if base.value < 0 and not whole:
        raise ExpressionError(
            "pow() of a negative number needs a whole power. Change one of the arguments."
        )
    if base.value == 0 and power.value < 0:
        raise ExpressionError("pow() of 0 needs a power of 0 or more. Change the power.")
    n = round(power.value) if whole else 0
    dim = (base.dim[0] * n, base.dim[1] * n)
    return _Q(math.pow(base.value, power.value), dim, base.bare)


def _random(args: list[_Q]) -> _Q:
    """random(seed) gives 0 to 1; random(seed, low, high) gives low to high. The same
    seed always gives the same value, so a part rebuilds the same every time."""
    import random

    _arg_count("random", args, 1, 3)
    if len(args) == 2:
        raise ExpressionError(
            "random() needs a seed, or a seed, a low value and a high value. Add the high value."
        )
    seed = args[0]
    if seed.dim != _NUMBER:
        raise ExpressionError(
            f"random() needs a plain number as the seed, not {_describe(seed.dim)}. "
            "Remove the unit."
        )
    fraction = random.Random(repr(float(seed.value))).random()
    if len(args) == 1:
        return _Q(fraction, _NUMBER)
    low, high = args[1], args[2]
    _same_dim("random", [low, high])
    return _Q(low.value + (high.value - low.value) * fraction, low.dim, low.bare and high.bare)


def _truth(args: list[_Q], name: str, count: int | None) -> list[bool]:
    _arg_count(name, args, 1 if count is None else count, count)
    return [a.value != 0 for a in args]


def _and(args: list[_Q]) -> _Q:
    return _Q(1.0 if all(_truth(args, "and", None)) else 0.0, _NUMBER)


def _or(args: list[_Q]) -> _Q:
    return _Q(1.0 if any(_truth(args, "or", None)) else 0.0, _NUMBER)


def _not(args: list[_Q]) -> _Q:
    return _Q(0.0 if _truth(args, "not", 1)[0] else 1.0, _NUMBER)


def _if(args: list[_Q]) -> _Q:
    _arg_count("if", args, 3, 3)
    cond, yes, no = args
    if yes.dim != no.dim:
        raise ExpressionError(
            f"if() needs both results in the same kind of unit, not {_describe(yes.dim)} "
            f"and {_describe(no.dim)}. Change one result to match."
        )
    return yes if cond.value != 0 else no


_FUNCTIONS: dict[str, _Func] = {
    "sin": _trig(math.sin, "sin"),
    "cos": _trig(math.cos, "cos"),
    "tan": _trig(math.tan, "tan"),
    "sqrt": _sqrt,
    "abs": _abs,
    "round": _round,
    "min": _min,
    "max": _max,
    "asin": _inverse_trig(math.asin, "asin"),
    "acos": _inverse_trig(math.acos, "acos"),
    "atan": _inverse_trig(math.atan, "atan"),
    "atan2": _atan2,
    "floor": _rounding(math.floor, "floor"),
    "ceil": _rounding(math.ceil, "ceil"),
    "if": _if,
    "and": _and,
    "or": _or,
    "not": _not,
    "exp": _plain(math.exp, "exp"),
    "ln": _plain(math.log, "ln", positive=True),
    "log10": _plain(math.log10, "log10", positive=True),
    "sign": _sign,
    "trunc": _rounding(math.trunc, "trunc"),
    "mod": _mod,
    "pow": _pow,
    "random": _random,
    "sinh": _plain(math.sinh, "sinh"),
    "cosh": _plain(math.cosh, "cosh"),
    "tanh": _plain(math.tanh, "tanh"),
}

#: Function names, for the equations manager's help and error messages.
FUNCTION_NAMES: tuple[str, ...] = tuple(_FUNCTIONS)


def reserved_name(name: str) -> str | None:
    """Why ``name`` cannot name a variable or value, when it is a unit, a function or
    pi (TR310, D919): "2 mm" reads mm as the unit, so a variable called mm could not be
    used after a number. None when the name is free."""
    clean = name.strip()
    if clean in _LENGTH_UNITS or clean in _ANGLE_UNITS:
        return (
            f"{clean} is a unit name, so a number typed before it reads as that unit. "
            f"Choose another name, such as {clean}_value."
        )
    if clean in _FUNCTIONS or clean == "pi":
        return (
            f"{clean} is the name of a formula function. Choose another name, such as "
            f"{clean}_value."
        )
    return None


_COMPARE = ("<", ">", "<=", ">=", "==", "!=")


class _Parser:
    def __init__(
        self,
        text: str,
        formula: bool,
        units: UnitSystem,
        variables: Mapping[str, tuple[Kind, float]],
    ) -> None:
        self.tokens = _tokenize(text)
        self.i = 0
        self.formula = formula
        self.units = units
        self.variables = variables
        self.depth = 0

    def _deeper(self) -> None:
        """Count one more nesting level; refuse very deep formulas (audit D12 item 8,
        D709), which would otherwise exhaust the Python stack."""
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ExpressionError(
                f"The formula nests more than {MAX_DEPTH} levels deep. "
                "Use fewer brackets or signs, or split it into variables."
            )

    # Token helpers --------------------------------------------------------

    @property
    def tok(self) -> _Tok:
        return self.tokens[self.i]

    def peek(self, offset: int = 1) -> _Tok:
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)]

    def take(self) -> _Tok:
        tok = self.tok
        self.i += 1
        return tok

    def is_sym(self, text: str, tok: _Tok | None = None) -> bool:
        t = tok or self.tok
        return t.kind == "sym" and t.text == text

    def expect_sym(self, text: str) -> None:
        if not self.is_sym(text):
            raise self.unexpected(f"Expected '{text}'")
        self.take()

    def unexpected(self, prefix: str = "Unexpected input") -> ExpressionError:
        tok = self.tok
        if tok.kind == "end":
            return ExpressionError(
                f"{prefix} at the end. The expression is incomplete. Finish the expression."
            )
        return ExpressionError(f"{prefix} near '{tok.text}'. Check the expression.")

    # Grammar --------------------------------------------------------------

    def parse(self) -> _Q:
        if self.tok.kind == "end":
            raise ExpressionError("Enter a value.")
        result = self.expr()
        if self.tok.kind != "end":
            raise self.unexpected()
        if not math.isfinite(result.value):
            # Infinite and not a number results could not be saved (audit D3 item 13).
            raise ExpressionError(
                "The value is too large or not a number. Check the formula for a division "
                "by zero or a huge power."
            )
        return result

    def expr(self) -> _Q:
        self._deeper()
        try:
            return self._expr()
        finally:
            self.depth -= 1

    def _expr(self) -> _Q:
        left = self.sum()
        if self.tok.kind == "sym" and self.tok.text in _COMPARE:
            op = self.take().text
            right = self.sum()
            left = self.compare(left, right, op)
        return left

    def sum(self) -> _Q:
        left = self.term()
        while self.is_sym("+") or self.is_sym("-"):
            op = self.take().text
            right = self.term()
            left = self.add(left, right, op)
        return left

    def term(self) -> _Q:
        left = self.unary()
        while self.is_sym("*") or self.is_sym("/"):
            op = self.take().text
            right = self.unary()
            left = self.multiply(left, right, op)
        return left

    def unary(self) -> _Q:
        if self.is_sym("-"):
            self.take()
            self._deeper()
            try:
                inner = self.unary()
            finally:
                self.depth -= 1
            return _Q(-inner.value, inner.dim, inner.bare)
        return self.juxt()

    def juxt(self) -> _Q:
        if self.tok.kind != "num":
            return self.primary()
        first, has_unit = self.literal()
        total = first
        # Feet and inches written side by side: 1' 3", 1ft 3in, 1' 3 1/2".
        while self.tok.kind == "num" and has_unit and total.dim == _LENGTH:
            nxt, nxt_unit = self.literal()
            if not nxt_unit or nxt.dim != _LENGTH:
                raise ExpressionError(
                    "Two values are next to each other without an operator. Add + or another unit."
                )
            total = _Q(total.value + nxt.value, _LENGTH)
        if self.tok.kind == "num":
            raise self.unexpected("Missing operator")
        return total

    def literal(self) -> tuple[_Q, bool]:
        """Parse a number, fraction or mixed number with an optional unit.

        A number right after a division sign is a plain divisor, so ``24mm / 2 / 3``
        divides twice instead of reading ``2/3`` as a fraction.
        """
        after_divide = self.i > 0 and self.is_sym("/", self.tokens[self.i - 1])
        whole = self.take()
        value = float(whole.text)
        if after_divide:
            return self.unit(value)
        # Mixed number: integer, space, fraction (1 3/4).
        if (
            self.tok.kind == "num"
            and self.is_sym("/", self.peek())
            and self.peek(2).kind == "num"
            and whole.text.isdigit()
        ):
            num = float(self.take().text)
            self.take()
            den = float(self.take().text)
            value += self.divide(num, den)
        # Fraction binds before arithmetic (7/8 mm).
        elif self.is_sym("/") and self.peek().kind == "num":
            self.take()
            value = self.divide(value, float(self.take().text))
        return self.unit(value)

    def divide(self, num: float, den: float) -> float:
        if den == 0:
            raise ExpressionError("Division by zero. Change the divisor.")
        return num / den

    def unit(self, value: float) -> tuple[_Q, bool]:
        tok = self.tok
        if tok.kind == "sym" and tok.text in _SYMBOL_UNITS:
            self.take()
            return _Q(value * _LENGTH_UNITS[_SYMBOL_UNITS[tok.text]], _LENGTH), True
        if tok.kind == "name":
            name = tok.text.lower()
            if name in _LENGTH_UNITS:
                self.take()
                return _Q(value * _LENGTH_UNITS[name], _LENGTH), True
            if name in _ANGLE_UNITS:
                self.take()
                return _Q(value * _ANGLE_UNITS[name], _ANGLE), True
            raise ExpressionError(f"Unknown unit '{tok.text}'. Use mm, cm, m, in, ft, deg or rad.")
        return _Q(value, _NUMBER, bare=True), False

    def primary(self) -> _Q:
        tok = self.tok
        if self.is_sym("("):
            self.take()
            inner = self.expr()
            self.expect_sym(")")
            return inner
        if tok.kind in ("name", "qname"):
            return self.name()
        raise self.unexpected()

    def name(self) -> _Q:
        tok = self.take()
        if not self.formula:
            raise ExpressionError(
                f"'{tok.text}' needs a formula. Start the value with = to use variables."
            )
        if tok.kind == "qname":
            if tok.text not in self.variables:
                raise ExpressionError(f'Unknown name "{tok.text}". Check the name and its case.')
            kind, value = self.variables[tok.text]
            return _Q(value, _KIND_DIM[kind])
        if self.is_sym("("):
            func = _FUNCTIONS.get(tok.text)
            if func is None:
                raise ExpressionError(
                    f"Unknown function '{tok.text}'. Use one of: {', '.join(FUNCTION_NAMES)}."
                )
            self.take()
            args = [self.expr()]
            while self.is_sym(","):
                self.take()
                args.append(self.expr())
            self.expect_sym(")")
            try:
                return func(args)
            except (OverflowError, ValueError) as exc:
                if isinstance(exc, ExpressionError):
                    raise
                raise ExpressionError(
                    f"'{tok.text}' cannot work out that value. Check what the formula passes to it."
                ) from exc
        if tok.text == "pi":
            return _Q(math.pi, _NUMBER)
        if tok.text not in self.variables:
            raise ExpressionError(f"Unknown variable '{tok.text}'. Check the name and its case.")
        kind, value = self.variables[tok.text]
        return _Q(value, _KIND_DIM[kind])

    # Arithmetic -----------------------------------------------------------

    def promote(self, q: _Q, dim: _Dim) -> _Q:
        """Outside formulas, a bare number next to a length or angle takes the default unit."""
        if self.formula or not q.bare or dim == _NUMBER:
            return q
        if dim == _LENGTH:
            return _Q(q.value * MM_PER_UNIT[self.units], _LENGTH)
        if dim == _ANGLE:
            return _Q(math.radians(q.value), _ANGLE)
        return q

    def add(self, left: _Q, right: _Q, op: str) -> _Q:
        left = self.promote(left, right.dim)
        right = self.promote(right, left.dim)
        if left.dim != right.dim:
            raise ExpressionError(
                f"Cannot add {_describe(left.dim)} and {_describe(right.dim)}. "
                "Give both values the same kind of unit."
            )
        value = left.value + right.value if op == "+" else left.value - right.value
        return _Q(value, left.dim, left.bare and right.bare)

    def compare(self, left: _Q, right: _Q, op: str) -> _Q:
        left = self.promote(left, right.dim)
        right = self.promote(right, left.dim)
        if left.dim != right.dim:
            raise ExpressionError(
                f"Cannot compare {_describe(left.dim)} and {_describe(right.dim)}. "
                "Give both values the same kind of unit."
            )
        a, b = left.value, right.value
        tol = 1e-9 * max(1.0, abs(a), abs(b))
        results = {
            "<": a < b - tol,
            ">": a > b + tol,
            "<=": a <= b + tol,
            ">=": a >= b - tol,
            "==": abs(a - b) <= tol,
            "!=": abs(a - b) > tol,
        }
        return _Q(1.0 if results[op] else 0.0, _NUMBER)

    def multiply(self, left: _Q, right: _Q, op: str) -> _Q:
        bare = left.bare and right.bare
        if op == "*":
            dim = (left.dim[0] + right.dim[0], left.dim[1] + right.dim[1])
            return _Q(left.value * right.value, dim, bare)
        dim = (left.dim[0] - right.dim[0], left.dim[1] - right.dim[1])
        return _Q(self.divide(left.value, right.value), dim, bare)


def evaluate(
    text: str,
    kind: Kind,
    units: UnitSystem,
    variables: Mapping[str, tuple[Kind, float]] | None = None,
) -> float:
    """Evaluate ``text`` for a field of ``kind``.

    Returns millimetres for lengths, radians for angles, a plain float for numbers.
    ``variables`` maps a name to its kind and evaluated internal value.
    Raises ExpressionError with a user facing message on any problem.
    """
    stripped = text.strip()
    if not stripped.startswith("="):
        return _plain_value(stripped, kind, units)
    return _evaluate(stripped[1:], True, kind, units, variables or {})


@functools.lru_cache(maxsize=4096)
def _plain_value(body: str, kind: Kind, units: UnitSystem) -> float:
    """A typed value without a formula: it uses no variables, so the same text always
    gives the same number and is read once (D2663). A rebuild of the 200 feature part
    read its 395 values again every time. Errors are not kept: they are raised again."""
    return _evaluate(body, False, kind, units, {})


def _evaluate(
    body: str,
    formula: bool,
    kind: Kind,
    units: UnitSystem,
    variables: Mapping[str, tuple[Kind, float]],
) -> float:
    result = _Parser(body, formula, units, variables).parse()
    want = _KIND_DIM[kind]
    if result.dim == want:
        return result.value
    if result.dim == _NUMBER:
        # A plain number result takes the field's default unit (D66).
        if kind is Kind.LENGTH:
            mm = result.value * MM_PER_UNIT[units]
            if not math.isfinite(mm):  # 1e308 in an inch part (D2671)
                raise ExpressionError(
                    "The value is too large or not a number. Type a smaller value."
                )
            return mm
        if kind is Kind.ANGLE:
            return math.radians(result.value)
    raise ExpressionError(
        f"This field needs {_describe(want)}, but the value is {_describe(result.dim)}. "
        "Change the unit or the formula."
    )


def quoted_spans(text: str) -> list[tuple[int, int]]:
    """Where the quoted names of a formula are: ``(start, end)`` of the text between
    the quotes, as indexes into ``text``. Plain values and unreadable text have none.
    """
    lead = len(text) - len(text.lstrip())
    if not text[lead:].startswith("="):
        return []
    body = text[lead + 1 :]
    try:
        tokens = _tokenize(body)
    except ExpressionError:
        return []
    offset = lead + 1
    out: list[tuple[int, int]] = []
    for tok in tokens:
        if tok.kind == "qname":
            end = body.find('"', tok.pos + 1)
            out.append((offset + tok.pos + 1, offset + end))
    return out


def references(text: str) -> set[str]:
    """Names a formula uses: bare names that are not functions or units, and quoted names.

    Plain values (no leading ``=``) use none. Text that cannot be read uses none.
    """
    stripped = text.strip()
    if not stripped.startswith("="):
        return set()
    try:
        tokens = _tokenize(stripped[1:])
    except ExpressionError:
        return set()
    out: set[str] = set()
    for i, tok in enumerate(tokens):
        if tok.kind == "qname":
            out.add(tok.text)
        elif tok.kind == "name":
            after_number = i > 0 and tokens[i - 1].kind == "num"
            call = tokens[i + 1].kind == "sym" and tokens[i + 1].text == "("
            if not after_number and not call and tok.text != "pi":
                out.add(tok.text)
    return out


def result_kind(
    text: str, units: UnitSystem, variables: Mapping[str, tuple[Kind, float]] | None = None
) -> Kind:
    """The kind of value ``text`` gives on its own: a length, an angle or a plain number.

    Used to pick the kind of a new global variable (D390). A value without a
    unit is a plain number. Raises ExpressionError.
    """
    stripped = text.strip()
    formula = stripped.startswith("=")
    body = stripped[1:] if formula else stripped
    result = _Parser(body, True, units, variables or {}).parse()
    for kind, dim in _KIND_DIM.items():
        if result.dim == dim:
            return kind
    raise ExpressionError(f"The value is {_describe(result.dim)}. Use a length, angle or number.")
