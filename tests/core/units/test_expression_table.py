"""Table tests for typed values (FDEF_SPEC section 12, DECISIONS D66).

Expected values are written as arithmetic, never as hand computed decimals.
"""

import math

import pytest

from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate

L, A, N = Kind.LENGTH, Kind.ANGLE, Kind.NUMBER
MM, IN = UnitSystem.MM, UnitSystem.IN
INCH = 25.4
VARS = {"Width": (L, 63.5), "Angle": (A, math.radians(30)), "Count": (N, 4.0)}

VALID = [
    # Bare numbers take the part unit, or degrees in angle fields.
    pytest.param("20", L, MM, 20, id="bare-mm"),
    pytest.param("20", L, IN, 20 * INCH, id="bare-in"),
    pytest.param("30", A, MM, math.radians(30), id="bare-angle-deg"),
    pytest.param("3", N, MM, 3.0, id="bare-number"),
    pytest.param("2 * 3.5", N, IN, 7.0, id="number-arith"),
    # Units, case and spacing.
    pytest.param("20mm", L, IN, 20, id="mm"),
    pytest.param("2cm", L, MM, 20, id="cm"),
    pytest.param("1.5m", L, MM, 1500, id="m"),
    pytest.param("2in", L, MM, 2 * INCH, id="in"),
    pytest.param("1ft", L, MM, 304.8, id="ft"),
    pytest.param('3"', L, MM, 3 * INCH, id="inch-symbol"),
    pytest.param("2'", L, MM, 2 * 304.8, id="foot-symbol"),
    pytest.param("20MM", L, IN, 20, id="unit-upper"),
    pytest.param("2In", L, MM, 2 * INCH, id="unit-mixed-case"),
    pytest.param("20 mm", L, IN, 20, id="space-before-unit"),
    pytest.param("  20mm  ", L, IN, 20, id="outer-spaces"),
    pytest.param("45deg", A, MM, math.radians(45), id="deg"),
    pytest.param("0.5rad", A, MM, 0.5, id="rad"),
    pytest.param("90 DEG", A, MM, math.pi / 2, id="deg-upper"),
    # Decimals, fractions and mixed numbers.
    pytest.param("20.5", L, MM, 20.5, id="decimal"),
    pytest.param(".5in", L, MM, 0.5 * INCH, id="leading-dot"),
    pytest.param("7/8 mm", L, IN, 7 / 8, id="fraction-mm"),
    pytest.param("2/3in", L, MM, 2 / 3 * INCH, id="fraction-in"),
    pytest.param("1 3/4in", L, MM, 1.75 * INCH, id="mixed-in"),
    pytest.param("1 3/4", L, IN, 1.75 * INCH, id="mixed-bare-in-part"),
    pytest.param("10/2in", L, MM, 5 * INCH, id="fraction-binds-before-unit"),
    # Feet and inches side by side.
    pytest.param("1' 3\"", L, MM, 15 * INCH, id="feet-inches-symbols"),
    pytest.param("1ft 3in", L, MM, 15 * INCH, id="feet-inches-words"),
    pytest.param("1' 3 1/2\"", L, MM, 15.5 * INCH, id="feet-mixed-inches"),
    pytest.param("2m 5cm", L, MM, 2050, id="metres-centimetres"),
    # Arithmetic.
    pytest.param("20mm + 1/4in", L, MM, 20 + 0.25 * INCH, id="mixed-units-add"),
    pytest.param("1/4in + 2", L, MM, 0.25 * INCH + 2, id="bare-added-to-length-mm"),
    pytest.param("1/4in + 2", L, IN, 2.25 * INCH, id="bare-added-to-length-in"),
    pytest.param("2in * 3", L, MM, 6 * INCH, id="length-times-number"),
    pytest.param("10mm / 4", L, IN, 2.5, id="length-divided"),
    pytest.param("(10 + 5) * 2", L, MM, 30, id="parentheses"),
    pytest.param("2 + 3 * 4", L, MM, 14, id="precedence"),
    pytest.param("-5mm", L, MM, -5, id="negative"),
    pytest.param("-(2mm + 3mm)", L, MM, -5, id="negative-group"),
    pytest.param("10mm - 2mm - 3mm", L, MM, 5, id="left-to-right-minus"),
    pytest.param("24mm / 2 / 3", L, MM, 4, id="left-to-right-divide"),
    pytest.param("10mm / 1/2", L, MM, 5, id="divisor-is-not-a-fraction"),
    pytest.param("30 + 0.5rad", A, MM, math.radians(30) + 0.5, id="bare-added-to-angle"),
    pytest.param("90deg - 30", A, MM, math.radians(60), id="angle-minus-bare"),
    # Formulas.
    pytest.param("=Width/2", L, MM, 31.75, id="var-half"),
    pytest.param("=(Width + 5mm)*2", L, MM, (63.5 + 5) * 2, id="var-group"),
    pytest.param("=Width/Count", L, MM, 63.5 / 4, id="var-by-number-var"),
    pytest.param("=Angle * 2", A, MM, math.radians(60), id="angle-var"),
    pytest.param("=sin(pi/2)", N, MM, 1.0, id="sin"),
    pytest.param("=cos(60deg)", N, MM, 0.5, id="cos-of-angle"),
    pytest.param("=tan(Angle)", N, MM, math.tan(math.radians(30)), id="tan-of-var"),
    pytest.param("=max(10mm, 1in)", L, MM, INCH, id="max"),
    pytest.param("=min(10mm, 1in, 2cm)", L, MM, 10, id="min-three"),
    pytest.param("=abs(-3mm)", L, MM, 3, id="abs"),
    pytest.param("=sqrt(16)", N, MM, 4, id="sqrt"),
    pytest.param("=round(2.6)", N, MM, 3, id="round"),
    pytest.param("=2*pi*1rad", A, MM, 2 * math.pi, id="pi-in-angle"),
    pytest.param("=2*3", L, MM, 6, id="formula-number-to-length-mm"),
    pytest.param("=2*3", L, IN, 6 * INCH, id="formula-number-to-length-in"),
    pytest.param("=90", A, MM, math.radians(90), id="formula-number-to-angle"),
    pytest.param("= Width", L, MM, 63.5, id="space-after-equals"),
]


@pytest.mark.parametrize(("text", "kind", "units", "expected"), VALID)
def test_valid(text: str, kind: Kind, units: UnitSystem, expected: float) -> None:
    result = evaluate(text, kind, units, VARS)
    assert result == pytest.approx(expected, rel=1e-12, abs=1e-12)


ERRORS = [
    pytest.param("", L, id="empty"),
    pytest.param("   ", L, id="blank"),
    pytest.param("=", L, id="bare-equals"),
    pytest.param("20 furlongs", L, id="unknown-unit"),
    pytest.param("=Height", L, id="unknown-variable"),
    pytest.param("=width", L, id="variable-case"),
    pytest.param("=foo(2)", L, id="unknown-function"),
    pytest.param("Width", L, id="variable-outside-formula"),
    pytest.param("pi", N, id="pi-outside-formula"),
    pytest.param("=Width + 5", L, id="bare-plus-length-in-formula"),
    pytest.param("10mm + 30deg", L, id="length-plus-angle"),
    pytest.param("30deg", L, id="angle-in-length-field"),
    pytest.param("10mm", A, id="length-in-angle-field"),
    pytest.param("10mm", N, id="length-in-number-field"),
    pytest.param("2in * 3in", L, id="area"),
    pytest.param("10mm / 0", L, id="divide-by-zero"),
    pytest.param("1/0", L, id="fraction-zero"),
    pytest.param("10mm +", L, id="trailing-operator"),
    pytest.param("(10mm", L, id="open-paren"),
    pytest.param("10mm)", L, id="close-paren"),
    pytest.param("1/", L, id="incomplete-fraction"),
    pytest.param("=,", L, id="lonely-comma"),
    pytest.param("2 3", L, id="missing-operator"),
    pytest.param("1ft 3", L, id="feet-then-bare"),
    pytest.param("=sqrt(16mm)", L, id="sqrt-of-length"),
    pytest.param("=sqrt(-4)", N, id="sqrt-negative"),
    pytest.param("=max(1mm, 2deg)", L, id="max-mixed"),
    pytest.param("=sin(1mm)", N, id="sin-of-length"),
    pytest.param("=abs(1, 2)", N, id="abs-two-args"),
    pytest.param("20 # 3", L, id="bad-character"),
    pytest.param("10\u221210", L, id="unicode-minus"),
]


@pytest.mark.parametrize(("text", "kind"), ERRORS)
def test_errors(text: str, kind: Kind) -> None:
    with pytest.raises(ExpressionError):
        evaluate(text, kind, MM, VARS)


def test_error_messages_say_what_to_do() -> None:
    with pytest.raises(ExpressionError, match=r"Unknown unit 'furlongs'\. Use mm"):
        evaluate("20 furlongs", L, MM)
    with pytest.raises(ExpressionError, match="Start the value with ="):
        evaluate("Width", L, MM, VARS)
