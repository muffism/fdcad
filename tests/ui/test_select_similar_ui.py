"""Select Similar and selection conversion in the window (TR303, D943)."""

from __future__ import annotations

import pytest
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from pytestqt.qtbot import QtBot

from fdcad.core.select_similar import describe
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window import select_similar as module
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _hole_wall, _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


class _View:
    """The parts of the 3D view the commands use (offscreen runs have no 3D view)."""

    def __init__(self, part: object) -> None:
        self._part_shape = part
        self.picks: list = []

    def selected(self) -> list:
        return list(self.picks)

    def select_shapes(self, shapes: list, add: bool = False) -> None:
        self.picks = [*self.picks, *shapes] if add else list(shapes)


def test_commands(window: MainWindow) -> None:  # noqa: F811
    for cid in ("select.similar", "select.to_edges", "select.to_faces", "select.to_bodies"):
        assert cid in BY_ID and cid in window.commands.actions
        assert BY_ID[cid].keys == ()


def test_similar_and_convert(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab, _ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    view = _View(report.body.shape)
    monkeypatch.setattr(tab, "viewport", view)
    wall = _hole_wall(tab)
    view.select_shapes([wall])
    assert window.select_similar.similar((["kind_size"], False, []))
    assert window.select_similar.wait()
    qtbot.waitUntil(lambda: "items picked" in window.status.text(), timeout=5000)
    picked = view.selected()
    assert picked and all(describe(f).kind == "cylinder" for f in picked)
    assert window.select_similar.convert("edges") > 0
    assert all(s.ShapeType() == TopAbs_EDGE for s in view.selected())
    assert window.select_similar.convert("faces") > 0
    assert all(s.ShapeType() == TopAbs_FACE for s in view.selected())
    assert window.select_similar.convert("bodies") >= len(picked)
    # The dialog can be cancelled; no rule set to Must match is refused.
    monkeypatch.setattr(module, "ask_rules", lambda _p: None)
    view.select_shapes([wall])
    assert not window.select_similar.similar()
    assert not window.select_similar.similar(([], False, ["area"]))
    assert "Must match" in window.status.text()
    view.select_shapes([])
    assert not window.select_similar.similar((["area"], False, []))
    assert "needs a picked face" in window.status.text()


def test_dialog_rules(qtbot: QtBot) -> None:
    dialog = module.SimilarDialog()
    qtbot.addWidget(dialog)
    assert dialog.rules() == (["kind_size"], False, [])
    dialog.choices["area"].setCurrentIndex(dialog.choices["area"].findData(module.EXCEPT))
    dialog.match.setCurrentIndex(1)
    assert dialog.rules() == (["kind_size"], True, ["area"])
