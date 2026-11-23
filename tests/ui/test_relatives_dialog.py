"""Parents and Children dialog (TR96 item 2, D942)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document import dependencies
from fdcad.ui.tree.relatives_dialog import RelativesDialog
from tests.core.features.phase3_parts import block_with_hole_and_boss
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _names(widget) -> list[str]:  # type: ignore[no-untyped-def]
    return [widget.item(i).text() for i in range(widget.count())]


def test_lists_and_walks(qtbot: QtBot) -> None:
    doc, ids = block_with_hole_and_boss()
    plate = ids["plate"]
    dialog = RelativesDialog(doc, plate)
    qtbot.addWidget(dialog)
    assert _names(dialog.parents) == [f.name for f in dependencies.parents_of(doc, plate)]
    children = dependencies.children_of(doc, plate)
    assert children and _names(dialog.children_list) == [f.name for f in children]
    child = dialog.children_list.item(0)
    dialog.children_list.itemDoubleClicked.emit(child)
    assert dialog.fid == children[0].id and dialog.walked == [children[0].id]
    assert plate in [dialog.parents.item(i).data(0x0100) for i in range(dialog.parents.count())]


def test_nothing_shows_a_plain_row(qtbot: QtBot) -> None:
    doc, ids = block_with_hole_and_boss()
    boss = ids["boss"]
    dialog = RelativesDialog(doc, boss)
    qtbot.addWidget(dialog)
    if not dependencies.children_of(doc, boss):
        assert _names(dialog.children_list) == ["nothing"]
        dialog.children_list.itemDoubleClicked.emit(dialog.children_list.item(0))
        assert dialog.fid == boss  # the empty row does not walk


def test_tree_arrows(qtbot: QtBot, window) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    """TR96 item 1: arrows to parents and children, off until the part row turns them on."""
    from fdcad.ui.tree.feature_tree import FID_ROLE, PART_MARK
    from tests.ui.test_body_tools import _open

    tab, ids = _open(qtbot, window)
    tree = window.tree
    assert tree is not None and not tree.relation_arrows
    part = next(i for i in tree.all_items() if i.data(0, FID_ROLE) == PART_MARK)
    menu = tree._context_menu(tab.session, part)
    assert menu is not None
    action = next(a for a in menu.actions() if a.objectName() == "relation_arrows")
    assert not action.isChecked()
    tree.select(ids["plate"])
    assert tree.arrow_rows() is None  # off
    action.setChecked(True)
    assert tree.relation_arrows
    found = tree.arrow_rows()
    assert found is not None
    _source, _parents, children = found
    assert children  # the boss and hole stand on the plate
    tree.grab()  # paints the arrows
    # A child inside a closed row points at that row.
    for row in children:
        assert row.parent() is None or row.parent().isExpanded()
    tree.set_relation_arrows(False)
    assert tree.arrow_rows() is None
