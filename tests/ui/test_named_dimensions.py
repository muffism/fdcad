"""Named dimensions and Show All Dimensions in the window (TR32, D698)."""

from __future__ import annotations

import copy
from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Variable
from fdcad.core.equations.value_names import set_value_name, value_name
from fdcad.core.io import fdef
from fdcad.core.units import Kind
from fdcad.samples.make import SAMPLE_DIR
from fdcad.ui.commands.document import ReplaceFeature
from fdcad.ui.equations.table_dialog import column_title
from fdcad.ui.main_window.feature_dims import all_dimensions, model_dimensions
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from tests.ui.sketch_tools.p2_helpers import canvas_of
from tests.ui.test_main_window import _folders, window
from tests.ui.test_property_panel import _session

__all__ = ["_folders", "window"]


def _bracket(qtbot: QtBot) -> DocumentSession:
    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    return _session(qtbot, doc)


def test_sketch_dimension_panel_names_a_dimension(qtbot: QtBot) -> None:
    from fdcad.core.document.model import Param
    from fdcad.core.sketch.model import Sketch

    sk = Sketch()
    line = sk.add_line(0, 0, 10, 0)
    sk.dimension("distance", [line], Param("10mm", 10))
    canvas, _panel = canvas_of(qtbot, sk)
    assert canvas.set_dimension_name("d1", "wall") == ""
    assert canvas.edit.sketch.dimensions[0].name == "wall"
    assert canvas.set_dimension_name("d1", "9lives") != ""
    canvas.undo()
    assert canvas.edit.sketch.dimensions[0].name is None


def test_panel_names_a_feature_value_on_ok(qtbot: QtBot) -> None:
    session = _bracket(qtbot)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, session.document.feature("f6"), is_new=False)
    assert panel.ask_value_name("depth", "width") == ""
    edited = panel.current_feature()
    assert edited is not None and value_name(edited, "depth") == "width"
    assert panel.ask_value_name("depth", "bad name") != ""


def test_replace_feature_rewrites_formulas_for_a_renamed_value(qtbot: QtBot) -> None:
    session = _bracket(qtbot)
    doc = session.document
    named = copy.deepcopy(doc.feature("f6"))
    set_value_name(named, "depth", "width")
    session.undo.push(ReplaceFeature(session, named))
    doc.variables.append(Variable("A", Kind.LENGTH, '="width@Bracket" * 2', 80.0))
    renamed = copy.deepcopy(doc.feature("f6"))
    set_value_name(renamed, "depth", "span")
    session.undo.push(ReplaceFeature(session, renamed))
    assert doc.variables[0].expr == '="span@Bracket" * 2'
    session.undo.undo()
    assert doc.variables[0].expr == '="width@Bracket" * 2'
    assert column_title(doc, "f6.depth") == "width (Bracket)"
    assert column_title(doc, "f6.reverse") == "f6.reverse"


def _open(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def test_show_all_dimensions(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    tab = _open(qtbot, window)
    one = model_dimensions(tab.session, "f6")
    every = all_dimensions(tab.session)
    assert len(every) > len(one) > 0
    assert len({d.key for d in every}) == len(every)
    assert window.commands.trigger("view.all_dimensions")
    assert window.model_dims.show_all and len(window.model_dims.items) == len(every)
    assert window.commands.trigger("view.all_dimensions")
    assert not window.model_dims.show_all
    assert window.tree is not None
    part = window.tree.topLevelItem(0)
    assert part is not None
    menu = window.tree._context_menu(tab.session, part)
    assert menu is not None and "Show All Dimensions" in [a.text() for a in menu.actions()]


def test_a_renamed_value_follows_into_node_editor_formulas(qtbot: QtBot) -> None:
    """Audit D3 item 5 (D735): graph formulas kept the old name, and undo did not
    restore them."""
    from fdcad.core.document.model import Param
    from fdcad.core.graph.model import Graph, Node

    session = _bracket(qtbot)
    doc = session.document
    named = copy.deepcopy(doc.feature("f6"))
    set_value_name(named, "depth", "width")
    session.undo.push(ReplaceFeature(session, named))
    node = Node("n1", "number", {"value": Param('="width@Bracket" * 2', 80.0)})
    doc.graphs.append(Graph("g1", "Graph 1", nodes=[node]))
    renamed = copy.deepcopy(doc.feature("f6"))
    set_value_name(renamed, "depth", "span")
    session.undo.push(ReplaceFeature(session, renamed))
    assert doc.graphs[0].nodes[0].params["value"].expr == '="span@Bracket" * 2'
    session.undo.undo()
    assert doc.graphs[0].nodes[0].params["value"].expr == '="width@Bracket" * 2'
