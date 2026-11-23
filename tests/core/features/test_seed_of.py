"""The seed of a pattern copy (TR142 item 2, D1016)."""

from __future__ import annotations

from fdcad.core.features.seed_of import seed_of
from tests.core.features.phase3_parts import ok_body
from tests.core.features.test_patterns import X, centred, count, length, pattern


def test_a_copy_face_leads_to_the_seed() -> None:
    doc, plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    names = [n for n, _f in ok_body(results, fid).faces]
    copy = next(n for n in names if "/instance2.1/" in n)
    assert seed_of(doc, copy) == boss
    assert seed_of(doc, f"face({copy}|x)") == boss  # inside a reference name
    plain = next(n for n in names if n.startswith(f"{plate}/"))
    assert seed_of(doc, plain) is None
    assert seed_of(doc, "f99/instance2.1/side") is None


def test_a_copy_face_gives_its_instance_number() -> None:
    """TR59 item 3 (D1900): Copy Values from the view starts that copy's entry."""
    from fdcad.core.features.seed_of import add_instance_values, instance_of

    doc, plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    names = [n for n, _f in ok_body(results, fid).faces]
    copy = next(n for n in names if "/instance3.1/" in n)
    assert instance_of(doc, copy) == (fid, (3, 1))
    assert instance_of(doc, next(n for n in names if n.startswith(f"{plate}/"))) is None
    assert add_instance_values("", (3, 1)) == "3: "
    assert add_instance_values("2: depth 4", (2, 2)) == "2: depth 4; 2.2: "
    assert add_instance_values("2: depth 4; 3: depth 1", (3, 1)) == "2: depth 4; 3: depth 1"
