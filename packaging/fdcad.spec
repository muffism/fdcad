# PyInstaller spec for FDCAD. One folder build (DECISIONS D43).
# With FDCAD_ONEFILE=1 in the environment: one portable FDCAD-portable.exe in dist/
# instead (Windows, D1033). It unpacks on every start, so it starts slower.
# Build from the repo root: uv run pyinstaller packaging/fdcad.spec --noconfirm
# Output: dist/FDCAD/ on Windows, dist/FDCAD.app on macOS.

import os
import re
import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))
from fdcad import __version__  # noqa: E402

# macOS wants plain numbers in the bundle version: "1.0.0.dev0" gives "1.0.0" (D556).
BUNDLE_VERSION = re.match(r"\d+(\.\d+){0,2}", __version__).group(0)
# The app icon at every size, made by tools/make_app_icon.py (D557).
ICONS_OUT = ROOT / "packaging" / "icons"

# OCP and VTK are only linked for OCP's optional VTK bridge, which FDCAD never uses.
EXCLUDES = [
    "vtk",
    "vtkmodules",
    "matplotlib",
    "tkinter",
    "PIL",
    "OCP.IVtkVTK",
    "OCP.IVtkTools",
    "OCP.IVtkOCC",
    "OCP.IVtk",
    # Development only packages that numpy finds when they are installed (D2865):
    # PyYAML (numpy.__config__ asks for it in a try) and typing_extensions (type stubs).
    "yaml",
    "_yaml",
    "typing_extensions",
]
# FDCAD's own name in the app's version and copyright fields (D2866).
COPYRIGHT = "Copyright (C) 2026 the FDCAD contributors"
# The notices and source offer, written by tools/third_party_notices.py (D2860).
NOTICE_FILES = ["LICENSE", "THIRD_PARTY_NOTICES.txt", "SOURCE_OFFER.md"]

if sys.platform == "win32":
    # Find Python's own DLLs first (D2864). PyInstaller looks for the DLLs a module
    # needs on PATH, so a build started from Git Bash took OpenSSL from Git's folder.
    os.environ["PATH"] = os.pathsep.join(
        [str(Path(sys.base_prefix)), str(Path(sys.base_prefix) / "DLLs"), os.environ["PATH"]]
    )

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    hiddenimports=collect_submodules("fdcad"),
    excludes=EXCLUDES,
    noarchive=False,
)
if sys.platform == "win32":
    # Every DLL must come from the project or the Python install, never from a
    # folder that happens to be on PATH (D2864).
    allowed = [ROOT.resolve(), Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()]
    strays = [
        src
        for _name, src, _kind in a.binaries
        if not any(Path(src).resolve().is_relative_to(base) for base in allowed)
    ]
    assert not strays, f"DLLs from outside the project and Python: {strays}"
# Ship the license texts, the notices and the source offer with the app (D2860).
# In the folder build they are also copied beside FDCAD.exe, below.
a.datas += [(name, str(ROOT / name), "DATA") for name in NOTICE_FILES]
a.datas += [
    ("CHANGELOG.md", str(ROOT / "CHANGELOG.md"), "DATA"),  # What's New (TR291, D2018)
    ("licenses/LGPL-2.1.txt", str(ROOT / "packaging" / "licenses" / "LGPL-2.1.txt"), "DATA"),
    ("licenses/LGPL-3.0.txt", str(ROOT / "packaging" / "licenses" / "LGPL-3.0.txt"), "DATA"),
]
# The user guide, opened from Help, Open User Guide (D551). The app reads it from
# docs/user_guide next to its other data files (fdcad/ui/help/paths.py).
GUIDE = ROOT / "docs" / "user_guide"
GUIDE_FILES = sorted(p for p in GUIDE.rglob("*.md"))
assert any(p.name == "README.md" for p in GUIDE_FILES), "no user guide found"
a.datas += [(f"docs/user_guide/{p.relative_to(GUIDE).as_posix()}", str(p), "DATA") for p in GUIDE_FILES]
# The window icon, drawn from the SVG at run time.
a.datas += [("fdcad/ui/app_icon.svg", str(ROOT / "src" / "fdcad" / "ui" / "app_icon.svg"), "DATA")]
# The bolder drawing used at 16 to 32 px (D672).
a.datas += [("fdcad/ui/app_icon_small.svg", str(ROOT / "src" / "fdcad" / "ui" / "app_icon_small.svg"), "DATA")]
# Sample parts, opened from File, Open Sample.
a.datas += [(f"samples/{p.name}", str(p), "DATA") for p in sorted((ROOT / "samples").glob("*.fdprt"))]
# The node editor samples, opened from the graphs folder inside the samples folder
# (user guide, Node editor and the attractor plate tutorial; D636).
GRAPHS = sorted((ROOT / "samples" / "graphs").glob("*.fdprt"))
assert GRAPHS, "no graph samples found"
a.datas += [(f"samples/graphs/{p.name}", str(p), "DATA") for p in GRAPHS]
# The icon set (PHASE1_CORRECTIONS C5): every SVG plus NAMES.md, and any other data file
# added to the folder later. The loader finds them next to fdcad/ui/icons/__init__.py.
# Theme images are written at start (DECISIONS D111 item 7), so no theme folder is needed,
# but they and the icons need Qt's SVG image plugin, which the PySide6 hooks bundle.
ICONS = ROOT / "src" / "fdcad" / "ui" / "icons"
ICON_FILES = sorted(p for p in ICONS.iterdir() if p.is_file() and p.suffix not in (".py", ".pyc"))
assert any(p.suffix == ".svg" for p in ICON_FILES), "no icons found"
a.datas += [(f"fdcad/ui/icons/{p.name}", str(p), "DATA") for p in ICON_FILES]
pyz = PYZ(a.pure)

ONEFILE = os.environ.get("FDCAD_ONEFILE") == "1" and sys.platform == "win32"
if ONEFILE:
    # The single file unpacks for some seconds before Python starts. The boot loader
    # shows the start picture meanwhile (D1034); the app closes it when its own is up.
    boot = Splash(
        str(ROOT / "packaging" / "splash.png"),
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
    )
    # "portable" in the name turns portable mode on (fdcad/portable.py).
    exe = EXE(
        pyz,
        a.scripts,
        boot,
        boot.binaries,
        a.binaries,
        a.datas,
        [],
        name="FDCAD-portable",
        console=False,
        icon=str(ICONS_OUT / "fdcad.ico"),
        upx=False,
        argv_emulation=False,
    )
    # Beside the portable file too, so they can go out with it (D2867).
    for name in NOTICE_FILES:
        shutil.copy2(ROOT / name, Path(DISTPATH) / name)
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="FDCAD",
        console=False,
        icon=str(ICONS_OUT / "fdcad.ico"),
        upx=False,
        argv_emulation=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="FDCAD", upx=False)
    if sys.platform == "win32":
        # Beside FDCAD.exe, where the installer and the folder zip carry them (D2867).
        for name in NOTICE_FILES:
            shutil.copy2(ROOT / name, Path(DISTPATH) / "FDCAD" / name)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="FDCAD.app",
        bundle_identifier="org.fdcad.FDCAD",
        icon=str(ICONS_OUT / "fdcad.icns"),
        version=BUNDLE_VERSION,
        info_plist={
            "CFBundleName": "FDCAD",
            "CFBundleDisplayName": "FDCAD",
            "CFBundleShortVersionString": BUNDLE_VERSION,
            "CFBundleVersion": BUNDLE_VERSION,
            "NSHumanReadableCopyright": f"{COPYRIGHT}. Free software under the GNU GPL v3 or later.",
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "FDCAD Part",
                    "CFBundleTypeRole": "Editor",
                    "CFBundleTypeIconFile": "fdcad.icns",
                    "LSHandlerRank": "Owner",
                    "LSItemContentTypes": ["org.fdcad.part"],
                }
            ],
            "UTExportedTypeDeclarations": [
                {
                    "UTTypeIdentifier": "org.fdcad.part",
                    "UTTypeDescription": "FDCAD Part",
                    "UTTypeConformsTo": ["public.json", "public.data"],
                    "UTTypeTagSpecification": {
                        "public.filename-extension": ["fdprt", "fdef"],
                        "public.mime-type": ["application/vnd.fdcad.part+json"],
                    },
                }
            ],
        },
    )
