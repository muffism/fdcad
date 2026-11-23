"""STEP export options (TR302 item 1, DECISIONS D1202).

The unit of the file, Y up instead of Z up, body names, one file per body, and
whether hidden bodies go in. The choice is kept in the part's print setup under
``step_export``. Writing goes through ``export.export_step``; this module holds
the options and the per body file names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from OCP.TopoDS import TopoDS_Shape

#: The file units and the STEP writer's names for them.
UNITS = {"mm": "MM", "in": "INCH", "m": "M"}


@dataclass(frozen=True)
class StepOptions:
    """How STEP export writes the part."""

    unit: str = "mm"
    #: Turn the model so its Z up is the file's Y up, for programs that use Y up.
    y_up: bool = False
    #: Write each body as a named product (its own name or Body N).
    names: bool = True
    #: One file per body, named after the file and the body.
    per_body: bool = False
    #: Hidden bodies go in too.
    hidden: bool = False

    def to_data(self) -> dict[str, Any]:
        """The options as saved in the part's print setup."""
        return {
            "unit": self.unit,
            "y_up": self.y_up,
            "names": self.names,
            "per_body": self.per_body,
            "hidden": self.hidden,
        }

    @classmethod
    def from_data(cls, raw: Any) -> StepOptions:
        """Options saved with :meth:`to_data`; anything missing or wrong is the default."""
        base = cls()
        if not isinstance(raw, dict):
            return base
        unit = raw.get("unit", base.unit)

        def flag(key: str, default: bool) -> bool:
            value = raw.get(key, default)
            return value if isinstance(value, bool) else default

        return cls(
            unit if unit in UNITS else base.unit,
            flag("y_up", base.y_up),
            flag("names", base.names),
            flag("per_body", base.per_body),
            flag("hidden", base.hidden),
        )


def y_up_trsf() -> Any:
    """The turn that takes the model's Z up to Y up: a quarter turn about X."""
    import math

    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf

    trsf = gp_Trsf()
    trsf.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), -math.pi / 2)
    return trsf


def turned(shape: TopoDS_Shape) -> TopoDS_Shape:
    """``shape`` turned Y up, as a moved copy that shares its geometry."""
    from OCP.TopLoc import TopLoc_Location

    return shape.Moved(TopLoc_Location(y_up_trsf()))


def safe_part(text: str) -> str:
    """``text`` as part of a file name: letters, digits, spaces, dots, dashes and
    underscores; others become underscores."""
    clean = re.sub(r"[^\w .-]", "_", text).strip(" .")
    return clean[:80] or "body"


def body_paths(target: Path, labels: list[str]) -> list[Path]:
    """One file per body: ``<stem>_<label><suffix>``, a number added where two match."""
    out: list[Path] = []
    seen: set[str] = set()
    for label in labels:
        base = f"{target.stem}_{safe_part(label)}"
        name, k = base, 2
        while name.lower() in seen:
            name, k = f"{base}_{k}", k + 1
        seen.add(name.lower())
        out.append(target.with_name(name + target.suffix))
    return out
