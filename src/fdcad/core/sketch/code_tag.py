"""Code tags in sketches (TR311, DECISIONS D1215).

A text becomes a QR code (``core.printing.qr_code``) drawn as sketch lines: the
dark modules joined into one region, its outlines closed loops of lines with
shared end points, ready to extrude as a raised or cut tag. ``module`` is the
side of one module in mm; ``at`` is the bottom left corner. No Qt.
"""

from __future__ import annotations

from fdcad.core.printing.qr_code import modules, outline
from fdcad.core.sketch.model import Line, Sketch

#: The smallest module side, in mm: a 0.4 mm nozzle prints about one line.
MIN_MODULE = 0.4


def add_code_tag(
    sketch: Sketch, text: str, module: float, at: tuple[float, float] = (0.0, 0.0)
) -> list[str]:
    """Add the code of ``text`` and return the new line ids. Raises ValueError for
    empty or too long text and for a module below :data:`MIN_MODULE`."""
    if not text:
        raise ValueError("the text is empty")
    if module < MIN_MODULE:
        raise ValueError(f"the module is smaller than {MIN_MODULE} mm")
    grid = modules(text)
    made: list[str] = []
    for loop in outline(grid):
        ids = [sketch.add_point(at[0] + x * module, at[1] + y * module) for x, y in loop]
        for i, a in enumerate(ids):
            b = ids[(i + 1) % len(ids)]
            lid = sketch.new_id()
            sketch.entities[lid] = Line(lid, a, b)
            made.append(lid)
    return made


def size_of(text: str, module: float) -> float:
    """The tag's side in mm."""
    return len(modules(text)) * module
