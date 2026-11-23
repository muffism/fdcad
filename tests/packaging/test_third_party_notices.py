"""Third party notices, the source offer and what the builds ship (D2860 to D2867)."""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

import pytest
from tools import third_party_notices as tpn

ROOT = Path(__file__).resolve().parents[2]
RECORDED = ROOT / "packaging" / "notices" / "inventory-windows.txt"
SPEC = ROOT / "packaging" / "fdcad.spec"
ISS = ROOT / "packaging" / "windows" / "fdcad.iss"
DMG = ROOT / "packaging" / "macos" / "make_dmg.sh"
DIST = ROOT / "dist" / ("FDCAD.app" if sys.platform == "darwin" else "FDCAD")
PLATFORM = "macos" if sys.platform == "darwin" else "windows"


@pytest.fixture(scope="module")
def notices() -> tpn.Notices:
    return tpn.load()


def test_written_files_are_up_to_date() -> None:
    assert tpn.stale() == [], "run: uv run python tools/third_party_notices.py write"


def test_every_recorded_windows_file_has_a_notice(notices: tpn.Notices) -> None:
    items = tpn.read_inventory(RECORDED)
    assert len(items) > 150
    assert tpn.unmatched(items, notices, "windows") == []


def test_every_windows_component_matches_a_recorded_file(notices: tpn.Notices) -> None:
    """A component whose files are gone from the build is stale."""
    assert tpn.unused(tpn.read_inventory(RECORDED), notices, "windows") == []


@pytest.mark.skipif(not DIST.exists(), reason="no build in dist/: run pyinstaller first")
def test_every_file_of_the_real_build_has_a_notice(notices: tpn.Notices) -> None:
    assert tpn.unmatched(tpn.inventory(DIST), notices, PLATFORM) == []


@pytest.mark.skipif(
    sys.platform != "win32" or not DIST.exists(), reason="needs the Windows folder build"
)
def test_recorded_inventory_matches_the_real_windows_build() -> None:
    """Re-record with the inventory command when the build changes."""
    assert tpn.read_inventory(RECORDED) == tpn.inventory(DIST)


def test_a_new_library_without_a_notice_is_reported(notices: tpn.Notices) -> None:
    items = [*tpn.read_inventory(RECORDED), "newlib.libs/libnew-0123abcd.dll", "extra/"]
    assert tpn.unmatched(items, notices, "windows") == ["newlib.libs/libnew-0123abcd.dll", "extra/"]


def test_inventory_lists_binaries_zips_and_data_folders(tmp_path: Path) -> None:
    files = [
        "FDCAD.exe",
        "_internal/python313.dll",
        "_internal/base_library.zip",
        "_internal/PySide6/Qt6Core.dll",
        "_internal/PySide6/translations/qt_de.qm",
        "_internal/docs/user_guide/README.md",
        "_internal/fdcad/ui/icons/a.svg",
        "_internal/OCP/__init__.py",
        "_internal/OCP/OCP.cp313-win_amd64.pyd",
    ]
    for name in files:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b"x")
    assert tpn.inventory(tmp_path) == [
        "FDCAD.exe",
        "OCP/OCP.cp313-win_amd64.pyd",
        "PySide6/Qt6Core.dll",
        "PySide6/translations/",
        "base_library.zip",
        "docs/",
        "fdcad/",
        "python313.dll",
    ]


def test_inventory_finds_mac_framework_libraries(tmp_path: Path) -> None:
    lib = tmp_path / "Contents/Frameworks/PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore"
    lib.parent.mkdir(parents=True)
    lib.write_bytes(b"x")
    assert tpn.inventory(tmp_path) == ["PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore"]


def test_mac_wheel_files_have_notices(notices: tpn.Notices) -> None:
    """Names from the macOS arm64 wheels on PyPI; no Mac build was listed (D2862)."""
    names = [
        "OCP/OCP.cpython-313-darwin.so",
        "OCP/.dylibs/libTKernel.8.0.1.dylib",
        "OCP/.dylibs/libfreeimage.3.18.0.dylib",
        "OCP/.dylibs/libraw.25.dylib",
        "OCP/.dylibs/libjpegxr.1.1.dylib",
        "OCP/.dylibs/libjxrglue.1.1.dylib",
        "OCP/.dylibs/libfmt.12.2.0.dylib",
        "OCP/.dylibs/libc++.1.0.dylib",
        "OCP/.dylibs/libz.1.3.2.dylib",
        "vtkmodules/.dylibs/libvtkCommonCore-9.6.dylib",
        "PySide6/QtCore.abi3.so",
        "PySide6/libpyside6.abi3.6.12.dylib",
        "PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore",
        "PySide6/Qt/plugins/platforms/libqcocoa.dylib",
        "shiboken6/Shiboken.abi3.so",
        "shiboken6/libshiboken6.abi3.6.12.dylib",
        "numpy/.dylibs/libscipy_openblas64_.dylib",
        "numpy/.dylibs/libquadmath.0.dylib",
        "planegcs/_planegcs.cpython-313-darwin.so",
        "python3.13/lib-dynload/_ssl.cpython-313-darwin.so",
        "FDCAD",
    ]
    assert tpn.unmatched(names, notices, "macos") == []


def test_every_component_has_version_licence_and_text(notices: tpn.Notices) -> None:
    for c in notices.components:
        assert c.version and c.license, c.id
        assert c.copyright, f"{c.id} has no copyright line"
        assert c.texts or c.kind == "self" or c.id == "msvc-runtime", f"{c.id} has no text"


def test_copyleft_components_have_exact_sources(notices: tpn.Notices) -> None:
    offer = (ROOT / tpn.SOURCE_OFFER_FILE).read_text(encoding="utf-8")
    copyleft = {c.id for c in notices.components if c.copyleft}
    assert {"qt", "pyside6", "shiboken6", "occt", "planegcs", "libraw", "freeimage"} <= copyleft
    for c in notices.components:
        choices = c.license.split(" OR ")
        if c.kind != "self" and all("GPL" in x and "exception" not in x for x in choices):
            assert c.copyleft, f"{c.id} is under the GPL or LGPL only"
        if c.copyleft:
            assert c.source, c.id
            assert c.modified, f"{c.id}: say whether FDCAD changed it"
            assert f"### {c.name} {c.version}" in offer
            first = c.source[0]
            assert c.version.replace(".", "_") in first.replace(".", "_") or (
                "version is not recorded" in first
            ), c.id


def test_notices_carry_the_required_credits() -> None:
    text = (ROOT / tpn.NOTICES_FILE).read_text(encoding="utf-8")
    assert "This software is based in part on the work of the Independent JPEG Group." in text
    assert "makes use of facilities provided by the Open CASCADE Technology" in text
    assert "Open CASCADE exception (version 1.0) to GNU LGPL version 2.1." in text
    flat = " ".join(text.split())
    assert "The FreeType Project (www.freetype.org). All rights reserved." in flat
    assert "FDCAD uses it under the GPL 3, the licence FDCAD itself is under." in flat
    assert "FreeImage Public License - Version 1.0" in text
    assert "Copyright (C) 2026 the FDCAD contributors" in text


def test_notices_have_no_dashes_in_our_own_words(notices: tpn.Notices) -> None:
    """CLAUDE.md 8.2 for the text FDCAD writes (licence texts are quoted as they are)."""
    ours = [notices.offer[k] for k in notices.offer]
    for c in notices.components:
        ours += [c.choice, c.modified, c.notes, c.credit, c.version_note]
    for value in ours:
        assert chr(0x2013) not in value and chr(0x2014) not in value, value[:60]
    offer = (ROOT / tpn.SOURCE_OFFER_FILE).read_text(encoding="utf-8")
    assert chr(0x2013) not in offer and chr(0x2014) not in offer


def test_source_offer_gives_a_written_offer_and_relinking() -> None:
    offer = " ".join((ROOT / tpn.SOURCE_OFFER_FILE).read_text(encoding="utf-8").split())
    assert "For at least three years" in offer
    assert "section 6" in offer
    assert "## 3. Replacing the LGPL libraries" in offer
    assert "codesign --force --deep --sign - FDCAD.app" in offer


def test_source_offer_names_a_contact_address() -> None:
    """GPL 3 section 6(b) wants a way to ask for the source that works for anyone (D2870)."""
    offer = " ".join((ROOT / tpn.SOURCE_OFFER_FILE).read_text(encoding="utf-8").split())
    assert "write to FDCAD@proton.me" in offer
    assert "through the person or page you got FDCAD from" not in offer


def test_spec_ships_the_notices_in_data_and_beside_the_exe() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert 'NOTICE_FILES = ["LICENSE", "THIRD_PARTY_NOTICES.txt", "SOURCE_OFFER.md"]' in spec
    assert 'a.datas += [(name, str(ROOT / name), "DATA") for name in NOTICE_FILES]' in spec
    assert spec.count("shutil.copy2(ROOT / name, Path(DISTPATH)") == 2
    assert '"NSHumanReadableCopyright": f"{COPYRIGHT}.' in spec
    assert 'COPYRIGHT = "Copyright (C) 2026 the FDCAD contributors"' in spec


def test_installer_checks_and_installs_the_notices() -> None:
    iss = ISS.read_text(encoding="utf-8")
    for name in ("THIRD_PARTY_NOTICES.txt", "SOURCE_OFFER.md", "LICENSE"):
        assert f'FileExists(AddBackslash(SourcePath) + "..\\..\\dist\\FDCAD\\{name}")' in iss
    assert r'Source: "..\..\dist\FDCAD\*"; DestDir: "{app}"' in iss
    assert r'Filename: "{app}\THIRD_PARTY_NOTICES.txt"' in iss


def test_installer_shows_the_gpl_as_information() -> None:
    iss = ISS.read_text(encoding="utf-8")
    assert r"InfoBeforeFile = ..\..\LICENSE" in iss
    assert re.search(r"^\s*LicenseFile\s*=", iss, re.MULTILINE) is None
    assert "AppCopyright = Copyright (C) 2026 the FDCAD contributors" in iss


def test_dmg_shows_the_notices_beside_the_app() -> None:
    script = DMG.read_text(encoding="utf-8")
    assert "for NAME in LICENSE THIRD_PARTY_NOTICES.txt SOURCE_OFFER.md; do" in script
    assert 'cp "$APP/Contents/Resources/$NAME" "$STAGING/$NAME"' in script


def _dev_only_packages() -> set[str]:
    """Locked packages that only the dev group needs."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    deps = {p["name"]: [d["name"] for d in p.get("dependencies", [])] for p in lock["package"]}
    seen: set[str] = set()
    todo = ["fdcad"]
    while todo:
        name = todo.pop()
        if name not in seen:
            seen.add(name)
            todo += deps.get(name, [])
    return set(deps) - seen


def _top_level_modules(dist_name: str) -> set[str]:
    try:
        files = metadata.distribution(dist_name).files or []
    except metadata.PackageNotFoundError:
        return set()
    tops = {Path(str(f)).parts[0] for f in files}
    names = {t.removesuffix(".py") for t in tops if not t.endswith((".dist-info", ".data"))}
    return {n.split(".")[0] for n in names if n.isidentifier() and n != "__pycache__"}


def test_dev_only_packages_found_by_the_build_are_excluded() -> None:
    dev = _dev_only_packages()
    assert {"pyyaml", "typing-extensions", "pyinstaller", "pytest"} <= dev
    assert not {"numpy", "pyside6-essentials", "cadquery-ocp", "vtk"} & dev
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    excludes = next(
        ast.literal_eval(n.value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "EXCLUDES"
    )
    assert {"yaml", "_yaml", "typing_extensions"} <= set(excludes)
    recorded = tpn.read_inventory(RECORDED)
    for name in dev:
        for module in _top_level_modules(name):
            assert not any(i.split("/")[0] == module for i in recorded), (name, module)


@pytest.mark.skipif(
    not (ROOT / "build" / "fdcad" / "PYZ-00.toc").is_file(), reason="no PyInstaller work folder"
)
def test_the_last_build_bundled_no_dev_only_module() -> None:
    toc = ast.literal_eval((ROOT / "build" / "fdcad" / "PYZ-00.toc").read_text(encoding="utf-8"))
    bundled = {name.split(".")[0] for name, _path, _kind in toc[1]}
    allowed = {"_pyi_rth_utils", "pyi_splash"}  # PyInstaller's own run time modules
    for dist_name in _dev_only_packages():
        found = (_top_level_modules(dist_name) & bundled) - allowed
        assert not found, (dist_name, found)
