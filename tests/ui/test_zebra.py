"""Zebra stripes (TR18, D754)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.command_tabs.tabs import EVALUATE_GROUPS
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.main_window.zebra import DEFAULT_COUNT, stripe_rows
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


class _View:
    def __init__(self) -> None:
        self.textures: list[object] = []

    def set_zebra(self, texture: object) -> None:
        self.textures.append(texture)


def test_command_icon_and_tab() -> None:
    from fdcad.ui.icons.audit import audit

    command = BY_ID["evaluate.zebra"]
    assert command.label == "Zebra Stripes" and command.keys == ()
    assert command.group == "Evaluate"
    assert audit("evaluate.zebra") == []
    listed = [
        c for _g, big, small in EVALUATE_GROUPS for c in [*big, *(x for s in small for x in s)]
    ]
    assert "evaluate.zebra" in listed


def test_stripe_pattern() -> None:
    rows = stripe_rows(4, vertical=True, size=16)
    assert rows[0] == [True, True, False, False] * 4 and rows[0] == rows[15]
    across = stripe_rows(4, vertical=False, size=16)
    assert [r[0] for r in across] == [True, True, False, False] * 4
    assert across[0] == [True] * 16


def test_toggle_shows_stripes_on_the_current_part_only(qtbot: QtBot, window: MainWindow) -> None:
    first, _e = _open_plate(qtbot, window)
    second, _e2 = _open_plate(qtbot, window)
    a, b = _View(), _View()
    first.viewport, second.viewport = a, b  # type: ignore[assignment]
    zebra = window.zebra
    assert window.commands.trigger("evaluate.zebra")
    assert zebra.on and zebra.panel.isVisible()
    assert zebra.count.value() == DEFAULT_COUNT
    assert b.textures[-1] is not None and a.textures[-1] is None  # the second tab is current
    window.tabs.setCurrentWidget(first)
    assert a.textures[-1] is not None and b.textures[-1] is None
    zebra.count.setValue(20)  # a new setting makes a new texture
    assert len(a.textures) >= 2 and a.textures[-1] is not a.textures[-2]
    assert window.commands.trigger("evaluate.zebra")
    assert not zebra.on and a.textures[-1] is None and b.textures[-1] is None
    assert not first.session.is_dirty  # display only


def test_the_kernel_view_takes_the_stripes(qtbot: QtBot) -> None:
    """With the kernel's view (skipped offscreen): the texture goes on and off again."""
    from fdcad.ui.main_window.zebra import stripe_texture
    from tests.ui.test_view_centre import _view

    view = _view(qtbot)
    view.set_zebra(stripe_texture(8, True))
    assert view._view.TextureEnv() is not None
    view.set_zebra(None)
    assert view._view.TextureEnv() is None
