"""Instance markers of a pattern (TR59 item 4, D2400)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import BuildContext
from fdcad.core.features.pattern_markers import instance_label, instance_markers, parse_label
from fdcad.core.features.preview import body_before, build_preview
from tests.core.features.test_patterns import X, Y, centred, count, length, pattern


def _ctx(doc, fid, results) -> BuildContext:  # type: ignore[no-untyped-def]
    return BuildContext(doc, body_before(doc, doc.feature(fid), results), results, {})


def test_labels_read_back() -> None:
    assert instance_label((3, 1)) == "3"
    assert instance_label((2, 2)) == "2.2"
    assert parse_label("2.2") == (2, 2)
    assert parse_label("4") == (4, 1)
    assert parse_label("x") is None and parse_label("2.") == (2, 1)


def test_each_copy_gets_a_marker_at_its_seed_middle_moved() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {
            "spacing1": length(12),
            "count1": count(3),
            "reverse1": True,
            "second_direction": True,
            "spacing2": length(20),
            "count2": count(2),
            "reverse2": True,
        },
        {"direction1": X, "direction2": Y, "features": [{"feature": boss}]},
        skip=[[3, 1]],
    )
    markers = dict(instance_markers(doc.feature(fid), _ctx(doc, fid, results)))
    assert set(markers) == {"2", "3", "1.2", "2.2", "3.2"}  # skipped copies keep a marker
    seed = (10.0, 10.0, 13.0)  # the boss middle: 5 to 15 in x and y, 10 to 16 in z
    two = markers["2"]
    assert abs(two[0] - seed[0]) == pytest.approx(12.0)
    assert two[2] == pytest.approx(seed[2])
    assert markers["1.2"][0] == pytest.approx(seed[0])


def test_preview_carries_markers_and_other_features_have_none() -> None:
    from tests.core.features.test_patterns import angle

    doc, plate, boss = centred()
    fid, results = pattern(
        doc,
        "circular_pattern",
        {"count1": count(4), "angle1": angle(360)},
        {"axis": {"feature": "f1", "axis": "z"}, "features": [{"feature": boss}]},
    )
    geometry = build_preview(doc, doc.feature(fid), results)
    assert geometry.error is None
    assert [label for label, _p in geometry.markers] == ["2", "3", "4"]
    x, y, _z = dict(geometry.markers)["3"]  # half a turn about z
    assert (x, y) == (pytest.approx(-10.0), pytest.approx(-10.0))
    assert build_preview(doc, doc.feature(plate), results).markers == []
    copy = doc.feature(fid)
    copy.data["only"] = [2, 1]
    assert instance_markers(copy, _ctx(doc, fid, results)) == []
