# Round 13, cloud G: sketch (report)

Branch `cloud/round13g`, decisions D1700 to D1719. The branch was made from `phase7b-stage2` and `origin/phase7b-stage2` was merged back in once at the end (a merge, not a rebase: the round's 21 commits each touched CHANGELOG.md, DECISIONS.md and PLAN.md, so a rebase would have hit a conflict on almost every commit). The stop signal was checked before every item and was never set.

## Items done

| Item | What was built | Decision | Commit |
|---|---|---|---|
| TR48 | Sketch Fillet with splines (line and spline, arc and spline). Sketch Chamfer on arcs and splines. Dragging from the corner sets the fillet size. | D1700, D1701, D1702 | 80d8d6be |
| TR339 | Show Construction in Part, a tick per sketch (tree menu or Sketch command). Construction curves and points show in 3D. They are offered to Convert Entities and to vertex picks. | D1703 | 8554a95b |
| TR106 | Close Sketch to Model tool: click inside the side to keep. | D1704 | 944f4f07 |
| TR341 item 2 | Direction arrows in the Offset and sketch pattern previews. | D1705 | 377dfd59 |
| TR238 | Preference: Lock changed dimensions while dragging. | D1706 | 4e8cbcd9 |
| TR111 items 1 and 3 (part) | Right click while placing a dimension locks its type. Dimension Display can hide the extension lines or the dimension line. | D1707, D1708 | f413c72b |
| TR114 item 2 | Edit Polygon (right click a side). Triangle button in the Polygon tool. | D1709 | 6ec1aacc, 132b9bbf |
| TR115 items 1 and 2 | Infinite Construction Line tool. Flip direction option for Tangent Arc. | D1710 | 6ccdddf8 |
| TR116 item 2 | Sketch Picture: Trace Colour Region and Trace Box turn picture areas into lines. | D1711 | 7070af7b, b918eac6 |
| TR118 | Convert Entities: click inside a face to copy its outer loop, with or without the inner loops. Ctrl click an edge to copy its loop. | D1712 | d25db9e1 |
| TR121 item 1 | Explode Text, with the kernel work off the UI thread. | D1713 | 605294e9 |
| TR232 | Temporary guide lines. Rest the cursor on two points; the guide's ends, middle, thirds and quarters snap. | D1714 | 1c86f8fb |
| TR234 | Already met by design: a finished sketch is display only and does not split faces for picking. The guide and the decision say so; no code. | D1715 | f0fee2f7 |
| TR112 | Drag Without Solving (asks before deleting what no longer holds). Detach Segment on Drag. Preference: Dragging changes dimensions. | D1716 | 31901281, 2c98b08e |
| TR34 | Sketch blocks: Make Block, Insert Copy, Select, Update Block from This Copy, Explode. | D1717 | c5085c8b |
| TR151 item 1 | Slice Body (Tools): parallel offset planes, each with a sketch of its section, all in one Slices folder. | D1718 | 91115a4f |
| TR7 (first form) | New feature type `sketch3d`. It holds plane sketch parts (2D sketches copied in with their planes) and typed 3D lines and splines. It is used as a path. | D1719 | 98f01ec4, 5e923ba2 |

A final commit fixes the ribbon layout test for the new 3D Sketch command (see "Last full suite").

## Items partly done or skipped, and why

- TR48: done. Two splines meeting each other are refused, with a message.
- TR111: the symmetric angle about a centerline (item 2) is not built: it needs a new dimension type in the solver. Arrow flip (item 3) is not built: sketch dimensions draw no arrowheads.
- TR115: no spline length dimension, since splines are not solver curves. Degree and weights do not apply to FDCAD splines (D1314).
- TR121: items 2 (bold, italic and rotation per character) and 3 (numbers that count up across pattern copies) are not built. Both need new text fields in the file, and item 3 also needs a link to the pattern.
- TR232: dragging from a point with a key held is not built, because the drag keys are an owner choice (TR53).
- TR151: slices round an axis are not built. Item 2 (turn a section view into a cut feature) is not built: a section can combine up to three turned planes, and no single body feature takes that.
- TR7: not built yet: drawing inside the 3D sketch with Tab to switch planes, relations between planes, Along X, Y and Z, and 3D dimensions. These need a 3D solver (planegcs is 2D only).
- PLAN.md: TR111, TR115, TR121, TR151 and TR7 stay unticked, each with a "done: Dxxxx; open: ..." note. Every other item is ticked.

## Owner file items (FDEF_SPEC.md and SHORTCUTS.md were not edited)

New keys written only when used:

- Sketch data: `show_construction: true` (D1703) and `blocks: [{id, name, sketch, copies: [{map}]}]` (D1717).
- Dimension `display`: `hide_extension: true` and `hide_line: true` (D1708).
- New feature type `sketch3d`. Its `data.parts` is a list of `{name, plane, sketch}` and its `data.lines` a list of `{kind: line | spline, points}` (D1719).
- Slice Body writes only existing types: `ref_plane` features (method offset, with `flip` for negative distances) and `sketch` features, plus one tree folder.

New preference keys: `sketch/lock_changed_dimensions` and `sketch/drag_changes_dimensions`.

New commands, with no default keys: `sketch.show_construction`, `sketch.close_to_model`, `sketch.infinite_line`, `tools.slice`, `feature.sketch3d`.

New snap kind: `guide` (label "Guide").

## Shared files changed (small edits)

- `ui/sketch_tools/canvas.py`:
  - hooks for the guides, arrows, the dimension lock, picture pixels and Ctrl for tools;
  - free drag and detach;
  - `ask_delete_unmet`;
  - `shown_segments`.
- `ui/main_window/context_menu.py`: menu items for Edit Polygon, blocks, Explode Text, Drag Without Solving and Detach Segment on Drag.
- `ui/main_window/sketch_mode.py`: the Show Construction action, and sketches as Convert Entities sources.
- `ui/tree/feature_tree.py`: the Show Construction in Part tick.
- `ui/equations/install.py`: one line adds Tools, Slice Body.
- `ui/command_tabs/tabs.py`: Close Sketch to Model, Infinite Construction Line and 3D Sketch added to existing dropdowns.
- `ui/input/commands.py`, `ui/strings.py`, `ui/strings_import.py`, `ui/icons/NAMES.md`: new commands, strings and icons.
- `ui/sketch_tools/registry.py`, `ui/sketch_tools/tool_text.py`: the new tools.
- `core/sketch/model.py`: the `blocks` field.
- `core/sketch/solver.py`: `drag(..., hold=...)`.
- `core/rebuild/engine.py`: `RebuildReport.construction_edges`.
- `ui/session.py`: `add_sketch_edges(report, doc)`.
- `core/features/__init__.py`, `core/features/names.py`, `ui/main_window/imports.py`, `ui/tree/row_icons.py`, `ui/property_panel/forms/__init__.py`: registering `sketch3d`.
- `ui/property_panel/start_group.py` and `end_group.py`: construction points in the vertex picks.
- Tests that list menus, tool names or ribbon contents were updated: `tests/ui/test_context_menus.py` (two new menu keys), `tests/ui/test_ribbon_layout.py` (3D Sketch) and `tests/ui/sketch_tools/test_offset_mirror_tools.py` (Sketch Fillet now picks splines).
- The sweep support was not changed. The new dialogs (Edit Polygon, Slice Body) use module level `run()` functions like the existing ones, and the drag question is a `QMessageBox`, which the sweep already handles.

## Last full suite

Run on the merged branch: `pytest -q -p no:cacheprovider`, with a local plugin from the scratchpad that closes pop up menus (see the note below).

Result: 8 failed, 5920 passed, 121 skipped, 1 xfailed. One of the 8, `tests/ui/test_ribbon_layout.py::test_features_tab_order_and_grouping`, was this branch's fault. It is fixed in the last commit and that test file now passes (9 tests). The full suite was not rerun after that fix.

The other 7 also fail on `origin/phase7b-stage2` itself (checked on a clean copy) and are not from this branch:

- `tests/core/io/test_schema_keys.py`: the `living_hinge_strip` and `nut_and_bolt` samples write keys that are not yet in FDEF_SPEC.md (4 tests).
- `tests/core/io/test_old_files.py[print_in_place_hinge]`: a sample from another session.
- `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory`: depends on the machine.
- `tests/ui/test_sketch_preferences.py::test_preferences_dialog_sketch_page`: the page list on the base.

`ruff check` reports 3 issues, all in files from the base branch: the import order in `core/features/__init__.py` and one line in `tests/ui/test_mesh_split_ui.py`. `mypy` (strict, `fdcad/core`) passes.

Note for local runs on Linux: with this PySide build, `monkeypatch.setattr(QMenu, "exec", ...)` in `tests/ui/sweep_support.py` does not take effect, so `menu.exec()` blocks. Before D2005 this hung `test_app_sweep` on the orientation pop up. I ran every test here with a scratchpad plugin that closes the active pop up menu on a timer. This is local only and nothing was committed for it.
