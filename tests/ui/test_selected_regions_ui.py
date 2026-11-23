"""Selected Regions box, region hover and picks in the view, and the shared sketch link
(TOOL_SPEC T5.1.6, T5.3.2, T5.3.5, DECISIONS D194). Runs offscreen with no GPU."""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, new_document
from fdcad.core.naming.regions import region_reference
from fdcad.core.sketch.model import Sketch, sketch_from_data
from fdcad.core.sketch.regions import compute
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from fdcad.ui.viewport.preview import FeaturePreview
from fdcad.ui.viewport.regions import (
    HOVER_TRANSPARENCY,
    IDLE_TRANSPARENCY,
    PICKED_HOVER_TRANSPARENCY,
    PICKED_TRANSPARENCY,
    RegionLayer,
    region_transparency,
)
from tests.core.features.test_features import add_extrude, add_sketch, rect


def _doc() -> tuple[Document, str, str, list[str], str]:
    doc = new_document()
    s = Sketch()
    sides = rect(s, 0, 0, 40, 20)
    circle = s.add_circle(40, 10, 8)
    sk = add_sketch(doc, s, {"feature": "f2"})
    return doc, sk, add_extrude(doc, sk, 5.0), sides, circle


def _session(qtbot: QtBot, doc: Document) -> DocumentSession:
    session = DocumentSession(doc)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    return session


def _ref(doc: Document, sk: str, name: str) -> dict[str, Any]:
    region = compute(sketch_from_data(doc.feature(sk).data)).find(name)
    assert region is not None
    return region_reference(region)


def _focus_in(widget: Any) -> None:
    widget.eventFilter(widget.list, QFocusEvent(QEvent.Type.FocusIn))


class FakeView(QObject):
    """Stands in for the 3D view, which needs a GPU."""

    region_clicked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.faces: dict[str, Any] = {}
        self.state: tuple[set[str], bool] | None = None
        self.hidden = 0

    def show_regions(self, faces: dict[str, Any]) -> None:
        self.faces = dict(faces)

    def set_region_state(self, picked: set[str], pickable: bool) -> None:
        self.state = (set(picked), pickable)

    def hide_regions(self) -> None:
        self.faces = {}
        self.hidden += 1

    def show_preview(self, *_args: Any) -> None:
        pass

    def clear_preview(self) -> None:
        pass


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


# Panel box ------------------------------------------------------------------------------


def test_box_takes_picks_only_while_active(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, sk, ext, sides, circle = _doc()
    panel.begin(_session(qtbot, doc), doc.feature(ext), is_new=False)
    assert "regions" in panel.groups and panel.regions is not None
    lens = _ref(doc, sk, f"region({sides[1]}+|{circle}+)")
    assert not panel.toggle_region(lens)  # not active yet
    _focus_in(panel.regions)
    assert panel.regions.active
    with qtbot.waitSignal(panel.values_changed) as blocker:
        assert panel.toggle_region(lens)
    feature = blocker.args[0]
    assert feature.refs["regions"] == [lens]
    assert panel.regions.list.item(0).text() == "Region 1"
    # Clicking the same region again removes it; an empty box leaves the key out.
    panel.toggle_region(lens)
    current = panel.current_feature()
    assert current is not None and "regions" not in current.refs


def test_another_field_ends_picking(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _sk, ext, _sides, _circle = _doc()
    panel.begin(_session(qtbot, doc), doc.feature(ext), is_new=False)
    assert panel.regions is not None
    _focus_in(panel.regions)
    depth = panel.values["depth"].edit
    panel.eventFilter(depth, QFocusEvent(QEvent.Type.FocusIn))
    assert not panel.regions.active


def test_delete_and_clear_remove_picks(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, sk, ext, sides, circle = _doc()
    panel.begin(_session(qtbot, doc), doc.feature(ext), is_new=False)
    box = panel.regions
    assert box is not None
    _focus_in(box)
    for name in (f"region({sides[1]}+|{circle}+)", f"region({sides[1]}-|{circle}+)"):
        panel.toggle_region(_ref(doc, sk, name))
    box.list.item(0).setSelected(True)
    key = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    assert box.eventFilter(box.list, key)
    assert box.names() == [f"region({sides[1]}-|{circle}+)"]
    box.clear_button.click()
    assert box.names() == []


def test_ok_stores_picks_through_undo(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, sk, ext, sides, circle = _doc()
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    assert panel.regions is not None
    _focus_in(panel.regions)
    lens = _ref(doc, sk, f"region({sides[1]}+|{circle}+)")
    panel.toggle_region(lens)
    panel.accept()
    assert session.document.feature(ext).refs["regions"] == [lens]
    session.undo.undo()
    assert "regions" not in session.document.feature(ext).refs


def test_opening_a_feature_lists_its_picks(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, sk, ext, sides, circle = _doc()
    doc.feature(ext).refs["regions"] = [_ref(doc, sk, f"region({sides[1]}+|{circle}+)")]
    panel.begin(_session(qtbot, doc), doc.feature(ext), is_new=False)
    assert panel.regions is not None and panel.regions.list.count() == 1
    assert not panel.regions.active


# View ----------------------------------------------------------------------------------


def test_regions_are_made_in_the_background_and_clicks_toggle(qtbot: QtBot) -> None:
    doc, sk, ext, sides, circle = _doc()
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    view = FakeView()
    preview = FeaturePreview()
    preview.bind(panel, lambda: view)
    panel.begin(session, doc.feature(ext), is_new=False)
    assert view.faces == {}  # nothing picked and the box is not active
    assert panel.regions is not None
    with qtbot.waitSignal(preview.regions.ready, timeout=20000) as blocker:
        _focus_in(panel.regions)
    assert len(blocker.args[0].faces) == 3
    assert len(view.faces) == 3
    assert view.state == (set(), True)
    lens = f"region({sides[1]}+|{circle}+)"
    view.region_clicked.emit(lens)
    assert panel.regions.names() == [lens]
    assert view.state == ({lens}, True)
    view.region_clicked.emit(lens)
    assert panel.regions.names() == []
    preview.regions.wait()
    panel.reject()
    assert view.faces == {} and view.hidden
    del sk


def test_region_looks() -> None:
    assert region_transparency(False, False) == IDLE_TRANSPARENCY
    assert region_transparency(False, True) == HOVER_TRANSPARENCY
    assert region_transparency(True, False) == PICKED_TRANSPARENCY
    assert region_transparency(True, True) == PICKED_HOVER_TRANSPARENCY
    assert IDLE_TRANSPARENCY > HOVER_TRANSPARENCY > PICKED_TRANSPARENCY  # picked is stronger


class _Context:
    """Records what the layer asks of the kernel's display context."""

    def __init__(self) -> None:
        self.shown: list[Any] = []
        self.active: set[int] = set()
        self.detected: list[Any] = []
        self._i = 0

    def Display(self, item: Any, *_args: Any) -> None:  # noqa: N802
        self.shown.append(item)
        self.active.add(id(item))

    def Remove(self, item: Any, _update: bool) -> None:  # noqa: N802
        self.shown.remove(item)

    def Activate(self, item: Any, _mode: int) -> None:  # noqa: N802
        self.active.add(id(item))

    def Deactivate(self, item: Any) -> None:  # noqa: N802
        self.active.discard(id(item))

    def Redisplay(self, _item: Any, _update: bool) -> None:  # noqa: N802
        pass

    def InitDetected(self) -> None:  # noqa: N802
        self._i = 0

    def MoreDetected(self) -> bool:  # noqa: N802
        return self._i < len(self.detected)

    def NextDetected(self) -> None:  # noqa: N802
        self._i += 1

    def DetectedCurrentShape(self) -> Any:  # noqa: N802
        return self.detected[self._i]


def test_layer_hover_only_while_pickable() -> None:
    from OCP.Quantity import Quantity_Color, Quantity_NOC_BLUE1

    from fdcad.core.sketch.profiles import BASIS_PLANES, region_face

    s = Sketch()
    rect(s, 0, 0, 40, 20)
    s.add_circle(40, 10, 8)
    found = compute(s)
    faces = {r.name: region_face(s, BASIS_PLANES["xy"], found, r) for r in found.regions}
    context = _Context()
    layer = RegionLayer(context, lambda: Quantity_Color(Quantity_NOC_BLUE1))
    layer.show(faces)
    assert len(context.shown) == 3 and not context.active  # not pickable yet
    name = found.regions[0].name
    context.detected = [faces[name]]
    assert layer.under_cursor() is None
    layer.set_state({name}, pickable=True)
    assert len(context.active) == 3
    assert layer.under_cursor() == name
    assert layer.set_hover(name) and not layer.set_hover(name)
    layer.set_state(set(), pickable=False)
    assert layer.hover is None and not context.active
    layer.hide()
    assert context.shown == []


# Tree ------------------------------------------------------------------------------------


def test_shared_sketch_shows_a_link_under_later_features(qtbot: QtBot) -> None:
    from fdcad.ui.tree.feature_tree import FID_ROLE, FeatureTree

    doc, sk, first, _sides, _circle = _doc()
    second = add_extrude(doc, sk, 2.0)
    session = _session(qtbot, doc)
    tree = FeatureTree()
    qtbot.addWidget(tree)
    tree.set_session(session)
    tree.refresh()
    rows = {item.data(0, FID_ROLE): item for item in tree.all_items() if item.parent() is None}
    first_children = [rows[first].child(i) for i in range(rows[first].childCount())]
    assert [c.data(0, FID_ROLE) for c in first_children] == [sk]  # nested under the first
    links = [rows[second].child(i) for i in range(rows[second].childCount())]
    assert [c.data(0, FID_ROLE) for c in links] == [sk]
    assert links[0].text(0) == f"{doc.feature(sk).name} (shared)"
    assert not links[0].flags() & Qt.ItemFlag.ItemIsEditable
