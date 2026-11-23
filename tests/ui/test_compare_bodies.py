"""Compare Bodies (TR27, D758)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.ui.command_tabs.tabs import EVALUATE_GROUPS
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.compare_bodies import STEP_CHOICE
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_command_icon_and_tab() -> None:
    from fdcad.ui.icons.audit import audit

    command = BY_ID["evaluate.compare_bodies"]
    assert command.label == "Compare Bodies" and command.keys == ()
    assert audit("evaluate.compare_bodies") == []
    listed = [
        c for _g, big, small in EVALUATE_GROUPS for c in [*big, *(x for s in small for x in s)]
    ]
    assert "evaluate.compare_bodies" in listed


def test_two_bodies_apart(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)  # two equal blocks 10 mm apart
    tool = window.compare_bodies
    assert window.commands.trigger("evaluate.compare_bodies")
    assert tool.panel.isVisible()
    assert [tool.first.itemText(i) for i in range(tool.first.count())] == ["Body 1", "Body 2"]
    assert tool.second.currentData() == 1 and tool.second.itemData(2) == STEP_CHOICE
    assert tool.compare()
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)
    assert "6 faces of the first body differ" in tool.summary.text()
    assert len(tab.viewport.painted_faces) == 6  # type: ignore[attr-defined]
    assert len(tab.viewport.print_layers["compare_first"]) == 1  # type: ignore[attr-defined]
    assert not tab.session.is_dirty  # display only
    assert window.commands.trigger("evaluate.compare_bodies")
    assert tab.viewport.painted_faces == []  # type: ignore[attr-defined]
    assert tab.viewport.print_layers["compare_first"] == []  # type: ignore[attr-defined]


def test_the_choices_are_not_cut_short(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """D1042: "STEP file..." showed as "STEP fil" in a box sized before it was filled."""
    _open(qtbot, window)
    tool = window.compare_bodies
    window.commands.trigger("evaluate.compare_bodies")
    qtbot.waitUntil(tool.panel.isVisible)
    for box in (tool.first, tool.second):
        widest = max(
            box.fontMetrics().horizontalAdvance(box.itemText(i)) for i in range(box.count())
        )
        assert box.width() >= widest + 30, (box.width(), widest)  # the text and the arrow


def test_the_same_body_twice_is_refused(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    _open(qtbot, window)
    tool = window.compare_bodies
    window.commands.trigger("evaluate.compare_bodies")
    tool.second.setCurrentIndex(0)
    assert not tool.compare()
    assert "Choose another body" in tool.summary.text()


def test_compare_with_a_step_file(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    from fdcad.core.features.solids import solids
    from fdcad.core.io.export import export_step

    tab = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    step = tmp_path / "first.step"
    export_step(solids(report.body.shape)[0], step)
    tool = window.compare_bodies
    window.commands.trigger("evaluate.compare_bodies")
    tool.second.setCurrentIndex(tool.second.findData(STEP_CHOICE))
    assert not tool.compare()
    assert "No STEP file chosen" in tool.summary.text()
    tool.step_path = step
    assert tool.compare()
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)
    assert tool.summary.text() == "The bodies are the same."
