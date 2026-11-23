"""Naming stress tests (PLAN Phase 6 item 1, PLAN 10 item 3, DECISIONS D431).

Random upstream edits, made with a fixed seed, on every sample part: dimension and
variable changes, sketch dimension changes, a new construction point in a sketch,
suppress and unsuppress, and moves one step up or down where the tree allows them.
After each edit every downstream reference must either resolve to the face or edge
that continues the one it named before, or fail with a clear error. It must never
resolve, silently, to a different face.

How a wrong face is found: while a part rebuilds, every face and edge looked up by
name is recorded with the feature that asked for it. After an edit, the face a
name gives is compared with the face it gave before the edit. Edits change values
by at most 10 percent, so the true continuation is the closest face of the same
kind; a name whose face is clearly farther than another face is reported.

The quick run (a few edits per small sample) runs by default. The full run is
marked ``slow``: run it with ``--run-slow`` or ``FDCAD_RUN_SLOW=1``.
"""

from __future__ import annotations

import math
import random
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Shape

import fdcad.core.rebuild.engine as engine_module
from fdcad.core.document.dependencies import move_problem
from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.naming.resolve import face_snapshot
from fdcad.core.occ import ShapeMap
from fdcad.core.rebuild.engine import RebuildEngine, RebuildReport
from fdcad.samples.graphs import SAMPLE_DIR as GRAPH_SAMPLE_DIR
from fdcad.samples.make import SAMPLE_DIR, measure

SEED = 20261030
SAMPLES = sorted([*SAMPLE_DIR.glob("*.fdprt"), *GRAPH_SAMPLE_DIR.glob("*.fdprt")])
#: Samples too slow for the quick run (each rebuild takes a second or more).
#: ``gearbox`` is 318 features: one rebuild takes a minute and a half (D1069).
HEAVY = {"generated_200", "lattice_block", "gearbox"}
QUICK_EDITS = 3
FULL_EDITS = 40
#: Full run edits of the gearbox (D1100): each edit rebuilds its 319 features three
#: times, so 40 edits took over three hours and kept the whole slow suite from finishing.
GEARBOX_FULL_EDITS = 4
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
#: Integer valued parameters change by one instead of by a factor.
_WHOLE = re.compile(r"^(count\d?|turns|starts|instances|fin_count|control_points)$")


# Recording what names resolve to ------------------------------------------


@dataclass
class Lookup:
    """One name lookup: the body searched and the face or edge found."""

    body: NamedShape
    shape: TopoDS_Shape


Key = tuple[str, str, str]  # (feature id, "face" or "edge", name)


class _Recorder:
    def __init__(self) -> None:
        self.current: str | None = None
        self.log: dict[Key, Lookup] = {}


_REC = _Recorder()


@contextmanager
def recording() -> Iterator[None]:
    """Record every face and edge looked up by name, with the feature building."""
    face0, edge0, build0 = NamedShape.face, NamedShape.edge, engine_module._build

    def face(self: NamedShape, name: str) -> Any:
        found = face0(self, name)
        if found is not None and _REC.current is not None:
            _REC.log.setdefault((_REC.current, "face", name), Lookup(self, found))
        return found

    def edge(self: NamedShape, name: str) -> Any:
        found = edge0(self, name)
        if found is not None and _REC.current is not None:
            _REC.log.setdefault((_REC.current, "edge", name), Lookup(self, found))
        return found

    def build(feature: Any, ftype: Any, ctx: Any) -> Any:
        outer, _REC.current = _REC.current, feature.id
        try:
            return build0(feature, ftype, ctx)
        finally:
            _REC.current = outer

    NamedShape.face, NamedShape.edge = face, edge  # type: ignore[method-assign]
    engine_module._build = build
    try:
        yield
    finally:
        NamedShape.face, NamedShape.edge = face0, edge0  # type: ignore[method-assign]
        engine_module._build = build0


def rebuild(
    doc: Document, engine: RebuildEngine | None = None
) -> tuple[RebuildReport, dict[Key, Lookup]]:
    """Rebuild ``doc`` and return the report and every name lookup."""
    _REC.log = {}
    with recording():
        report = (engine or RebuildEngine()).rebuild(doc)
    return report, dict(_REC.log)


# Comparing faces and edges ------------------------------------------------


def _diagonal(shape: TopoDS_Shape) -> float:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    return math.dist((lo.X(), lo.Y(), lo.Z()), (hi.X(), hi.Y(), hi.Z())) or 1.0


def _edge_signature(shape: TopoDS_Shape) -> dict[str, Any]:
    edge = TopoDS.Edge(shape)
    curve = BRepAdaptor_Curve(edge)
    mid = curve.Value(0.5 * (curve.FirstParameter() + curve.LastParameter()))
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    return {
        "surface": int(curve.GetType()),
        "point": [mid.X(), mid.Y(), mid.Z()],
        "area": props.Mass(),
    }


def _signature(kind: str, shape: TopoDS_Shape) -> dict[str, Any]:
    return face_snapshot(TopoDS.Face(shape)) if kind == "face" else _edge_signature(shape)


def _distance(a: dict[str, Any], b: dict[str, Any], scale: float) -> float:
    """How far apart two faces or edges are: 0 for the same, infinite for other kinds."""
    if a["surface"] != b["surface"]:
        return math.inf
    d = math.dist(a["point"], b["point"]) / scale
    if "normal" in a and "normal" in b:
        d += math.dist(a["normal"], b["normal"])
    if "axis" in a and "axis" in b:
        d += 1 - abs(sum(x * y for x, y in zip(a["axis"][3:], b["axis"][3:], strict=True)))
    d += 0.2 * abs(math.log(max(a["area"], 1e-9) / max(b["area"], 1e-9)))
    return d


def _all(kind: str, shape: TopoDS_Shape) -> list[TopoDS_Shape]:
    if kind == "face":
        return list(faces_of(shape))
    emap = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, emap)
    return [emap.FindKey(i) for i in range(1, emap.Extent() + 1)]


def wrong_lookups(before: dict[Key, Lookup], after: dict[Key, Lookup]) -> list[str]:
    """Names that now give a face or edge clearly farther than another candidate."""
    found = []
    for key, now in after.items():
        if key not in before:
            continue
        kind = key[1]
        old = _signature(kind, before[key].shape)
        scale = _diagonal(now.body.shape)
        given = _distance(old, _signature(kind, now.shape), scale)
        best = min(
            (_distance(old, _signature(kind, s), scale) for s in _all(kind, now.body.shape)),
            default=math.inf,
        )
        if given > 2 * best + 0.05:
            found.append(f"{key}: resolves {given:.3f} away, another {kind} is {best:.3f} away")
    return found


# Edits --------------------------------------------------------------------


Edit = tuple[str, Callable[[Document, random.Random], None]]


def _scaled(expr: str, value: float, rnd: random.Random, whole: bool) -> Param:
    number = float(expr)
    if whole:
        new = max(2.0, round(number) + rnd.choice([-1, 1]))
        text = str(int(new))
    else:
        text = f"{number * rnd.choice([0.9, 0.95, 1.05, 1.1]):.6g}"
        new = float(text)
    return Param(text, value * new / number if number else value)


def candidate_edits(doc: Document) -> list[Edit]:
    """Every edit the stress test may pick for ``doc``, in a fixed order."""
    out: list[Edit] = []
    for var in doc.variables:
        if _NUMBER.match(var.expr.strip()) and var.value:

            def set_var(d: Document, rnd: random.Random, name: str = var.name) -> None:
                v = next(v for v in d.variables if v.name == name)
                p = _scaled(v.expr, v.value, rnd, whole=False)
                v.expr, v.value = p.expr, p.value

            out.append((f"variable {var.name}", set_var))
    for feature in doc.features[4:]:
        fid = feature.id
        for key, p in feature.params.items():
            if isinstance(p, Param) and _NUMBER.match(p.expr.strip()) and p.value:

                def set_param(
                    d: Document, rnd: random.Random, fid: str = fid, key: str = key
                ) -> None:
                    f = d.feature(fid)
                    old = f.params[key]
                    assert isinstance(old, Param)
                    f.params[key] = _scaled(old.expr, old.value, rnd, bool(_WHOLE.match(key)))

                out.append((f"{feature.name} {key}", set_param))
        if feature.type == "sketch":
            for dim in feature.data.get("dimensions", []):
                p = dim.get("param")
                if dim.get("driving", True) and isinstance(p, dict | Param):
                    expr = p.expr if isinstance(p, Param) else str(p.get("expr", ""))
                    if _NUMBER.match(expr.strip()):

                        def set_dim(
                            d: Document, rnd: random.Random, fid: str = fid, did: str = dim["id"]
                        ) -> None:
                            entry = next(
                                x for x in d.feature(fid).data["dimensions"] if x["id"] == did
                            )
                            old = entry["param"]
                            if isinstance(old, Param):
                                entry["param"] = _scaled(old.expr, old.value, rnd, False)
                            else:
                                new = _scaled(str(old["expr"]), float(old["value"]), rnd, False)
                                entry["param"] = {"expr": new.expr, "value": new.value}

                        out.append((f"{feature.name} {dim['id']}", set_dim))

            def add_point(d: Document, rnd: random.Random, fid: str = fid) -> None:
                data = d.feature(fid).data
                n = data["next_entity"]
                data["entities"].append(
                    {"id": f"e{n}", "type": "point", "x": 1.25, "y": 2.5, "construction": True}
                )
                data["next_entity"] = n + 1

            out.append((f"{feature.name} new point", add_point))

        def suppress(d: Document, rnd: random.Random, fid: str = fid) -> None:
            d.feature(fid).suppressed = not d.feature(fid).suppressed

        out.append((f"suppress {feature.name}", suppress))
        index = doc.features.index(feature)
        for to in (index - 1, index + 1):
            if 4 <= to < len(doc.features) and move_problem(doc, fid, to) is None:

                def move(d: Document, rnd: random.Random, fid: str = fid, to: int = to) -> None:
                    f = d.feature(fid)
                    d.features.remove(f)
                    d.features.insert(to, f)

                out.append((f"move {feature.name} to {to}", move))
    return out


def _unclear(doc: Document, report: RebuildReport) -> list[str]:
    """Error messages that do not name a feature or that name one by its id."""
    names = [f.name for f in doc.features]
    bad = []
    for fid, result in report.results.items():
        for issue in result.issues:
            if issue.state is not FeatureState.ERROR:
                continue
            text = issue.message
            if (
                not text.endswith(".")
                or not any(n in text for n in names)
                or re.search(r"\bFeature f\d+\b", text)
            ):
                bad.append(f"{fid}: {text}")
    return bad


def _shape_of(report: RebuildReport) -> dict[str, Any] | None:
    return measure(report.body.shape) if report.body is not None else None


def _same_measure(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if a is None or b is None:
        return a is b
    return (
        (a["faces"], a["edges"]) == (b["faces"], b["edges"])
        and math.isclose(a["volume"], b["volume"], rel_tol=1e-6, abs_tol=1e-9)
        and all(math.isclose(x, y, abs_tol=1e-4) for x, y in zip(a["bbox"], b["bbox"], strict=True))
    )


def stress(path: Path, count: int) -> list[str]:
    """Run ``count`` seeded edits on the sample at ``path``; return every problem found."""
    text = path.read_text(encoding="utf-8")
    base = fdef.loads(text)
    report0, before = rebuild(base)
    problems = [
        f"start: {k} is {r.state.name}"
        for k, r in report0.results.items()
        if r.state is not FeatureState.OK
    ]
    rnd = random.Random(f"{SEED}:{path.stem}")
    edits = candidate_edits(base)
    for label, apply in rnd.sample(edits, min(count, len(edits))):
        doc = fdef.loads(text)
        warm = RebuildEngine()
        warm.rebuild(doc)  # fill the cache, as in the app
        apply(doc, rnd)
        report, after = rebuild(doc)
        problems += [f"{label}: {p}" for p in wrong_lookups(before, after)]
        problems += [f"{label}: unclear error {p}" for p in _unclear(doc, report)]
        cached = warm.rebuild(doc)
        if not _same_measure(_shape_of(cached), _shape_of(report)):
            problems.append(f"{label}: the cached rebuild differs from a full rebuild")
        if label.startswith("suppress "):
            apply(doc, rnd)  # unsuppress: the part must come back exactly
            again = warm.rebuild(doc)  # from the cache, as after Undo in the app
            fresh, lookups = rebuild(doc)
            for name, rep in (("cached", again), ("full", fresh)):
                if not _same_measure(_shape_of(rep), _shape_of(report0)):
                    problems.append(f"{label}: unsuppressing does not give the part back ({name})")
            for key, old in before.items():
                new = lookups.get(key)
                if (
                    new is None
                    or _distance(_signature(key[1], old.shape), _signature(key[1], new.shape), 1.0)
                    > 1e-6
                ):
                    problems.append(f"{label}: after unsuppress {key} no longer resolves the same")
    return problems


# Tests --------------------------------------------------------------------


@pytest.mark.parametrize("path", [p for p in SAMPLES if p.stem not in HEAVY], ids=lambda p: p.stem)
def test_quick_naming_stress(path: Path) -> None:
    assert stress(path, QUICK_EDITS) == []


@pytest.mark.slow
@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_full_naming_stress(path: Path) -> None:
    count = GEARBOX_FULL_EDITS if path.stem == "gearbox" else FULL_EDITS
    assert stress(path, count) == []


def test_every_sample_has_edits_of_each_kind() -> None:
    kinds = set()
    for path in SAMPLES:
        for label, _ in candidate_edits(fdef.load(path)):
            kinds.add(
                label.split()[0]
                if label.split()[0] in ("suppress", "move", "variable")
                else "value"
            )
    assert kinds == {"suppress", "move", "variable", "value"}


def test_the_check_finds_a_wrong_face(monkeypatch: pytest.MonkeyPatch) -> None:
    """The comparison reports a name that gives another face (a naming bug)."""
    path = SAMPLE_DIR / "plate_with_holes.fdprt"
    _, before = rebuild(fdef.load(path))
    key = next(k for k in before if k[1] == "face" and k[2].endswith("cap/end"))
    face0 = NamedShape.face

    def swapped(self: NamedShape, name: str) -> Any:
        if name == key[2]:
            return face0(self, name.replace("cap/end", "cap/start"))
        return face0(self, name)

    monkeypatch.setattr(NamedShape, "face", swapped)
    _, after = rebuild(fdef.load(path))
    assert any(str(key) in p for p in wrong_lookups(before, after))
