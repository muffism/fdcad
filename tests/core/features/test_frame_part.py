"""A bike frame, built feature by feature as a user would (D1043 to D1052).

The owner asked for an extremely complex part to prove the modeller (2026-11-12). The
whole frame is 103 features and takes two minutes; this builds the part of it that
found the faults: the lofted and swept tubes, the stays with domed ends, the dropouts,
the mirror, the bores, three joint fillets, a Mounting Boss with its pattern on the
hollow down tube, the wrapped head badge, the hanger with a tapped hole, the eyelets
and the threads. It checks that every feature builds, that the wrap and the boss have
the volume they should, and that the part opens from its file as it was built.
"""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import precise_volume
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.frame_builder import SIZES, Frame, area


@pytest.fixture(scope="module")
def frame() -> Frame:
    f = Frame(SIZES["m"])
    f.b.quiet = True
    f.build("bores")
    # The quick volume is too rough to weigh a badge on a frame: it can be 1 percent off
    # on spline faces, and the frame is 2000 times the badge.
    f.volumes = {}  # type: ignore[attr-defined]
    f.weld("Weld Top Tube to Head Tube", [((f.top,), (f.head,))], 5.0)
    f.weld("Weld Top Tube to Seat Tube", [((f.top,), (f.seat,))], 5.0)
    f.weld("Weld Seat Tube to BB", [((f.seat,), (f.shell,))], 4.0)
    for step in ("bottle_bosses", "head_badge", "hanger", "eyelets", "small_cuts", "finish"):
        before = precise_volume(f.b.body.shape)
        getattr(f, step)()
        f.volumes[step] = precise_volume(f.b.body.shape) - before  # type: ignore[attr-defined]
    return f


def test_every_feature_builds_into_one_valid_solid(frame: Frame) -> None:
    report = frame.b.rebuild()
    bad = {
        frame.b.doc.feature(fid).name: [i.message for i in result.issues]
        for fid, result in report.results.items()
        if result.state is not FeatureState.OK
    }
    assert bad == {}
    assert report.body_count == 1 and frame.b.valid()
    assert len(frame.b.doc.features) > 80


def test_the_head_badge_is_there(frame: Frame) -> None:
    """D1049: it built with no error and added 0.27 mm3."""
    added = frame.volumes["head_badge"]  # type: ignore[attr-defined]
    assert 280.0 < added < 400.0, added
    top = [f for n, f in frame.b.body.faces if n.startswith(f"{frame.badge}/")]
    assert max(area(f) for f in top) == pytest.approx(377.0, rel=0.15)


def test_the_bottle_bosses_stand_on_the_tube_and_do_not_fill_it(frame: Frame) -> None:
    """D1045 and D1046: two bosses, each a ring of about 170 mm3 less its hole through
    the wall. One boss had filled the tube (2684 mm3), and it could not be patterned."""
    added = frame.volumes["bottle_bosses"]  # type: ignore[attr-defined]
    assert 250.0 < added < 400.0, added
    assert frame.b.ok(frame.boss_pattern)


def test_the_frame_opens_from_its_file_as_it_was_built(frame: Frame) -> None:
    """D1049 and D1052: the frame as first built reopened with eleven features in error."""
    built = frame.b.rebuild()
    doc = fdef.loads(fdef.dumps(frame.b.doc))
    opened = RebuildEngine().rebuild(doc)
    states = {fid: r.state for fid, r in opened.results.items()}
    assert states == {fid: r.state for fid, r in built.results.items()}
    assert all(state is FeatureState.OK for state in states.values())

    def faces(report: object) -> list[tuple[str, float]]:
        body = report.body  # type: ignore[attr-defined]
        return sorted((name, round(area(face), 1)) for name, face in body.faces)

    assert faces(opened) == faces(built)


def test_material_is_where_the_features_put_it(frame: Frame) -> None:
    """Idea 60: tubes hollow, stays and dropouts on both sides, slots and holes open."""
    assert frame.place_checks() == []
    assert frame.place_count > 25  # type: ignore[attr-defined]


@pytest.mark.slow
def test_the_whole_frame() -> None:
    """All 103 features, with the welds, guides, clamp slot and text the quick test leaves
    out: all build into one valid solid and material is where it should be."""
    f = Frame(SIZES["m"])
    f.b.quiet = True
    f.build()
    report = f.b.rebuild()
    assert all(r.state is FeatureState.OK for r in report.results.values())
    assert report.body_count == 1 and f.b.valid()
    assert f.place_checks() == []
    assert f.place_count > 35  # type: ignore[attr-defined]
