# UI polish spec (U1 to U11)

Owner request of 2026-10-31: design FDCAD the way a top product team would, and fix every small detail in colours, UI, icons, contrast, design and debugging, so it "looks like a million bucks". This spec is FDCAD's own design rules (CLAUDE.md sections 7 and 10). It does not copy any other program. Every colour, icon and layout stays original.

The manager measured the current themes on 2026-10-31 (WCAG contrast formula). The numbers are listed under each rule so the fix can be checked.

## U1. Colour and contrast

1. Text meets 4.5:1 on every background it can sit on, in all four themes (Light, Beige, Dark, Stealth). That includes hover, selected and pressed fills, tooltips and disabled-looking but readable captions. Known misses:
   - accent text on surface: Light 4.48, Beige 4.39
   - Dark: muted on selected 4.02, accent on raised 4.06
2. The outline of an input (text field, drop down, check box, spin box, slider groove) meets 3:1 against the colour around it. Today `border_strong` is 1.84 to 2.42 and `border` is 1.33 to 1.70 in every theme. Keep `border` for quiet dividers. Inputs use a new `input_border` token that passes 3:1.
3. Edges of the model always read against the view background. Today `edge` is black in Dark (1.32 to 2.32) and Stealth (1.00 to 1.25), so edges vanish. In dark themes, edges are lighter than the shaded faces and darker than the background top. They must reach at least 3:1 against both ends of the view gradient, and stay visible against a mid-grey face.
4. Selection and pre-selection (hover highlight) read at 3:1 or more on both ends of the view gradient and on a mid-grey face. Today selection orange on the Light background bottom is 1.67, and 2.08 on Beige. Pre-selection and selection are two clearly different colours. Neither is the accent blue used for sketches, and neither depends on colour alone: a selected edge is also drawn thicker.
5. View state colours (ok, warning and error) pass 3:1 on the view background and 4.5:1 when used as text in the tree or panels. Today Light has ok 2.95, warning 2.86 and accent 2.76 on the background bottom.
6. Every colour comes from a theme token. No hex colour is written in a widget file, except user-chosen data (appearance swatches, a part's saved colours). Move the rest (the node editor, print tools, equations dialog, filter cursor, view bar, sketch canvas, viewport) into `Palette` or `Chrome`.
7. A test computes the contrast of every text, input and view pair above for every theme and fails under the limits. It reuses one helper.
8. The four themes feel like one family: the same accent hue, the same state hues, and the same steps between `window`, `surface` and `raised`. Dark themes are not pure black except Stealth's window.

## U2. Type and spacing

1. One type scale for the whole app, from the system UI font:
   - captions and units: 11 px
   - body, labels and tree: 13 px
   - panel and group titles: 13 px semibold
   - dialog titles: 15 px semibold
   No widget picks its own font size outside these.
2. Spacing on a 4 px grid: 4, 8, 12, 16, 24. Panels use 12 px padding, rows 8 px apart, and groups 16 px apart. Fix any form row, dialog or panel that uses odd gaps.
3. Labels line up. In a form, labels share one column and fields share one left edge. Units sit in the same place in every value field.
4. Numbers in value fields and the status bar use tabular figures where the font offers them, so values don't jump while typing or dragging.
5. Text never clips or sits under another widget at 100, 125, 150 and 200 percent display scaling.

## U3. Control states

1. Every interactive control has distinct normal, hover, pressed, focused, disabled and (where it applies) checked or selected looks. Hover changes the fill a little. Pressed changes it more. Checked uses the accent. Disabled lowers contrast but stays readable at 3:1 or more.
2. One corner radius for buttons and fields (4 px), one for panels and menus (6 px), and 0 for the 3D view.
3. Every button, field and list row is at least 24 px tall, and 28 px for main buttons. Hit areas of small icon buttons are at least 24 by 24 px, even if the icon is 16 px.
4. Menus have the same item height, icon column and shortcut column everywhere. Shortcuts are right-aligned in the muted colour.
5. Scroll bars are thin when idle and widen on hover, in all themes.
6. The command tab buttons belong to RIBBON_SPEC (round 10f). Do not change `QToolButton#ribbon_*` rules or `ui/command_tabs/` here.

## U4. Keyboard and accessibility

1. Keyboard focus is always visible. Today only text fields and drop downs show it. Buttons, tool buttons, check boxes, radio buttons, sliders, tabs, tree and list rows, and the view all get a 2 px accent focus ring (inside the control's radius), shown for keyboard focus only, not after a mouse click.
2. Tab order follows reading order in every panel and dialog. Esc closes or cancels, and Enter runs the default button.
3. Every control without visible text has an accessible name (today none have one). Every icon button uses its tooltip title. The tree, view and panels have names too.
4. No information is shown by colour alone: errors also have an icon and a message, and tree states also have an icon.
5. A preference to reduce motion turns off all animation (U7).

## U5. Icons

1. All 268 icons pass one audit, run with `tools/icon_sheet.py` at 16, 24 and 48 px in both light and dark:
   - 1.5 px strokes and round caps
   - shapes kept inside 2 to 22
   - the same visual weight and size (a circle icon is drawn a little larger than a square one so they look the same size)
   - accent used only for the active part
   - no stray fills or hairlines
   Redraw any icon that fails. Every icon stays FDCAD's own drawing.
2. Lines land on the pixel grid at 16 and 24 px, so icons are sharp at 100 percent and on HiDPI screens.
3. Icons of one family share a base shape: all sketch tools, all features, all reference geometry, all view tools.
4. Disabled icons use the theme's disabled colour, not lowered opacity on top of the accent.
5. The app icon reads at 16, 32, 48, 256 and 512 px, has a Windows `.ico` with all sizes and a macOS `.icns`, and looks right on light and dark taskbars.
6. The icon sheet for the owner goes to `docs/screenshots/icons_light.png` and `icons_dark.png`.

## U6. The 3D view

1. Smooth edges: multisample anti-aliasing on when the graphics card supports it (fall back quietly), and smooth lines for edges and sketches.
2. The background gradient is subtle and the same direction in all themes. Parts sit on it with clear contrast (U1.3).
3. Lighting shows shape: a key light, a soft fill and some ambient. No face of a plain grey part looks flat black or blown out from any standard view.
4. Silhouette edges are drawn, so a part's outline reads from any angle.
5. Pre-selection highlights under the cursor without lag. Selection keeps its colour while rotating.
6. Standard view changes (front, top, iso, normal to) animate the camera in about 250 ms with ease in and out, unless reduce motion is on.
7. The orientation cube and axis triad match the theme, use the type scale, and never cover the part at the default zoom.
8. No flicker, black frame or white flash on start, resize, theme change or when panels open.

## U7. Motion

1. Animations are short and have a purpose: 120 to 200 ms for panels and menus, 250 ms for the camera. No bounce.
2. Nothing animates when reduce motion is on, or during a slow rebuild.

## U8. Feedback and messages

1. Anything that takes longer than 300 ms shows progress in the status bar, and can be cancelled when the work allows it. The window never looks frozen.
2. Every error message says what happened and what to do next, in plain words. It names the feature, never shows a raw exception, and offers a "Copy details" button that copies the technical text.
3. Empty places say what to do: an empty tree ("Start a sketch on a plane"), an empty search result, an empty recent files list.
4. Short confirmations (saved, exported, copied) appear briefly in the status bar, not as a dialog.
5. Destructive actions (delete feature, close without saving) name what will be lost, and default to the safe button.
6. All wording follows CLAUDE.md section 8: plain words, no dashes, title case for command labels and sentence case for messages.

## U9. Window and app details

1. The window remembers its size, position, splitter sizes and maximised state, and opens on a visible screen if a monitor is gone.
2. The start is clean: a small splash or the empty window within 1 second, no half-drawn widgets.
3. The title shows the file name, a mark for unsaved changes, and "FDCAD".
4. The About box shows the version, build date and log folder, with a button to open the log folder.
5. Windows uses the dark title bar in dark themes. macOS uses the native title bar and menu placement.

## U10. Debugging and robustness

1. Uncaught errors in the UI are caught by one handler. It writes the full trace to the log, shows the U8.2 message, and keeps the app running when it safely can.
2. Qt warnings (qWarning, bad style sheet, missing icon) go to the log. Tests fail on any Qt warning raised while building the main window and opening each panel.
3. Help > Diagnostics has "Copy system info" (version, OS, Qt and OpenGL versions, GPU, display scaling, theme) for bug reports.
4. A developer overlay, hidden behind a preference, shows frame time and rebuild time in the view corner.

## U11. Checks

1. Tests for U1.7, U2.1 (no font size outside the scale), U3.3 (minimum sizes), U4.1 (focus ring rule present for each control type), U4.3 (every icon button has an accessible name), U5.1 (icon audit: viewBox, stroke width, bounds) and U10.2.
2. Screenshots of the main window, a sketch, a part with selection, the property panel, a dialog and an error message, in all four themes at 100 and 150 percent. They go to `docs/screenshots/polish/` for the owner.
3. Every change keeps all existing tests passing.
