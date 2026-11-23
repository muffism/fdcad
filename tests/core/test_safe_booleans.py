"""The kernel's booleans run in the mode that leaves their inputs alone (D1067).

Found on a gearbox of 318 features (2026-11-12). The kernel's booleans may write into
the shapes they are given. A body shares its faces with the results of the features
before it, which the rebuild keeps, so a cut in the cover left three faces of the
housing, as kept for the features before, not valid. ``fdcad.core.occ`` holds the
kernel's boolean classes with its safe mode switched on; all code uses those.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

import fdcad
from fdcad.core import occ
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.occ import ShapeList

SOURCE = Path(fdcad.__file__).parent
#: Has no safe mode in this kernel build; used by Delete and Patch only.
ALLOWED = {"BRepAlgoAPI_Defeaturing"}


def test_no_module_takes_a_boolean_straight_from_the_kernel() -> None:
    wrong = []
    for path in SOURCE.rglob("*.py"):
        if path.name == "occ.py" and path.parent.name == "core":
            continue
        text = path.read_text(encoding="utf-8")
        for found in re.finditer(r"from OCP\.BRepAlgoAPI import ([^\n(]+|\([^)]*\))", text):
            names = set(re.findall(r"BRepAlgoAPI_\w+", found.group(1)))
            if names - ALLOWED:
                wrong.append(f"{path.relative_to(SOURCE)}: {sorted(names - ALLOWED)}")
        if "SetNonDestructive(False)" in text:
            wrong.append(f"{path.relative_to(SOURCE)}: switches the safe mode off")
    assert wrong == [], "import these from fdcad.core.occ: " + "; ".join(wrong)


def _boxes():  # type: ignore[no-untyped-def]
    return (
        BRepPrimAPI_MakeBox(10, 10, 10).Shape(),
        BRepPrimAPI_MakeBox(gp_Pnt(5, 5, 5), 10, 10, 10).Shape(),
    )


@pytest.mark.parametrize(
    ("name", "volume"),
    [("BRepAlgoAPI_Cut", 875.0), ("BRepAlgoAPI_Fuse", 1875.0), ("BRepAlgoAPI_Common", 125.0)],
)
def test_the_two_shape_form_builds_at_once_in_the_safe_mode(name: str, volume: float) -> None:
    a, b = _boxes()
    op = getattr(occ, name)(a, b)
    assert op.NonDestructive() and op.IsDone()
    assert volume_of(op.Shape()) == pytest.approx(volume)
    assert BRepCheck_Analyzer(a).IsValid() and BRepCheck_Analyzer(b).IsValid()


@pytest.mark.parametrize(
    "name", ["BRepAlgoAPI_Cut", "BRepAlgoAPI_Fuse", "BRepAlgoAPI_Common", "BRepAlgoAPI_Splitter"]
)
def test_the_empty_form_is_in_the_safe_mode_and_built_by_the_caller(name: str) -> None:
    a, b = _boxes()
    op = getattr(occ, name)()
    assert op.NonDestructive()
    first, second = ShapeList(), ShapeList()
    first.Append(a)
    second.Append(b)
    op.SetArguments(first)
    op.SetTools(second)
    op.Build()
    assert op.IsDone() and solids(op.Shape())
    assert isinstance(op, occ.BRepAlgoAPI_BooleanOperation) or name.endswith("Splitter")


def test_the_section_forms() -> None:
    a, b = _boxes()
    plane = gp_Pln(gp_Pnt(0, 0, 4), gp_Dir(0, 0, 1))
    now = occ.BRepAlgoAPI_Section(a, plane)
    assert now.NonDestructive() and now.IsDone() and not now.Shape().IsNull()
    later = occ.BRepAlgoAPI_Section(a, b, False)
    assert later.NonDestructive()
    later.Build()
    assert later.IsDone() and not later.Shape().IsNull()
    empty = occ.BRepAlgoAPI_Section()
    assert empty.NonDestructive()
    with pytest.raises(TypeError):
        occ.BRepAlgoAPI_Section(a)
    with pytest.raises(TypeError):
        occ.BRepAlgoAPI_Cut(a)


def test_shapes_that_share_a_face_are_built_in_the_kernels_own_mode() -> None:
    """D1076: found on a sheet metal tray with two gussets. Fold cuts the part after a
    slot by the part before it; the two share nearly every face, and in the safe mode
    the kernel gave back the whole part where nothing should be left. Its own mode is
    right there, so the mode is chosen at every build."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2

    box, _other = _boxes()
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(5, 5, -1), gp_Dir(0, 0, 1)), 2.0, 12.0).Shape()
    first = occ.BRepAlgoAPI_Cut(box, hole)
    assert first.NonDestructive()  # a fresh tool: nothing shared
    drilled = first.Shape()
    one, other = ShapeList(), ShapeList()
    one.Append(box)
    other.Append(drilled)
    assert occ.share_a_face(one, other) and not occ.share_a_face(one, ShapeList())
    added = occ.BRepAlgoAPI_Cut(drilled, box)
    assert not added.NonDestructive()
    assert volume_of(added.Shape()) == pytest.approx(0.0, abs=1e-9)
    gone = occ.BRepAlgoAPI_Cut(box, drilled)
    assert not gone.NonDestructive()
    assert volume_of(gone.Shape()) == pytest.approx(3.141592653589793 * 4 * 10, rel=1e-6)
    # The same object asked to build again with a fresh tool goes back to the safe mode.
    again = occ.BRepAlgoAPI_Cut()
    fresh = ShapeList()
    fresh.Append(hole)
    again.SetArguments(one)
    again.SetTools(other)
    again.Build()
    assert not again.NonDestructive()
    again.SetTools(fresh)
    again.Build()
    assert again.NonDestructive() and again.IsDone()
