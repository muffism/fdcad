"""Folders inside Solid Bodies (TR153 item 1, D2106)."""

from __future__ import annotations

from fdcad.core import body_folders as bf
from fdcad.core.io import fdef
from fdcad.core.rebuild.runner import rebuild
from tests.core.test_body_titles import _two_bodies


def test_folders_follow_their_bodies() -> None:
    doc, named = _two_bodies()
    assert bf.folders_of(doc, named) == [None, None]
    doc.print_setup[bf.BODY_FOLDERS] = bf.with_folder(doc, named, [1], " Lids ")
    again = list(rebuild(doc).values())[-1].body
    assert bf.folders_of(doc, again) == [None, "Lids"]
    assert bf.members(doc, again, "Lids") == [1]
    assert bf.folder_names(doc, again) == ["Lids"]
    doc.print_setup[bf.BODY_FOLDERS] = bf.with_folder(doc, again, [0, 1], "Parts")
    assert bf.folder_names(doc, again) == ["Parts"]
    doc.print_setup[bf.BODY_FOLDERS] = bf.renamed(doc, "Parts", "All")
    assert bf.members(doc, again, "All") == [0, 1]
    loaded = fdef.loads(fdef.dumps(doc))
    assert bf.stored(loaded) == bf.stored(doc)
    doc.print_setup[bf.BODY_FOLDERS] = bf.renamed(doc, "All", "")
    assert bf.folders_of(doc, again) == [None, None]
    doc.print_setup[bf.BODY_FOLDERS] = bf.with_folder(doc, again, [0], "A")
    doc.print_setup[bf.BODY_FOLDERS] = bf.with_folder(doc, again, [0], "")
    assert bf.stored(doc) == {}
