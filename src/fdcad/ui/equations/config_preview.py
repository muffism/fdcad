"""Preview Configuration: a small window showing one configuration built on a copy,
without making it active (TR197 item 2, D2101)."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from fdcad.ui import strings_config as text

if TYPE_CHECKING:
    from fdcad.core.config_preview import Preview
    from fdcad.ui.session import DocumentSession


class ConfigPreview(QDialog):
    """Builds configuration ``name`` in the background and shows it."""

    def __init__(
        self,
        session: DocumentSession,
        name: str,
        parent: QWidget | None = None,
        doc: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("config_preview")
        self.setWindowTitle(text.CONFIG_PREVIEW_TITLE.format(name=name))
        self.name = name
        self.built: Preview | None = None
        self.message = QLabel(text.CONFIG_PREVIEW_BUILDING.format(name=name))
        self.message.setObjectName("config_preview_message")
        self.message.setWordWrap(True)
        layout = QVBoxLayout(self)
        self.view: Any = None
        from fdcad.ui.main_window.window import viewport_supported

        if viewport_supported():
            from fdcad.ui.viewport.widget import ViewportWidget

            self.view = ViewportWidget(self)
            layout.addWidget(self.view, 1)
        layout.addWidget(self.message)
        self.resize(360, 300)
        self.job: Any = None
        # ``doc``: a ready copy to build instead, such as trial values (TR331).
        self._start(doc if doc is not None else copy.deepcopy(session.document))

    def _start(self, doc: Any) -> None:
        from fdcad.core.config_preview import build
        from fdcad.ui.main_window.window import _Job

        found: dict[str, Preview] = {}
        name = self.name

        def work() -> str:
            from fdcad.ui.strings import clause

            try:
                found["preview"] = build(doc, name)
            except Exception as exc:  # report, never crash
                return text.CONFIG_PREVIEW_ERROR.format(name=name, reason=clause(exc))
            return ""

        job = _Job(work)
        job.signals.done.connect(lambda message: self.finished_build(found.get("preview"), message))
        self.job = job
        QThreadPool.globalInstance().start(job)

    def finished_build(self, preview: Preview | None, message: str = "") -> None:
        """Show the built shape, or say why there is none."""
        self.built = preview
        if preview is None:
            self.message.setText(message or text.CONFIG_PREVIEW_NONE.format(name=self.name))
            return
        if preview.shape is None:
            self.message.setText(text.CONFIG_PREVIEW_NONE.format(name=self.name))
            return
        if self.view is not None:
            self.view.show_part(preview.shape, preview.color)
            self.view.fit_all()
        self.message.setText(
            text.CONFIG_PREVIEW_FAILED.format(name=self.name, n=preview.failed)
            if preview.failed
            else text.CONFIG_PREVIEW_READY.format(name=self.name)
        )
