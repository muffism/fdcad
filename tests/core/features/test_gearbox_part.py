"""A gearbox of many bodies, built feature by feature as a user would (D1054 to D1068).

The owner asked for a part of at least 200 features that uses as many feature types as
it can (2026-11-12). The whole part is 318 features of 105 types in 60 bodies and
takes five minutes; it runs with the slow tests. The quick tests build the parts of it
that found the faults which need a large part to show: the housing with its cover (a
later cut spoiled the kept results of earlier features, D1067) and the body tools and
joints (numbered faces that differed between a session and its file, D1068).
"""

from __future__ import annotations

import json

import pytest
from OCP.BRepCheck import BRepCheck_Analyzer

from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine, RebuildReport
from fdcad.samples.location import sample_dir, sample_files
from tests.core.features.gearbox_builder import Gear

#: With the canary bodies in the part first, the housing block is a second body, and
#: FDCAD says so; and the parting line also runs round the canaries, whose 4 mm
#: interlock teeth break it (gaps of 4 mm): a true warning. The sample itself, with no
#: canaries, opens with no warning (D1103, checked by the sample tests).
EXPECTED_WARNINGS = frozenset({"Housing Block", "Parting Line"})


def _built(stages: list[str], canaries: bool = False) -> Gear:
    gear = Gear()
    gear.b.quiet = True
    gear.watch_valid = False
    if canaries:  # four bodies no feature works on (D1078)
        gear.canaries_at_start = gear.add_canaries()  # type: ignore[attr-defined]
    gear.build(stages)
    return gear


def _not_ok(
    gear: Gear, report: RebuildReport, expected: frozenset[str] = EXPECTED_WARNINGS
) -> dict[str, list[str]]:
    return {
        gear.b.doc.feature(fid).name: [i.message for i in result.issues]
        for fid, result in report.results.items()
        if result.state is not FeatureState.OK and gear.b.doc.feature(fid).name not in expected
    }


def _spoiled(gear: Gear, report: RebuildReport) -> list[str]:
    """Features whose kept result is not a valid solid any more."""
    bad, seen = [], None
    for feature in gear.b.doc.features:
        result = report.results.get(feature.id)
        if result is None or result.body is None:
            continue
        if seen is not None and result.body.shape.IsSame(seen):
            continue
        seen = result.body.shape
        if not BRepCheck_Analyzer(seen).IsValid():
            bad.append(feature.name)
    return bad


def _names(doc, report: RebuildReport) -> dict[str, list[str]]:  # type: ignore[no-untyped-def]
    return {
        f.id: sorted(n for n, _face in report.results[f.id].body.faces)
        for f in doc.features
        if f.id in report.results and report.results[f.id].body is not None
    }


def _differing(gear: Gear, first: dict[str, list[str]], second: dict[str, list[str]]) -> list[str]:
    return [gear.b.doc.feature(fid).name for fid in first if first[fid] != second.get(fid)]


@pytest.fixture(scope="module")
def housing() -> Gear:
    return _built(["housing", "bearings", "feet", "walls", "references", "cover",
                   "cover_details", "filler"], canaries=True)  # fmt: skip


@pytest.fixture(scope="module")
def tools() -> Gear:
    return _built(["body_tools", "joints"], canaries=True)


def test_the_housing_and_cover_build(housing: Gear) -> None:
    report = housing.b.rebuild()
    assert _not_ok(housing, report) == {}
    assert len(housing.b.doc.features) > 100
    assert len({f.type for f in housing.b.doc.features}) >= 40
    assert housing.b.valid()


def test_a_later_cut_does_not_spoil_the_results_kept_for_earlier_features(housing: Gear) -> None:
    """D1067: the grille cut in the cover left three faces of the housing not valid in
    the results kept for every feature before it."""
    assert _spoiled(housing, housing.b.rebuild()) == []


def test_body_tools_and_joints_are_named_alike_in_the_session_and_from_the_file(
    tools: Gear,
) -> None:
    """D1068: Indent and Half Lap numbered their faces in the kernel's listing order."""
    session = tools.b.rebuild()
    assert _not_ok(tools, session) == {}
    doc = fdef.loads(fdef.dumps(tools.b.doc))
    opened = RebuildEngine().rebuild(doc)
    assert _differing(tools, _names(tools.b.doc, session), _names(doc, opened)) == []
    assert _spoiled(tools, session) == []


def test_no_feature_disturbs_the_bodies_it_does_not_work_on(housing: Gear, tools: Gear) -> None:
    """D1078: with two locked blocks in the part, a plain Extrude of a new block joined
    them. Both parts are built with four canary bodies in them from the start."""
    for gear in (housing, tools):
        assert gear.canaries() == gear.canaries_at_start  # type: ignore[attr-defined]


def test_every_feature_puts_material_where_it_should(housing: Gear, tools: Gear) -> None:
    """Idea 60: each feature is followed by points that must be inside or outside the
    part (``Kit.expect``). A mirror left out a patterned foot (D1081), a fillet left out
    a picked shoulder (D1084), and both built with no error."""
    for gear in (housing, tools):
        assert gear.wrong == []
    assert housing.checks > 250 and tools.checks > 40


def test_no_two_bodies_share_material(housing: Gear, tools: Gear) -> None:
    """D1083, D1085: a lip stood inside the cover, and each leaf of a hinge stood inside
    the other, with both features OK."""
    for gear in (housing, tools):
        assert gear.overlaps() == []


@pytest.mark.slow
def test_the_whole_gearbox_leaves_the_canary_bodies_alone() -> None:
    """D1078: 318 features of 105 types. Only the Section Cut may touch the canaries: it
    cuts every body on one side of its plane."""
    gear = Gear()
    gear.b.quiet = True
    gear.watch_valid = False
    start = gear.add_canaries()
    stages = [s for s in gear.STAGES if s != "print_tools"]
    gear.build(list(stages))
    assert gear.canaries() == start
    gear.build(["print_tools"])
    assert gear.canaries() == []  # the Section Cut at x = 780 took them, as it should


@pytest.mark.slow
def test_the_whole_gearbox() -> None:
    """318 features of more than 100 types: all build, the part is valid, no kept
    result is spoiled, and the session, a new engine and the file agree on every name."""
    gear = _built([])
    session = gear.b.rebuild()
    # No canaries here: the sample opens with no warning at all (D1103).
    assert _not_ok(gear, session, expected=frozenset()) == {}
    assert len(gear.b.doc.features) >= 300
    assert len({f.type for f in gear.b.doc.features}) >= 100
    assert session.body_count > 40 and gear.b.valid()
    assert _spoiled(gear, session) == []
    fresh = RebuildEngine().rebuild(gear.b.doc)
    doc = fdef.loads(fdef.dumps(gear.b.doc))
    opened = RebuildEngine().rebuild(doc)
    # The sample part that ships with FDCAD is this part (D1069).
    saved = json.loads((sample_dir() / "gearbox.fdprt").read_text(encoding="utf-8"))
    assert json.loads(fdef.dumps(gear.b.doc)) == saved
    names = _names(gear.b.doc, session)
    assert _differing(gear, names, _names(gear.b.doc, fresh)) == []
    assert _differing(gear, names, _names(doc, opened)) == []
    # Material is where every feature should have put it, and bodies stay apart.
    assert gear.wrong == [] and gear.checks > 500
    assert gear.overlaps() == []


def test_the_gearbox_ships_as_a_sample_part() -> None:
    """D1069: the owner asked for the gearbox among the samples, to learn from. The
    slow test checks that the file is what the builder makes."""
    path = sample_dir() / "gearbox.fdprt"
    assert path in sample_files()
    doc = fdef.load(path)
    assert len(doc.features) >= 300
    assert len({f.type for f in doc.features}) >= 100
    assert not any(f.suppressed for f in doc.features)
