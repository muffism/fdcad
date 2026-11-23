"""Select Faces Between on the right click menu (TR328, D2108)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.strings_config import SEED_PICK_DONE
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect
from tests.core.test_seed_pick import _faces
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_select_faces_between(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from fdcad.core.sketch.model import Sketch

    doc, _ext = plate()
    s = Sketch()
    rect(s, 15, 15, 35, 35)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 4.0, operation="cut")
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    faces = _faces(session.report.body.shape)
    ceiling = next(f for f, c in faces if c == (25.0, 25.0, 4.0))
    bottom = next(f for f, c in faces if c[2] == 0.0)
    tab.selection = [bottom, ceiling]
    found = window.context_menus.select_between(tab, ceiling)
    assert len(found) == 5
    assert window.status.text() == SEED_PICK_DONE.format(n=5)
