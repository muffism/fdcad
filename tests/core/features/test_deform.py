"""Deformation features: bend, twist, taper, stretch, flow along curve (PLAN Phase 4,
PHASE4_SPEC P4.9, PLAN 10 item 8, D393)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fdcad.core.deform import maps
from fdcad.core.deform.feature import default_params
from fdcad.core.deform.nurbs import basis_matrix, greville
from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features import REGISTRY
from fdcad.core.features.base import BuildContext, FeatureState
from fdcad.core.features.direct import valid_solid
from fdcad.core.features.preview import build_preview
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from tests.core.features.phase3_parts import add_extrude, add_sketch, rect

FRAME = maps.Frame.from_axes((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))


def _pts(*rows: tuple[float, float, float]) -> np.ndarray:
    return np.array(rows, dtype=float)


# Maps -------------------------------------------------------------------------------


def test_twist_map_turns_linearly_and_rigidly_beyond() -> None:
    f = maps.twist(FRAME, 0.0, 10.0, math.pi / 2)
    out = f(_pts((1, 0, -5), (1, 0, 5), (1, 0, 10), (1, 0, 20)))
    assert out[0] == pytest.approx([1, 0, -5])
    assert out[1] == pytest.approx([math.cos(math.pi / 4), math.sin(math.pi / 4), 5])
    assert out[2] == pytest.approx([0, 1, 10], abs=1e-12)
    assert out[3] == pytest.approx([0, 1, 20], abs=1e-12)


def test_taper_stretch_maps() -> None:
    t = maps.taper(FRAME, 0.0, 10.0, 0.5)(_pts((2, 2, 10), (2, 2, 5)))
    assert t[0] == pytest.approx([1, 1, 10]) and t[1] == pytest.approx([1.5, 1.5, 5])
    s = maps.stretch(FRAME, 0.0, 10.0, 5.0)(_pts((0, 0, 4), (0, 0, 12)))
    assert s[0] == pytest.approx([0, 0, 6]) and s[1] == pytest.approx([0, 0, 17])


def test_bend_keeps_the_neutral_length_and_links_angle_and_radius() -> None:
    length, angle = 50.0, math.pi / 2
    f = maps.bend(FRAME, 0.0, length, angle)
    radius = maps.bend_radius(length, angle)
    end = f(_pts((0, 0, length)))[0]
    assert end == pytest.approx([0, radius, radius], abs=1e-9)
    beyond = f(_pts((0, 0, length + 10)))[0]  # goes on straight along the turned axis
    assert beyond == pytest.approx([0, radius + 10, radius], abs=1e-9)
    assert maps.bend(FRAME, 0, 10, 0.0)(_pts((1, 2, 3)))[0] == pytest.approx([1, 2, 3])


def test_flow_lays_the_axis_on_the_curve() -> None:
    s = np.linspace(0.0, 10.0, 11)
    points = np.stack([s, np.zeros_like(s), np.zeros_like(s)], axis=1)  # along X
    tangents = np.tile([1.0, 0.0, 0.0], (11, 1))
    curve = maps.rotation_minimizing(s, points, tangents, (0.0, 1.0, 0.0))
    f = maps.flow(FRAME, 0.0, 10.0, curve, 1.0)
    out = f(_pts((0, 0, 3), (1, 0, 3), (0, 0, 12)))
    assert out[0] == pytest.approx([3, 0, 0])
    assert out[2] == pytest.approx([12, 0, 0])  # straight on past the end
    assert np.linalg.norm(out[1] - out[0]) == pytest.approx(1.0)


def test_greville_fit_basis_is_a_partition_of_unity() -> None:
    knots = np.array([0, 0, 0, 0, 1, 2, 3, 3, 3, 3], dtype=float)
    g = greville(knots, 3)
    b = basis_matrix(knots, 3, g)
    assert b.shape == (6, 6)
    assert b.sum(axis=1) == pytest.approx(np.ones(6))
    assert g[0] == 0 and g[-1] == 3


# Features ---------------------------------------------------------------------------


def _bar(length: float = 100.0) -> tuple[Document, str]:
    """A 10 x 10 bar along Z from 0 to ``length``, centred on the Z axis."""
    doc = new_document()
    s = Sketch()
    rect(s, -5, -5, 5, 5)
    bar = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), length)
    return doc, bar


def _add(doc: Document, ftype: str, **params: object) -> Feature:
    feature = Feature(doc.new_feature_id(), ftype, ftype.title() + " 1", params=dict(params))
    doc.features.append(feature)
    return feature


def _build(doc: Document) -> tuple[RebuildEngine, object]:
    engine = RebuildEngine()
    return engine, engine.rebuild(doc)


@pytest.mark.parametrize(
    ("ftype", "params", "volume"),
    [
        ("twist", {"angle": Param("90", math.pi / 2)}, 10000.0),
        ("taper", {"factor": Param("0.5", 0.5)}, 10000.0 * (1 - 0.5 + 0.25 / 3)),
        ("stretch", {"distance": Param("20", 20.0)}, 12000.0),
        ("bend", {"angle": Param("90", math.pi / 2)}, 10000.0),
        ("bend", {"bend_by": "radius", "radius": Param("100", 100.0)}, 10000.0),
    ],
)
def test_each_type_gives_a_valid_solid(
    ftype: str, params: dict[str, object], volume: float
) -> None:
    doc, bar = _bar()
    feature = _add(doc, ftype, **params)
    report = RebuildEngine().rebuild(doc)
    result = report.results[feature.id]
    assert result.state is FeatureState.OK, [i.message for i in result.issues]
    body = result.body
    assert body is not None and valid_solid(body.shape)
    assert volume_of(body.shape) == pytest.approx(volume, rel=2e-3)
    # Faces keep their names (D393): the bar's cap and sides are still there.
    names = {n for n, _f in body.faces}
    assert f"{bar}/cap/end" in names and f"{bar}/cap/start" in names
    assert "Largest deviation" in result.extras["report"][0]


def test_trim_planes_limit_the_region() -> None:
    doc, _bar_id = _bar()
    feature = _add(
        doc,
        "twist",
        angle=Param("90", math.pi / 2),
        ox=Param("0", 0.0), oy=Param("0", 0.0), oz=Param("0", 0.0),
        start=Param("40", 40.0), end=Param("60", 60.0),
    )  # fmt: skip
    body = RebuildEngine().rebuild(doc).results[feature.id].body
    assert body is not None and valid_solid(body.shape)
    assert volume_of(body.shape) == pytest.approx(10000.0, rel=2e-3)


def test_tight_tolerance_gives_the_approximate_warning() -> None:
    doc, _bar_id = _bar()
    feature = _add(
        doc, "bend", angle=Param("90", math.pi / 2), tolerance=Param("0.000000001", 1e-9)
    )
    result = RebuildEngine().rebuild(doc).results[feature.id]
    assert result.state is FeatureState.WARNING
    assert any(i.code == "approximate" and "approximate" in i.message for i in result.issues)


def test_invalid_result_is_an_error_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    import fdcad.core.deform.feature as base

    doc, _bar_id = _bar()
    feature = _add(doc, "twist", angle=Param("90", math.pi / 2))
    monkeypatch.setattr(base, "valid_solid", lambda _shape: False)
    result = RebuildEngine().rebuild(doc).results[feature.id]
    assert result.state is FeatureState.ERROR
    assert "not a valid solid" in result.issues[0].message


def test_bad_values_are_errors() -> None:
    for params in (
        {"factor": Param("0", 0.0)},
        {"factor": Param("1", 1.0), "start": Param("5", 5.0), "end": Param("5", 5.0)},
    ):
        doc, _bar_id = _bar()
        feature = _add(doc, "taper", **params)
        result = RebuildEngine().rebuild(doc).results[feature.id]
        assert result.state is FeatureState.ERROR


@pytest.mark.parametrize(
    ("radius", "folds"), [(4.0, True), (5.0, True), (-4.0, True), (5.5, False), (-6.0, False)]
)
def test_a_bend_tighter_than_the_body_is_an_error(radius: float, folds: bool) -> None:
    """A 10 mm bar bent to a 4 mm radius folded through itself but only got a warning."""
    doc, _bar_id = _bar()
    feature = _add(
        doc,
        "bend",
        bend_by="radius",
        radius=Param(f"{radius:g}", radius),
        start=Param("-10", -10.0),
        end=Param("10", 10.0),
    )
    result = RebuildEngine().rebuild(doc).results[feature.id]
    messages = [i.message for i in result.issues]
    assert (result.state is FeatureState.ERROR) is folds, messages
    if folds:
        assert "fold through themselves" in messages[0]


def test_flow_along_a_sketch_arc() -> None:
    doc, _bar_id = _bar()
    path = Sketch()
    path.add_arc(-80.0, 0.0, 80.0, 0.0, math.pi / 2)
    sid = add_sketch(doc, path, {"feature": "f3"})
    feature = _add(doc, "flow")
    feature.refs["path"] = {"feature": sid}
    result = RebuildEngine().rebuild(doc).results[feature.id]
    assert result.state is not FeatureState.ERROR, [i.message for i in result.issues]
    assert result.body is not None and valid_solid(result.body.shape)
    assert volume_of(result.body.shape) == pytest.approx(10000.0, rel=5e-3)
    feature.params["fit"] = True  # 100 mm of bar spread over the 125.7 mm arc
    result = RebuildEngine().rebuild(doc).results[feature.id]
    assert result.body is not None
    assert volume_of(result.body.shape) == pytest.approx(10000.0 * 40 * math.pi / 100, rel=5e-3)


@pytest.mark.parametrize(("radius", "folds"), [(2.0, True), (4.0, True), (6.0, False)])
def test_flow_round_a_bend_tighter_than_the_body_is_an_error(radius: float, folds: bool) -> None:
    """A 10 mm bar flowed round a 2 mm arc folded through itself, yet the result was OK."""
    doc, _bar_id = _bar()
    path = Sketch()
    path.add_arc(-radius, 0.0, radius, 0.0, math.pi / 2)
    sid = add_sketch(doc, path, {"feature": "f3"})
    feature = _add(doc, "flow", fit=True)
    feature.refs["path"] = {"feature": sid}
    result = RebuildEngine().rebuild(doc).results[feature.id]
    messages = [i.message for i in result.issues]
    assert (result.state is FeatureState.ERROR) is folds, messages
    if folds:
        assert "fold through themselves" in messages[0]


def test_only_picked_bodies_deform() -> None:
    from tests.core.features.phase3_parts import face_ref

    doc, bar = _bar()
    s = Sketch()
    rect(s, 20, -5, 30, 5)
    other = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0, merge=False)
    engine = RebuildEngine()
    body = engine.rebuild(doc).body
    assert body is not None and len(solids(body.shape)) == 2
    feature = _add(doc, "stretch", distance=Param("50", 50.0))
    feature.refs["bodies"] = [face_ref(body, f"{bar}/cap/end")]
    result = engine.rebuild(doc).results[feature.id]
    assert result.body is not None
    volumes = sorted(volume_of(s) for s in solids(result.body.shape))
    assert volumes == pytest.approx([1000.0, 15000.0], rel=1e-6)
    assert other


def test_default_params_and_preview_handles() -> None:
    doc, _bar_id = _bar()
    engine = RebuildEngine()
    body = engine.rebuild(doc).body
    assert body is not None
    params = default_params(body.shape, "z", UnitSystem.MM)
    assert params["start"].value == pytest.approx(-50.0)
    assert params["end"].value == pytest.approx(50.0)
    assert params["oz"].value == pytest.approx(50.0)
    feature = _add(doc, "twist", angle=Param("45", math.pi / 4), **params)
    report = engine.rebuild(doc)
    preview = build_preview(doc, feature, report.results)
    assert preview.error is None and preview.shape is not None
    assert {h.param for h in preview.handles} == {"ox", "oy", "oz", "start", "end"}
    ctx = BuildContext(doc, body, dict(report.results))
    handles = REGISTRY["twist"].preview_handles(feature, ctx)
    end = next(h for h in handles if h.param == "end")
    assert end.tip == pytest.approx((0.0, 0.0, 100.0), abs=1e-6)


def test_the_input_body_is_never_changed() -> None:
    """Regression: the conversion shared vertices with the input, which then moved."""
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.deform.nurbs import deform_shape

    doc, _bar_id = _bar()
    body = RebuildEngine().rebuild(doc).body
    assert body is not None

    def corners() -> list[tuple[float, float, float]]:
        out = []
        explorer = TopExp_Explorer(body.shape, TopAbs_VERTEX)
        while explorer.More():
            p = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
            out.append((round(p.X(), 9), round(p.Y(), 9), round(p.Z(), 9)))
            explorer.Next()
        return sorted(out)

    before = corners()
    fmap = maps.stretch(FRAME, 0.0, 100.0, 50.0)
    first = deform_shape(body.shape, fmap, 0.01, 100.0)
    second = deform_shape(body.shape, fmap, 0.01, 100.0)
    assert corners() == before
    assert volume_of(body.shape) == pytest.approx(10000.0)
    assert volume_of(first.shape) == pytest.approx(volume_of(second.shape)) == pytest.approx(15000)
