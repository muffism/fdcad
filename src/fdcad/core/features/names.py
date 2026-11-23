"""Default names for new features: "Extrude 1", "Cut 1" and so on.

Names are a plain generic word, a space and a number (D11, owner approved in D110).
"""

from __future__ import annotations

import re

from fdcad.core.document.model import Document

_PREFIX = {
    ("extrude", "boss"): "Extrude",
    ("extrude", "cut"): "Cut",
    ("revolve", "boss"): "Revolve",
    ("revolve", "cut"): "Revolve Cut",
    ("sweep", "boss"): "Sweep",
    ("sweep", "cut"): "Sweep Cut",
    ("loft", "boss"): "Loft",
    ("loft", "cut"): "Loft Cut",
    ("split_for_print", "boss"): "Print Split",
    ("curve_array", "boss"): "Curve Array",
    ("sketch3d", "boss"): "3D Sketch",  # TR7 (D1719)
}


def name_prefix(ftype: str, operation: str = "boss") -> str:
    """The name without its number, such as "Cut"."""
    return _PREFIX.get((ftype, operation), ftype.replace("_", " ").title())


def default_name(doc: Document, ftype: str, operation: str = "boss") -> str:
    """The next free name: one more than the highest number already used."""
    prefix = name_prefix(ftype, operation)
    pattern = re.compile(rf"^{re.escape(prefix)} (\d+)$")
    used = [int(m.group(1)) for f in doc.features if (m := pattern.match(f.name))]
    return f"{prefix} {max(used, default=0) + 1}"
