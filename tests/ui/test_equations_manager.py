"""Equations manager in the window (PHASE4_SPEC P4.10 item 1, D390)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLineEdit
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param, Variable
from fdcad.core.units import Kind
from fdcad.ui import strings_config as text
from fdcad.ui.equations.dialog import MARK, NAME, RESULT, VALUE, EquationsDialog
from fdcad.ui.equations.tree_rows import EQUATIONS_ROLE
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.feature_dims import ModelDimension
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.equations.test_equations import _plate
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _open(qtbot: QtBot, window: MainWindow) -> DocumentTab:  # noqa: F811
    session = DocumentSession(_plate(), None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def _row(dialog: EquationsDialog, name: str):  # type: ignore[no-untyped-def]
    return next(i for i in dialog.items() if i.text(NAME) == f'"{name}"')


def test_command_menu_and_tree_folder(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    assert "tools.equations" in BY_ID and "tools.equations" in window.commands.actions
    _open(qtbot, window)
    assert window.tree is not None
    folder = next(i for i in window.tree.all_items() if i.data(0, EQUATIONS_ROLE) == "equations")
    assert folder.childCount() == 1
    assert folder.child(0).text(0).startswith('"Width" = 60')


def test_sections_rows_marks_and_values(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    assert isinstance(dialog, EquationsDialog)
    titles = [dialog.tree.topLevelItem(i).text(0) for i in range(3)]
    assert titles == list(text.EQ_SECTIONS.values())
    width = _row(dialog, "Width")
    assert width.text(VALUE) == "60" and width.text(MARK) == text.EQ_OK_MARK
    assert width.text(RESULT).startswith("60")
    # The sketch's width dimension uses =Width, so it is listed as an equation.
    assert _row(dialog, "d1@Sketch 1").text(VALUE) == "=Width"


def test_typing_a_name_quotes_it_and_starts_the_value(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    head = dialog.sections["variable"]
    add = head.child(head.childCount() - 1)
    assert add.text(NAME) == text.EQ_ADD["variable"]
    add.setText(NAME, "Thick")
    assert add.text(NAME) == '"Thick"' and add.text(VALUE) == "="
    assert head.child(head.childCount() - 1).text(NAME) == text.EQ_ADD["variable"]
    qtbot.wait(20)
    editor = QApplication.focusWidget()
    assert isinstance(editor, QLineEdit) and editor.text() == "="
    add.setText(VALUE, "=Width / 5")
    assert add.text(MARK) == text.EQ_OK_MARK and add.text(RESULT).startswith("12")
    add.setText(VALUE, "=Width +")
    assert add.text(MARK) == text.EQ_BAD_MARK
    assert "incomplete" in add.toolTip(VALUE)


def test_circular_reference_is_shown(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    a = dialog.add("variable", "A", "=B")
    b = dialog.add("variable", "B", "=A")
    assert a.text(MARK) == text.EQ_BAD_MARK and b.text(MARK) == text.EQ_BAD_MARK
    assert "Circular reference" in dialog.message.text()


def test_ok_applies_one_undo_step_and_rebuilds(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    dialog.add("variable", "Thick", "=12mm", "plate thickness")
    dialog.add("equation", "depth@Extrude 1", '="Thick"')
    count = session.undo.count()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        dialog.accept()
    assert session.undo.count() == count + 1
    doc = session.document
    assert doc.variables[-1] == Variable("Thick", Kind.LENGTH, "=12mm", 12.0, "plate thickness")
    depth = doc.features[-1].params["depth"]
    assert isinstance(depth, Param) and depth.expr == '="Thick"' and depth.value == 12.0
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert [v.name for v in session.document.variables] == ["Width"]


def test_feature_value_row_suppresses(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    row = dialog.add("feature", "Extrude 1", '=if("Width" > 50mm, suppressed, unsuppressed)')
    assert row.text(RESULT) == text.EQ_SUPPRESSED
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        dialog.accept()
    assert tab.session.document.features[-1].suppressed


def test_dimension_double_clicked_in_the_view_goes_into_the_cell(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    row = dialog.add("variable", "Twice", "=")
    dialog._last_cell = (row, VALUE)
    fid = tab.session.document.features[-1].id
    item = ModelDimension("k", fid, "10", "10", (0.0, 0.0, 0.0), Kind.LENGTH, param="depth")
    window.model_dims.items = {"k": item}
    assert window.model_dims.edit("k") is None  # no value box: the pick went to the manager
    assert row.text(VALUE) == '="depth@Extrude 1"'
    assert row.text(MARK) == text.EQ_OK_MARK


def test_renamed_or_deleted_variable_keeps_or_drops_its_configured_values(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.core import configurations as configs
    from fdcad.ui.equations.commands import DocumentChange

    tab = _open(qtbot, window)
    session = tab.session
    session.document.variables.append(Variable("Spare", Kind.LENGTH, "5", 5.0))
    session.undo.push(DocumentChange(session, "add", lambda d: configs.add(d, "Long")))
    for name in ("Width", "Spare"):
        session.undo.push(
            DocumentChange(
                session,
                "w",
                lambda d, p=f"var.{name}": configs.set_scoped(d, p, Param("80", 80.0), "this"),
            )
        )
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    _row(dialog, "Width").setText(NAME, "W")
    dialog.tree.setCurrentItem(_row(dialog, "Spare"))
    dialog.delete_row()
    dialog.accept()
    doc = session.document
    assert configs.configured_paths(doc) == ["var.W"]
    session.undo.undo()
    assert configs.configured_paths(session.document) == ["var.Spare", "var.Width"]


def test_ok_refuses_a_variable_name_no_formula_can_use(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    row = dialog.add("variable", "My Var", "=5mm")
    assert row.text(MARK) == text.EQ_BAD_MARK
    assert _row(dialog, "Width").text(MARK) == text.EQ_OK_MARK  # only the bad row is marked
    dialog.accept()
    assert "not a valid variable name" in dialog.message.text()
    assert [v.name for v in tab.session.document.variables] == ["Width"]


def test_allowed_values_are_kept_and_warned_about(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR274, D906."""
    tab = _open(qtbot, window)
    session = tab.session
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    dialog.ask_allowed = lambda _name, _current: "1..5"  # type: ignore[method-assign]
    assert dialog.edit_allowed("Width")
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        dialog.accept()
    width = next(v for v in session.document.variables if v.name == "Width")
    assert width.allowed == {"min": 1.0, "max": 5.0}
    assert "above its largest allowed value" in window.status.text()
