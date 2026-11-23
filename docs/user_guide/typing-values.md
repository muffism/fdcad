# Typing values

## Units

Lengths use mm, cm, m, in, ft. Use `"` for inches and `'` for feet.
Angles use deg and rad.
Unit names ignore case. The space before a unit is optional.
A number without a unit uses the part's units. In an angle field it means degrees.
In an inch part, a new Move Face, pattern or other body tool starts with small round inch values such as 0.04 in, and a tap drill or other table value keeps its exact length.
A number too large for the part's unit, such as `1e308`, is refused when you type it.

## Fractions and mixed numbers

Type `7/8 mm` or `2/3in`. Mixed numbers work too: `1 3/4in`.
Feet and inches together: `1' 3"`, `1ft 3in`, `1' 3 1/2"`.

## Exponent notation

A number may end in `e` or `E`, an optional sign and digits: `2e3` is 2000, `1.5e-3` is 0.0015.
Numbers pasted from a spreadsheet or a calculator, such as `2E+06`, work as they are.
A unit can follow: `2e3 mm`. In a formula too: `=2e3*Count`.
The exponent needs its digits, so `2e` and `2e+` are errors.
In a formula, a name such as `e` or `e3` on its own is still a variable.

## How values are shown

Preferences has three choices for shown values. They change only how numbers look:
fields, formulas and the model keep every digit.

- **Round shown numbers**: Half away from zero (the default), Half to even, or Cut off.
- **Decimal separator**: Follow the system, Point or Comma. Value fields still read a point,
  so type `1.5`, not `1,5`.
- **Inch values as fractions**: Off, or a step from 1/2 to 1/64. In an inch part a value
  that lands on a step shows as a fraction, such as `1 3/4`. A value that does not land
  on a step keeps its decimals, so a fraction never hides a difference.

## Arithmetic

Use `+ - * /` and parentheses. Each value may have its own unit: `20mm + 1/4in`.
A bare number added to a length uses the part units: `1/4in + 2`.
A number right after a division sign is a divisor. So `24mm / 2 / 3` is 4 mm.

## Formulas

Start a value with `=` to use variables. For example `=Width/2` or `=(Width + 5mm)*2`.
Variable names are case sensitive.
Functions: sin, cos, tan, asin, acos, atan, atan2, sqrt, abs, min, max, round, floor, ceil, trunc, sign, mod, pow, exp, ln, log10, sinh, cosh, tanh, random, and the constant pi. Conditions: `if(test, then, else)`, `and`, `or`, `not` and the comparisons `<`, `<=`, `>`, `>=`, `==` and `!=`. For example `=if(Width > 50mm, 3mm, 2mm)`.

- `trunc(x)` drops the fraction toward zero. `sign(x)` is -1, 0 or 1.
- `mod(a, b)` is the remainder of a divided by b, with the sign of b: `=mod(25mm, 10mm)` is 5 mm and `=mod(-7, 3)` is 2. Both values need the same kind of unit.
- `pow(a, b)` is a to the power b. There is no `^` sign; use `pow`. A length can only take a whole power: `=pow(3mm, 2)` is an area, so divide it back by a length before using it as a length.
- `exp`, `ln` (natural log), `log10`, `sinh`, `cosh` and `tanh` take plain numbers.
- `random(seed)` gives a number from 0 to 1, and `random(seed, low, high)` one from low to high. The same seed always gives the same number, so the part rebuilds the same each time. Change the seed for another value.
- A minus sign in front applies to what follows it: `-pow(3, 2)` is -9.
- `==` on two computed lengths can fail because of tiny rounding. Test with a tolerance instead: `=if(abs(A - B) < 0.001mm, 1, 0)`.
- A function name only works as a function when `(` follows it, so an older variable called `mod` or `exp` still works.
round, floor and ceil work on the value in millimetres (or radians for an angle), so `=round(1.4in)` is 36 mm. To round in inches, divide by the unit first: `=round(1.4in / 1in) * 1in` is 1 inch.
Write angles with `deg`, not the degree sign.
Trigonometry uses radians, or an angle with its unit: `=cos(60deg)`.

## Strict rules

Adding a plain number to a length is an error. `=Width + 5` must be `=Width + 5mm`.
A formula that gives a plain number uses the part units, or degrees in an angle field.

## Typing in the view

You do not have to go to the panel to type a value. While a feature's property panel is open, each length, angle or count of the feature shows as a value label in the 3D view. Features with a drag handle (Extrude, Revolve, Move Face, Move Body, Scale, the deformations and Edge Flange) show the value beside the handle. The others show their values at the first item you picked: the middle of the first edge for Fillet and Chamfer, the first face for Shell and Offset Face, and the neutral face for Draft. Features placed by sketch points or a picked spot (Hole Tool, Mounting Boss, Rib, Dome and the like) show their labels at the middle of the preview. When labels would cover each other, the later ones move down.

1. Click a label to open the value box on it. The value box is the same one Smart Dimension uses: units, formulas, the wheel and the Up and Down keys all work.
2. With the view focused, type a digit, a minus sign, a dot or `=`. The value box opens on the first label, or on the one you used last, with that character already typed.
3. Enter applies the value and closes the box. The panel field and the preview update at once.
4. Tab and Shift+Tab apply the value and move the box to the next or previous label of the feature.
5. Esc closes the box and puts back every value it changed.
6. OK on the panel adds or changes the feature as one undo step, the same as typing in the panel.

In a sketch you can type sizes while you draw and the values of sketch tools. See [Sketching](sketching.md#typing-sizes-while-you-draw).

## Errors

The field shows a message that says what is wrong.
For example: "Unknown unit 'furlongs'. Use mm, cm, m, in, ft, deg or rad."
Fix the text and press Enter again.

| You type | Means |
| --- | --- |
| 20mm | 20 millimetres |
| 1' 3" | 1 foot 3 inches |
| 1 3/4in | one and three quarter inches |
| 20mm + 1/4in | 20 mm plus a quarter inch |
| 1/4in + 2 | a quarter inch plus 2 part units |
| 24mm / 2 / 3 | 4 mm |
| 2e3 mm | 2000 millimetres |
| 1.5e-3 | 0.0015 part units |
| =Width/2 | half of the Width variable |
| =cos(60deg) | cosine of 60 degrees |