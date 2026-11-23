---
name: fdcad-qt-ui
description: Use when building or changing FDCAD user interface in PySide6: windows, panels, command tabs, dialogs, the viewport, themes, icons, shortcuts or UI text. Covers layout, threading, high DPI, naming and UI tests.
---

# FDCAD Qt user interface

Read `PLAN.md` section 8, `SHORTCUTS.md` and `CLAUDE.md` sections 5, 7 and 8 first.

## 1. Layout (PLAN 8)

1. Top: menu bar (File, Edit, View, Insert, Tools, Help) and command tabs (Features, Sketch, later Sheet Metal, Evaluate, Graph).
2. Left panel tabs: feature tree with rollback bar; property panel with OK and Cancel while editing; configurations and variables.
3. Centre: viewport with a small view toolbar, XYZ triad bottom left, confirmation corner (OK and Cancel) top right while editing.
4. Bottom: status bar with sketch status, cursor coordinates and unit selector.
5. Several parts open as document tabs.

## 2. Code rules

1. Code lives in `src/fdcad/ui/<area>` (`main_window`, `viewport`, `tree`, `property_panel`, `command_tabs`, `sketch_tools`, `commands`, `input`, `themes`, `preferences`).
2. Never call OCP on the UI thread. Run kernel work in a worker and return results by signal. Follow `MainWindow.load_test_cube` in `src/fdcad/ui/main_window/window.py` (QRunnable, QThreadPool, signals).
3. Displaying shapes in the viewer happens on the UI thread. Building them does not.
4. Every document change goes through an undoable command in `src/fdcad/ui/commands`.
5. UI code may import `fdcad.core`. Core never imports UI.

## 3. Viewport (`src/fdcad/ui/viewport/widget.py`)

1. OpenCascade draws into a native child window (DECISIONS D59). Qt never paints it.
2. Everything passed to OpenCascade is in device pixels: logical size or position times `devicePixelRatioF()`.
3. Resize and screen changes call `_sync_size`, which resizes the OCCT window and calls `MustBeResized`.
4. Navigation: middle drag rotates, Ctrl and middle drag pans, wheel zooms. Trackpad: two finger drag rotates, Shift and two finger drag pans, pinch zooms.
5. `ZoomAtPoint` scales by 1 + d / 100 for a pointer move of d pixels. Use `_zoom_at` with a factor.
6. On the Qt offscreen platform the viewport is replaced by a placeholder (`viewport_supported`).

## 4. Look and feel

1. Themes: light, dark and follow system. Colours live in `ui/themes/theme.py` (`Palette` for what FDCAD paints, `Chrome` for Qt widgets); the application style sheet is built in `ui/themes/style.py` (D111). Style a widget by giving it an object name and a rule there, not with inline colours.
2. Sketch colours: blue under defined, black fully defined (white in dark theme), red over defined.
3. Icons: original SVG files in `src/fdcad/ui/icons`, listed in `NAMES.md`. Check new ones with `tools/icon_sheet.py`. Never copy or trace icons or screenshots from commercial software.
4. Spacing and sizes in logical pixels, as multiples of `themes.style.unit(font)` (4 at the default font), so they scale with the screen and the UI font. One accent colour, radii `r1` (controls) and `r2` (panels, plates, popups).
5. Error borders on text fields: set the `error` (or `invalid`) property and repolish; never an inline style sheet.
6. Check the look with `tools/screenshot_tabs.py` (offscreen, light and dark, `--scale 2` for 200 percent).

## 5. Text

1. All UI strings live in one module so translation can be added later.
2. Command labels in title case ("Extruded Cut"). Messages in sentence case.
3. Error messages say what failed and what to do next.
4. Plain short sentences. No em dashes or en dashes.
5. Use generic names: feature tree, property panel, command tabs, configurations panel, Hole Tool, shortcut bar, confirmation corner, node editor, transform handles, "Add as Feature".
6. Never use the product names listed in `CLAUDE.md` section 7.1 in UI, code, docs or icons.

## 6. Input (SHORTCUTS.md)

1. Default shortcuts and gestures come from `SHORTCUTS.md`. A shortcut becomes active when its command is built.
2. Everything is customizable in preferences. The editor warns about clashes.
3. On Mac, Ctrl becomes Cmd, except the cases in `SHORTCUTS.md` section 1.2. Never take a Cmd shortcut that macOS reserves (section 9).
4. Selection: hover highlight, filters, box selection, select other.

## 7. Performance (PLAN 11)

1. Window visible in under 2 s. Show it first, load heavy modules after (see `src/fdcad/app.py`).
2. Rate limit hover highlighting and live previews. Cancel superseded work.
3. Never loop over triangles or vertices in Python. Pass whole arrays.

## 8. Tests

1. UI tests use pytest-qt on the Qt offscreen platform (`tests/conftest.py`). CI never needs a GPU.
2. Test behaviour through public methods and status messages, as in `tests/ui/test_main_window.py`.
3. The real viewport is checked by hand. To check rendering locally, call the viewport's `dump(path)` and look at the image.
