# FDCAD source offer

FDCAD is free software under the GNU General Public License, version 3 or later (GPL v3). Some of the components bundled with it are under the GNU GPL or the GNU Lesser General Public License (LGPL). Those licences give you the right to the source code. This file says where to get it.

This file is written by `tools/third_party_notices.py` from `packaging/notices`.

## 1. FDCAD's own source

FDCAD's source code, with the build files used to make the installers (`packaging/fdcad.spec`, `packaging/windows/fdcad.iss`, `packaging/macos/make_dmg.sh` and `.github/workflows/release.yml`), is kept in the repository https://github.com/muffism/fdcad. Each release is the commit tagged with its version, for example `v1.0.0`. The repository is private for now, so it cannot be downloaded yet. Until it is public, the written offer below applies.

### Written offer

For at least three years after the last copy of this FDCAD version is given out, the FDCAD maintainers will give anyone who has a copy of FDCAD's object code a complete copy of the Corresponding Source of that version, as the GNU GPL version 3, section 6, defines it. That is FDCAD's source and build files, and the source of every GPL and LGPL component listed in part 2 of this file, in the exact versions shipped. You get it as a download, or on a physical medium for no more than the cost of making and sending it. To ask for it, write to FDCAD@proton.me, naming the FDCAD version (Help, About FDCAD shows it). This offer is valid for anyone who has the object code, not only the person who first got it.

## 2. The GPL and LGPL components

FDCAD made no changes to any component below. Each is shipped as the party named built it from the project's release. Where that builder applied patches or its own build files, the entry says so, and those patches and build files are part of the source it names.

### Qt 6.12.0

- Licence: LGPL-3.0-only
- Licence that applies: Qt is offered under the LGPL 3, the GPL 2, the GPL 3 or a commercial licence. FDCAD uses it under the LGPL 3.
- Shipped on: Windows and macOS
- Files: `PySide6/Qt6*.dll`, `PySide6/plugins/*`, `PySide6/translations/`, `PySide6/Qt/lib/*`, `PySide6/Qt/plugins/*`, `PySide6/Qt/translations/`
- Source: https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtbase-everywhere-src-6.12.0.tar.xz (Core, Gui, Widgets, Network and the platform, style, TLS, network and image plugins)
- Source: https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtsvg-everywhere-src-6.12.0.tar.xz (Svg and the SVG plugins)
- Source: https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtimageformats-everywhere-src-6.12.0.tar.xz (ICNS, TGA, TIFF, WBMP and WebP plugins)
- Source: https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qttranslations-everywhere-src-6.12.0.tar.xz (translations)
- Changes: No. The Qt files are those of the PySide6-Essentials 6.12.0 wheel, built by The Qt Company from the Qt 6.12.0 release.
- Notice: THIRD_PARTY_NOTICES.txt, entry 4

### Qt for Python (PySide6-Essentials) 6.12.0

- Licence: LGPL-3.0-only
- Licence that applies: PySide6 is offered under the LGPL 3, the GPL 2, the GPL 3 or a commercial licence. FDCAD uses it under the LGPL 3. The wheel carries only Qt's commercial licence stub, so this entry gives the LGPL terms.
- Shipped on: Windows and macOS
- Files: `PySide6/Qt*.pyd`, `PySide6/pyside6*.dll`, `PySide6/Qt*.so`, `PySide6/libpyside6*.dylib`
- Source: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz
- Changes: No. The files are those of the PyPI wheel pyside6-essentials 6.12.0.
- Notice: THIRD_PARTY_NOTICES.txt, entry 5

### Shiboken6 (Qt for Python binding runtime) 6.12.0

- Licence: LGPL-3.0-only
- Licence that applies: Offered under the LGPL 3, the GPL 2, the GPL 3 or a commercial licence. FDCAD uses it under the LGPL 3.
- Shipped on: Windows and macOS
- Files: `shiboken6/Shiboken*`, `shiboken6/shiboken6*.dll`, `shiboken6/libshiboken6*.dylib`
- Source: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz (folder sources/shiboken6)
- Changes: No. The files are those of the PyPI wheel shiboken6 6.12.0.
- Notice: THIRD_PARTY_NOTICES.txt, entry 6

### Open CASCADE Technology (OCCT) 8.0.1

- Licence: LGPL-2.1-only WITH OCCT-exception-1.0
- Shipped on: Windows and macOS
- Files: `cadquery_ocp.libs/TK*`, `OCP/__dot__dylibs/libTK*`, `*/libTK*.dylib`
- Source: https://github.com/Open-Cascade-SAS/OCCT/archive/refs/tags/V8_0_1.tar.gz
- Source: Build files and the one patch: https://github.com/CadQuery/ocp-build-system/tree/v8.0.1.1.0 (patches/occt-8.0.1 and .github/actions/build-occt-sdk)
- Changes: Not by FDCAD. The OCP wheel builders compiled the V8_0_1 tag with one patch, switch-vtk-freetype-cmake-order.patch, which moves the FreeType section after the VTK section in CMakeLists.txt, and on Windows they add VTK link libraries to src/Visualization/TKIVtk/EXTERNLIB.cmake. Both are build files: no OCCT source code is changed. Checked in ocp-build-system at tag v8.0.1.1.0 (D2863).
- Notice: THIRD_PARTY_NOTICES.txt, entry 8.1

### FreeImage 3.18.0

- Licence: GPL-3.0-only
- Licence that applies: FreeImage is offered under the GPL 2, the GPL 3 or the FreeImage Public License (FIPL). FDCAD uses it under the GPL 3, the licence FDCAD itself is under. The FIPL is based on the Mozilla Public License 1.1, which the Free Software Foundation lists as incompatible with the GNU GPL, so FDCAD does not use the FIPL. Its text is included because it is part of FreeImage's own licence notice (D2863).
- Shipped on: Windows and macOS
- Files: `cadquery_ocp.libs/FreeImage-*`, `OCP/__dot__dylibs/libfreeimage*`
- Source: https://downloads.sourceforge.net/project/freeimage/Source%20Distribution/3.18.0/FreeImage3180.zip (sha256 f41379682f9ada94ea7b34fe86bf9ee00935a3147be41b6569c9605a53e438fd)
- Source: conda-forge recipe and patches for build 25: https://github.com/conda-forge/freeimage-feedstock/tree/436a9750733f67540340dcc9583d5f1e1912abf9/recipe
- Source: Built package, Windows: https://anaconda.org/conda-forge/freeimage/3.18.0/download/win-64/freeimage-3.18.0-h81f0cfa_25.conda
- Source: Built package, macOS: https://anaconda.org/conda-forge/freeimage/3.18.0/download/osx-arm64/freeimage-3.18.0-h87663b4_25.conda (the build that takes the OpenEXR 3.4.15 of the macOS wheel)
- Changes: Not by FDCAD. conda-forge built it from the 3.18.0 source with its own CMake files and patches (fix_libraw_0_20, fix_libraw_0_21, libtiff44, Use-system-libs, Fix-compatibility-with-system-libpng, CVE-2019-12211-13, freeimage-openexr3, remove_auto_ptr), which make it use the separate image libraries listed here. Those patches are in the recipe named above.
- Notice: THIRD_PARTY_NOTICES.txt, entry 8.2

### LibRaw 0.22.2

- Licence: LGPL-2.1-only
- Licence that applies: LibRaw is offered under the LGPL 2.1 or the CDDL 1.0. FDCAD uses it under the LGPL 2.1, which is compatible with the GPL; the CDDL is not.
- Shipped on: Windows and macOS
- Files: `cadquery_ocp.libs/raw-*`, `OCP/__dot__dylibs/libraw*`
- Source: https://github.com/LibRaw/LibRaw/archive/0.22.2.tar.gz (sha256 627928088300ecde6ca91ffd202e189203f04ad61ad12f0fe9dc57b9a7a0fb3c)
- Source: Build files: https://github.com/LibRaw/LibRaw-cmake/archive/eb98e4325aef2ce85d2eb031c2ff18640ca616d3.tar.gz and https://github.com/conda-forge/libraw-feedstock/tree/0fd90be48b382a2ae44ca5f9883f559c02c71dd0/recipe
- Changes: Not by FDCAD. conda-forge built the 0.22.2 source unchanged, with the LibRaw-cmake build files; its recipe applies no patches.
- Notice: THIRD_PARTY_NOTICES.txt, entry 8.3

### planegcs (the PlaneGCS sketch solver from FreeCAD) 0.9.6

- Licence: LGPL-2.1-or-later
- Shipped on: Windows and macOS
- Files: `planegcs/_planegcs*`
- Source: https://github.com/spookylukey/planegcs/archive/refs/tags/v0.9.6.tar.gz
- Source: https://pypi.org/project/planegcs/0.9.6/#files (sdist)
- Changes: Not by FDCAD. planegcs takes the PlaneGCS solver files from FreeCAD's Sketcher module and adds small shims and Python bindings; those changes are in its source. Windows: the PyPI wheel. macOS: FDCAD's release workflow compiles the same 0.9.6 source, unchanged (CLAUDE.md 9.2).
- Notice: THIRD_PARTY_NOTICES.txt, entry 10

### libquadmath (GCC) not recorded

- Licence: LGPL-2.1-or-later
- Shipped on: macOS
- Files: `numpy/__dot__dylibs/libquadmath*`
- Source: https://gcc.gnu.org/git/?p=gcc.git;a=tree;f=libquadmath (the GCC version is not recorded; see the numpy 2.5.4 macOS wheel and https://github.com/MacPython/openblas-libs)
- Changes: No. The file is that of the numpy 2.5.4 macOS arm64 wheel.
- Notice: THIRD_PARTY_NOTICES.txt, entry 11.3

## 3. Replacing the LGPL libraries

FDCAD loads every LGPL library as a separate shared library file, so you can replace it with your own build of the same library, made from the source named above or from a modified version of it.

1. Windows, installed or from the folder zip: the Qt libraries are `_internal/PySide6/Qt6*.dll` and the Qt plugins are in `_internal/PySide6/plugins`. PySide6 is `_internal/PySide6/*.pyd` and `pyside6.abi3.dll`, shiboken6 is in `_internal/shiboken6`. Open CASCADE is `_internal/cadquery_ocp.libs/TK*.dll`, LibRaw is `raw-*.dll` and FreeImage is `FreeImage-*.dll` in the same folder. planegcs is `_internal/planegcs/_planegcs*.pyd`. Replace a file with your build of the same version and the same programming interface, keeping its file name (the names with a code after the dash were given by the wheel tool `delvewheel`, and the other libraries look for exactly those names).
2. macOS: the same files are inside `FDCAD.app/Contents/Frameworks` (Qt in `PySide6/Qt/lib`, Open CASCADE, FreeImage and LibRaw in `OCP/__dot__dylibs`, which PyInstaller names so in place of the wheel's `OCP/.dylibs`). After replacing a file, sign the app again with `codesign --force --deep --sign - FDCAD.app`, or macOS will not start it.
3. The portable one file `FDCAD-portable.exe` unpacks itself to a temporary folder at every start, so its libraries cannot be swapped in place. Use the installer or the folder zip, or build FDCAD from its source with your own libraries: `uv sync`, put your libraries in place of the ones in `.venv`, then `uv run pyinstaller packaging/fdcad.spec --noconfirm`.

Python libraries and data stay readable: no FDCAD file is encrypted or locked to a library version beyond its normal programming interface.

## 4. Where these files are

Windows: `THIRD_PARTY_NOTICES.txt`, `SOURCE_OFFER.md` and `LICENSE` are beside `FDCAD.exe` in the install folder and in the folder zip, and in Help, About FDCAD, Licenses. macOS: they are in `FDCAD.app/Contents/Resources`, beside the app on the disk image, and in Help, About FDCAD, Licenses.

FDCAD 1.0.0.dev0. Copyright (C) 2026 the FDCAD contributors.
