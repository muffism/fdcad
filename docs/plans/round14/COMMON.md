# Round 14 rules (on top of ../round13/COMMON.md)

1. Follow `docs/plans/round13/COMMON.md` and `docs/plans/round12/COMMON.md` in full, with your branch and decision block from `README.md` here. Create your branch from `origin/phase7b-stage2`.
2. STOP SIGNAL: before each item run `git ls-remote --heads origin control/stop`. If it prints anything: push what is finished, write and push `docs/plans/round14/REPORT_<letter>.md`, and stop.
3. Most items are partly done; their PLAN.md line says what is left. Build only what is left. An item the kernel cannot do (no setting for it): record that in DECISIONS, leave the line unticked with a "(not built: ...)" note, and move on.
4. Ribbon: a command tab group never scrolls inside itself, so keep every group under about 900 px wide on the test platform (`tests/ui/test_command_tabs.py::test_window_fits_a_small_screen_and_tabs_scroll`). Add a new group rather than a fifth column (D1027).
5. New sample parts must build on Windows too: avoid sizes right at a face end (the 18 mm thread on a 20 mm shaft failed on Windows, D1027). Samples are saved with app_version 0.1.0 (tests/conftest.py).
6. New sketch or panel options that default off must be added to the defaults tests (`tests/ui/test_sketch_preferences.py`).
