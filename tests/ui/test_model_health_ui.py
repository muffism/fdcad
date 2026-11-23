"""Model Health window (TR286, D775)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature, Param
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.test_health import _plate
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["evaluate.model_health"].label == "Model Health"
    assert BY_ID["evaluate.model_health"].keys == () and audit("evaluate.model_health") == []


def test_advice_selects_and_moves_an_early_fillet(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch, rect

    doc, ext = _plate()
    fillet = doc.new_feature_id()
    doc.features.append(
        Feature(
            fillet,
            "fillet",
            "Fillet 1",
            params={"fillet_type": "constant", "radius": Param("1", 1.0)},
            refs={"faces": [{"kind": "face", "name": f"{ext}/cap/end"}]},
        )
    )
    boss = Sketch()
    rect(boss, 50, 0, 60, 10)
    add_extrude(doc, add_sketch(doc, boss, {"feature": "f2"}), 5.0)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    tool = window.model_health
    assert window.commands.trigger("evaluate.model_health")
    qtbot.waitUntil(lambda: tool.items is not None, timeout=20000)
    row = next(i for i, item in enumerate(tool.items) if item.kind == "early_round")
    tool.found.setCurrentRow(row)
    assert window.tree is not None and window.tree.selected_id() == fillet
    assert tool.move_button.isEnabled()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert tool.move_to_end()
    assert session.document.features[-1].id == fillet
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert session.document.features[-1].id != fillet


def test_link_a_typed_value_to_its_variable(qtbot: QtBot, window: MainWindow) -> None:
    """TR351, D905."""
    from fdcad.core.document.model import Variable
    from fdcad.core.units import Kind

    doc, ext = _plate()
    depth = doc.feature(ext).params["depth"]
    doc.variables.append(Variable("plate", Kind.LENGTH, depth.expr, depth.value))
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    tool = window.model_health
    assert window.commands.trigger("evaluate.model_health")
    qtbot.waitUntil(lambda: tool.items is not None, timeout=20000)
    row = next(i for i, item in enumerate(tool.items) if item.kind == "unlinked_value")
    tool.found.setCurrentRow(row)
    assert tool.link_button.isEnabled()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert tool.link_variable()
    assert session.document.feature(ext).params["depth"].expr == "plate"
