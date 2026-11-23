"""Push Pull panel (TR267, DECISIONS D1413).

Flat faces or a sketch on a face, a signed distance, Symmetric for a sketch, and
Next Parallel Face, which steps through the faces parallel to the first picked
face, nearest first, and makes the next one the target (as Tab does while
dragging in other programs). Every picked face takes the same distance.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QPushButton

from fdcad.core.document.model import Feature
from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import form
from fdcad.ui.property_panel.forms.spec_form import F, G, SpecForm


@form("push_pull")
class PushPullForm(SpecForm):
    """Edits a Push Pull feature."""

    first_param = "distance"
    layout = (
        G(
            "push_pull",
            strings.PUSH_PULL,
            strings.PUSH_PULL_TIP,
            (
                F("faces", strings.PUSH_PULL_FACES, "faces", strings.PUSH_PULL_FACES_TIP,
                  optional=True),
                F("sketch", strings.PUSH_PULL_SKETCH, "sketch", strings.PUSH_PULL_SKETCH_TIP,
                  optional=True),
                F("distance", strings.PUSH_PULL_DISTANCE, "length", strings.PUSH_PULL_TIP, 5.0),
                F("symmetric", strings.PUSH_PULL_SYMMETRIC, "bool", strings.PUSH_PULL_SYMMETRIC_TIP,
                  when=lambda v: bool(v.get("sketch"))),
                F("to_face", strings.PUSH_PULL_TARGET, "faces", strings.PUSH_PULL_TARGET_TIP,
                  single=True, optional=True, when=lambda v: bool(v.get("faces"))),
            ),
        ),
    )  # fmt: skip

    def after_groups(self) -> None:
        """Next Parallel Face."""
        self.next_face = QPushButton(strings.PUSH_PULL_NEXT)
        self.next_face.setToolTip(strings.PUSH_PULL_NEXT_TIP)
        self.next_face.clicked.connect(self.next_parallel)
        self.spec_groups["push_pull"].form.addRow(self.next_face)
        self._step = -1

    def next_parallel(self) -> str | None:
        """Make the next parallel face, nearest first, the target."""
        from fdcad.core.features.push_pull import parallel_targets
        from fdcad.core.naming.select import reference_for

        body = self.body_before()
        faces = self.picks["faces"].refs()
        if body is None or not faces:
            return strings.PUSH_PULL_PICK_FIRST
        first = body.face(str(faces[0].get("name", "")))
        if first is None:
            return strings.PUSH_PULL_PICK_FIRST
        targets = parallel_targets(body, first)
        if not targets:
            return strings.PUSH_PULL_NO_PARALLEL
        self._step = (self._step + 1) % len(targets)
        name, distance = targets[self._step]
        face = body.face(name)
        ref = reference_for(body, face) if face is not None else None
        if ref is not None:
            self.picks["to_face"].set_refs([ref])
            self.picks["to_face"].changed.emit()
        self.fields["distance"].edit.setText(f"{distance:.6g}")
        return None

    def take_shapes(self, body: Any, shapes: list[Any]) -> str | None:
        """Picked faces are pushed (the target is set by Next Parallel Face, or by
        clicking its list first)."""
        if self.active_pick is None:
            self.active_pick = "faces"
        return super().take_shapes(body, shapes)

    def extra_apply(self, feature: Feature) -> str | None:
        """Faces or a sketch, not both and not neither."""
        faces, sketch = feature.refs.get("faces"), feature.refs.get("sketch")
        if not faces and not sketch:
            return strings.PUSH_PULL_NEEDS
        if faces and sketch:
            feature.refs.pop("sketch", None)
        return None


def start_push_pull(window: Any, tab: Any) -> None:
    """Open a new Push Pull; the selected faces become its faces."""
    from fdcad.ui.main_window.new_feature import FeatureFlow

    if getattr(window, "feature_flow", None) is None:
        window.feature_flow = FeatureFlow(window)
    window.feature_flow.open_direct(tab, "push_pull", "boss")
