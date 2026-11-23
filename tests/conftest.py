"""Test setup: force the Qt offscreen platform so tests never need a GPU.

Tests marked ``slow`` (the long naming stress runs) are skipped unless pytest is
given ``--run-slow`` or the environment sets ``FDCAD_RUN_SLOW=1`` (D431).
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--run-slow", action="store_true", help="also run tests marked slow")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-slow") or os.environ.get("FDCAD_RUN_SLOW") == "1":
        return
    skip = pytest.mark.skip(reason="slow: run with --run-slow or FDCAD_RUN_SLOW=1")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


#: The ``app_version`` the sample parts and test fixtures were saved with (D556).
FIXTURE_APP_VERSION = "0.1.0"


@pytest.fixture(autouse=True)
def _fixture_app_version(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Save files with the fixtures' ``app_version`` so byte for byte checks test the schema.

    ``app_version`` names the FDCAD that last saved a file (FDEF_SPEC 2 item 3), so every
    version bump would otherwise change the saved text of every sample and fixture.
    Tests marked ``real_version`` save with the real ``fdcad.__version__``.
    """
    if request.node.get_closest_marker("real_version") is None:
        from fdcad.core.io import fdef

        monkeypatch.setattr(fdef, "__version__", FIXTURE_APP_VERSION)


@pytest.fixture(autouse=True)
def _no_outside_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never start a slicer, the default app for a file, a file browser or a mail app.

    Without this, a test that runs Open in Slicer hands a real ``.3mf`` to the
    system, which starts the owner's slicer or asks which app to use.
    """
    from fdcad.core.printing import slicer

    real_launch = slicer.launch

    def quiet_launch(file, program, platform=slicer.sys.platform, popen=None, startfile=None):  # type: ignore[no-untyped-def]
        return real_launch(
            file,
            program,
            platform,
            popen=popen or (lambda *_a, **_k: None),
            startfile=startfile or (lambda _p: None),
        )

    monkeypatch.setattr(slicer, "launch", quiet_launch)
    monkeypatch.setattr(os, "startfile", lambda *_a, **_k: None, raising=False)
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda _url: True))
    from fdcad.ui.help import report

    # Report Problem (D2871) never starts the owner's mail app from a test.
    monkeypatch.setattr(report, "open_mail", lambda _url: True)


@pytest.fixture(autouse=True)
def _mesh_export_options_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The STL and 3MF options dialog (TR182, D776) is accepted with what it shows, so
    tests that export never wait for a click. Tests of the dialog set their own."""
    from fdcad.ui.main_window import mesh_export_dialog

    monkeypatch.setattr(mesh_export_dialog, "run", lambda _dialog: True)
    from fdcad.ui.main_window import body_pick_dialog, step_export_dialog

    # TR302 (D1202, D1203): the STEP options and Pick Bodies are accepted as shown too.
    monkeypatch.setattr(step_export_dialog, "run", lambda _dialog: True)
    monkeypatch.setattr(body_pick_dialog, "run", lambda _dialog: True)
    from fdcad.ui.print_tools import section_export

    monkeypatch.setattr(section_export, "run", lambda _dialog: True)  # TR300 (D1204)
    from fdcad.ui.main_window import body_settings_dialog

    monkeypatch.setattr(body_settings_dialog, "run", lambda _dialog: True)  # TR383 (D1207)
    from fdcad.ui.print_tools import heights_tool

    monkeypatch.setattr(heights_tool, "run", lambda _dialog: True)  # TR384 (D1208)
    from fdcad.ui.print_tools import arrange_tool

    monkeypatch.setattr(arrange_tool, "run", lambda _dialog: True)  # TR301 (D1210)
    from fdcad.ui.print_tools import islands_tool

    monkeypatch.setattr(islands_tool, "ask", lambda *_a: "")  # TR409 (D1213)
    from fdcad.ui.sketch_tools import code_tag_dialog

    monkeypatch.setattr(code_tag_dialog, "run", lambda _dialog: False)  # TR311 (D1215)
    from fdcad.ui.print_tools import calibration_tool

    monkeypatch.setattr(calibration_tool, "run", lambda _dialog: False)  # TR358 (D2000)


@pytest.fixture(autouse=True)
def _no_system_reduce_motion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never follow the machine's reduce motion setting (TR294, D975)."""
    from fdcad.ui.themes import motion

    monkeypatch.setattr(motion, "system_reduce_motion", lambda platform=None: False)


@pytest.fixture(autouse=True)
def _session_toggles_reset() -> object:
    """Display toggles kept on a class for the whole session (TR235 Show Formulas) and
    the pick size scale (TR313) go back to their defaults after each test."""
    import sys

    yield
    canvas = sys.modules.get("fdcad.ui.sketch_tools.canvas")
    if canvas is not None:
        canvas.SketchCanvas.show_formulas = False
        canvas.SketchCanvas.shade_regions = False  # TR335
        canvas.SketchCanvas.show_points = True
        canvas.SketchCanvas.mark_open_ends = True  # TR341
        canvas.SketchCanvas.mark_crossings = True  # TR238
        canvas.SketchCanvas.hidden_tags = frozenset()
        canvas.SketchCanvas.show_driving = True
        canvas.SketchCanvas.show_reference = True
        canvas.SketchCanvas.tag_scale = 1.0
        canvas.SketchCanvas.line_scale = 1.0  # TR341 (D1013)
        canvas.SketchCanvas.reference_mode = False  # TR111
    picks = sys.modules.get("fdcad.ui.input.pick_size")
    if picks is not None:
        picks.set_size("normal")
    numbers = sys.modules.get("fdcad.core.units.number_display")
    if numbers is not None:
        numbers.set_style(None)  # TR350: shown numbers in the default style


@pytest.fixture(autouse=True)
def _private_panel_prefs(tmp_path_factory: pytest.TempPathFactory) -> object:
    """Panel favourites and start presets (TR326, D947) use a store of the test's own,
    so a preset the owner chose in FDCAD never changes what a test's new feature starts
    with. Tests that set their own store keep it."""
    from PySide6.QtCore import QSettings

    from fdcad.ui.preferences import phase4_settings as prefs
    from fdcad.ui.preferences.settings import Settings

    if prefs.OVERRIDE is not None:
        yield
        return
    path = tmp_path_factory.mktemp("prefs") / "prefs.ini"
    prefs.OVERRIDE = Settings(QSettings(str(path), QSettings.Format.IniFormat))
    yield
    prefs.OVERRIDE = None
