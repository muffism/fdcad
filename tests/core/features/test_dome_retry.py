"""The dome asks the kernel again when it returns nothing (D1053).

Found on a bike frame (2026-11-12): the dome on the end of a swept chain stay built in
the session and failed when the same part was opened from its file ("the dome cannot
rise from every edge of this face"). The kernel's intersection of the pushed up end
face and the dome's sphere reported success and returned an empty shape at one
tolerance, the right shape at ten times it.
"""

from typing import Any, ClassVar

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features import dome
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, plate, volume
from tests.core.features.test_hole import face_ref


class _Flaky:
    """The kernel's intersection, returning nothing at the tolerances in ``empty``."""

    empty: ClassVar[tuple[float, ...]] = ()
    asked: ClassVar[list[float]] = []

    def __init__(self) -> None:
        self._op = _REAL()
        self._fuzzy = 0.0

    def SetFuzzyValue(self, value: float) -> None:  # noqa: N802
        self._fuzzy = value
        self._op.SetFuzzyValue(value)

    def Shape(self) -> Any:  # noqa: N802
        type(self).asked.append(self._fuzzy)
        if self._fuzzy in type(self).empty:
            from OCP.TopoDS import TopoDS_Compound

            return TopoDS_Compound()
        return self._op.Shape()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._op, name)


_REAL = dome.BRepAlgoAPI_Common


def _domed_plate() -> tuple[Any, str]:
    doc, ext = plate()
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "dome",
            "Dome 1",
            params={"distance": Param("5", 5.0), "continuous": True},
            refs={"faces": [face_ref(doc, ext, "cap/end")]},
        )
    )
    return doc, fid


def test_an_empty_answer_is_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    doc, fid = _domed_plate()
    right = volume(body(rebuild(doc), fid).shape)
    assert right > 25000 + 1000
    _Flaky.empty = (dome.FUZZY_TOLERANCE,)
    _Flaky.asked = []
    monkeypatch.setattr(dome, "BRepAlgoAPI_Common", _Flaky)
    doc, fid = _domed_plate()
    doc.feature(fid).params["distance"] = Param("5.0", 5.0)  # another key: not from the cache
    again = rebuild(doc)[fid]
    assert again.state is FeatureState.OK, [i.message for i in again.issues]
    assert again.body is not None and volume(again.body.shape) == pytest.approx(right, rel=1e-6)
    assert _Flaky.asked[:2] == [dome.FUZZY_TOLERANCE, 10 * dome.FUZZY_TOLERANCE]


def test_shapes_that_do_not_overlap_still_give_the_empty_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Flaky.empty = dome._COMMON_TOLERANCES
    _Flaky.asked = []
    monkeypatch.setattr(dome, "BRepAlgoAPI_Common", _Flaky)
    doc, fid = _domed_plate()
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "Tick Continuous dome" in result.issues[0].message
    assert len(_Flaky.asked) == len(dome._COMMON_TOLERANCES)
