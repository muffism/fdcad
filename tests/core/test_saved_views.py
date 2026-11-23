"""Saved views in the part file (TR14.2, D690)."""

from __future__ import annotations

import pytest

from fdcad.core.document import saved_views as sv
from fdcad.core.document.model import Document
from fdcad.core.io import fdef
from fdcad.core.io.migrations import FileFormatError

SIDE = sv.SavedView("Side", (1.0, 2.0, 3.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0), 500.0, 80.0)


def test_round_trip_through_the_file() -> None:
    doc = Document()
    doc.views = sv.save_view([], SIDE)
    back = fdef.loads(fdef.dumps(doc))
    assert sv.find(back.views, "Side") == SIDE


def test_parts_without_views_save_without_the_key() -> None:
    assert '"views"' not in fdef.dumps(Document())


def test_update_rename_delete_and_names() -> None:
    views = sv.save_view([], SIDE)
    moved = sv.SavedView("Side", (0, 0, 0), (1, 0, 0), (0, 1, 0), 10.0, 5.0)
    views = sv.save_view(views, moved)  # same name: update
    assert len(views) == 1 and sv.find(views, "Side") == moved
    assert sv.name_problem(views, " side ") != ""
    assert sv.name_problem(views, "") != ""
    assert sv.name_problem(views, "Top Corner") == ""
    views = sv.rename_view(views, "Side", "Left Side")
    assert sv.names(views) == ["Left Side"]
    with pytest.raises(sv.SavedViewError):
        sv.rename_view(views, "Left Side", "")
    assert sv.delete_view(views, "Left Side") == []


def test_damaged_views_make_the_file_damaged() -> None:
    data = fdef.to_json_data(Document())
    data["views"] = [{"name": "Bad", "center": [0, 0], "direction": [0, 0, 1], "up": [0, 1, 0]}]
    with pytest.raises(FileFormatError):
        fdef.from_json_data(data)
