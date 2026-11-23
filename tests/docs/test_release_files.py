"""Release preparation checks for v1.0 (D556, D557, D558)."""

from __future__ import annotations

import re
import struct
import tomllib
from pathlib import Path

import pytest
from tools.set_version import set_version

from fdcad import __version__

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / "packaging" / "icons"
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_version_is_the_same_in_both_places() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == __version__


def test_a_release_version_has_its_change_log_section() -> None:
    """A development version may be anything; a release version needs a dated section
    at the top of the change log, which the release workflow reads for its notes."""
    if ".dev" in __version__:
        return
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    first = next(line for line in changelog.splitlines() if line.startswith("## ["))
    assert first.startswith(f"## [{__version__}] - 20"), first


def test_set_version_writes_both_places(tmp_path: Path) -> None:
    (tmp_path / "src" / "fdcad").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    (tmp_path / "src/fdcad/__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    set_version("1.0.0", tmp_path)
    assert 'version = "1.0.0"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"1.0.0"' in (tmp_path / "src/fdcad/__init__.py").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="is not a version"):
        set_version("v1", tmp_path)


def test_release_workflow_refuses_a_tag_that_does_not_match() -> None:
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert text.count('if [[ "$V" != "$APP" ]]') == 2


@pytest.mark.parametrize("size", PNG_SIZES)
def test_app_icon_png_at_every_size(size: int) -> None:
    data = (ICONS / "png" / f"fdcad_{size}.png").read_bytes()
    assert _png_size(data) == (size, size)


def test_windows_icon_holds_16_to_256() -> None:
    data = (ICONS / "fdcad.ico").read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1)
    sizes = []
    for k in range(count):
        width, _h, _c, _r, _p, _b, length, offset = struct.unpack(
            "<BBBBHHII", data[6 + 16 * k : 22 + 16 * k]
        )
        side = width or 256
        assert _png_size(data[offset : offset + length]) == (side, side)
        sizes.append(side)
    assert sizes == [16, 24, 32, 48, 64, 128, 256]


def test_mac_icon_holds_16_to_1024_with_retina_sizes() -> None:
    data = (ICONS / "fdcad.icns").read_bytes()
    assert data[:4] == b"icns"
    assert struct.unpack(">I", data[4:8])[0] == len(data)
    kinds = {}
    pos = 8
    while pos < len(data):
        kind = data[pos : pos + 4].decode("ascii")
        length = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        kinds[kind] = _png_size(data[pos + 8 : pos + length])[0]
        pos += length
    assert kinds == {
        "icp4": 16,
        "icp5": 32,
        "icp6": 64,
        "ic07": 128,
        "ic08": 256,
        "ic09": 512,
        "ic10": 1024,
        "ic11": 32,
        "ic12": 64,
        "ic13": 256,
        "ic14": 512,
    }


def test_app_icon_svg_is_shipped_in_the_package() -> None:
    from fdcad.ui.help.paths import app_icon_path

    assert app_icon_path().is_file()
    assert app_icon_path().read_text(encoding="utf-8").startswith("<svg")


def test_spec_uses_the_icons_and_a_numeric_mac_version() -> None:
    spec = (ROOT / "packaging" / "fdcad.spec").read_text(encoding="utf-8")
    assert 'icon=str(ICONS_OUT / "fdcad.ico")' in spec
    assert 'icon=str(ICONS_OUT / "fdcad.icns")' in spec
    assert '"CFBundleShortVersionString": BUNDLE_VERSION' in spec
    assert "fdcad/ui/app_icon.svg" in spec
    match = re.match(r"\d+(\.\d+){0,2}", __version__)
    assert match is not None and match.group(0) == "1.0.0"


def test_windows_installer_has_the_release_items() -> None:
    iss = (ROOT / "packaging" / "windows" / "fdcad.iss").read_text(encoding="utf-8")
    for needed in (
        "AppPublisher = ",
        r"SetupIconFile = ..\icons\fdcad.ico",
        r"UninstallDisplayIcon = {app}\FDCAD.exe",
        r'Name: "{group}\FDCAD"',  # Start menu
        r'Name: "{group}\{cm:UninstallProgram,FDCAD}"',  # uninstaller in the Start menu
        r'Subkey: "Software\Classes\.fdprt"',  # file association
        r'Subkey: "Software\Classes\.fdef"',  # older part files still open
        r"FDCAD.Part\DefaultIcon",
        "ChangesAssociations = yes",
        "ArchitecturesAllowed = x64compatible",
        r"InfoBeforeFile = ..\..\LICENSE",  # the GPL as information, not to accept (D2867)
    ):
        assert needed in iss, needed
    icon = iss.split("SetupIconFile = ")[1].split()[0].replace("\\", "/")
    assert (ROOT / "packaging" / "windows" / icon).resolve().exists()


def test_mac_dmg_script_signs_and_verifies() -> None:
    script = (ROOT / "packaging" / "macos" / "make_dmg.sh").read_text(encoding="utf-8")
    assert "codesign --force --deep --sign -" in script
    assert "codesign --verify" in script
    assert "macos-arm64.dmg" in script


@pytest.mark.real_version
def test_saving_writes_the_real_app_version() -> None:
    from fdcad.core.document.model import Document
    from fdcad.core.io import fdef

    text = fdef.dumps(Document())
    assert f'"app_version": "{__version__}"' in text


def test_spec_ships_the_graph_samples_the_guide_opens() -> None:
    # The node editor guide and the attractor plate tutorial open samples from the
    # graphs folder, which the installed app did not have (round 10e, D636).
    spec = (ROOT / "packaging" / "fdcad.spec").read_text(encoding="utf-8")
    assert 'f"samples/graphs/{p.name}"' in spec
    assert any((ROOT / "samples" / "graphs").glob("*.fdprt"))
