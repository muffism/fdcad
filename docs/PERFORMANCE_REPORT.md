# Performance Report (Phase 6)

This report is the Phase 6 performance pass of PLAN section 11 (DECISIONS D432). It lists where rebuild time goes in every sample part, the five slowest steps, what was fixed, and how each budget of PLAN 11.2 is tested.

## 1. How it was measured

1. Machine: the Linux cloud container used for this work (4 virtual cores, Intel Xeon at 2.1 GHz, no GPU). It is not one of the PLAN 11.1 baseline machines, so the numbers show proportions. The budget tests run on Windows CI and on Mac pull request runs.
2. Each sample (`samples/*.fdef` and `samples/graphs/*.fdef`) was opened and rebuilt from nothing with a fresh `RebuildEngine`, three times; the fastest run is listed. Time per feature comes from the rebuild report (`FeatureResult.seconds`, the same numbers as the Rebuild Statistics panel).
3. Inside a feature, time was split by wrapping the kernel and naming helpers with timers. Python's `cProfile` was not used for kernel heavy steps: it does not see most of the time spent inside the kernel.

## 2. Full rebuild of every sample

| Sample | Full rebuild (s) |
| --- | --- |
| generated_200 | 1.608 |
| piped_frame | 0.228 |
| voronoi_panel | 0.178 |
| lattice_block | 0.115 |
| attractor_plate | 0.109 |
| flowed_strap | 0.096 |
| chain_along_curve | 0.072 |
| sheet_metal_bracket | 0.049 |
| twisted_bar | 0.045 |
| sheet_metal_bracket_flat | 0.045 |
| enclosure | 0.044 |
| imported_step_with_features | 0.033 |
| split_with_pins | 0.025 |
| bracket | 0.024 |
| plate_with_holes | 0.020 |
| lofted_handle | 0.018 |
| turned_shaft | 0.016 |
| swept_spring | 0.015 |
| imported_mesh_with_cut | 0.013 |
| configured_bolt_family | 0.007 |
| slider_bracket | 0.005 |

Every sample is inside budget 4 (2 s). Only the 200 feature part comes close.

## 3. The five slowest steps

1. **Hole cuts in the 200 feature part (about 1.2 s of 1.6 s).** Each of the 99 Extruded Cuts runs one kernel boolean on the plate. A cut costs about 12 ms on average and grows with the number of faces already in the plate (about 27 ms for the last holes). The time is inside the kernel's boolean. Turning on the kernel's oriented bounding boxes and turning off its inverted solid check were measured and gave no clear gain, so nothing was changed. Not fixed: no change is possible without changing how the cut is made.
2. **Frame Tube in piped_frame (0.23 s).** About three quarters of it is the boolean that cuts the inner tube out of the outer tube; the two sweeps take the rest. Building the hollow tube another way would change how its faces are made and named, so it was left as it is.
3. **Graph Body in the graph samples (0.10 to 0.17 s each).** The Voronoi panel, the attractor plate and the lattice block each run their graph and one kernel boolean for all cells, holes or struts together. These were already batched when they were built (D376, D377); nothing more is clearly fixable.
4. **Flow Along Curve in flowed_strap (0.08 s) and Twist in twisted_bar (0.04 s).** The body is converted to NURBS and every face is fitted to the mapped points. The kernel binding reads and writes control points one at a time (D393 item 6); the maps and solves already use numpy.
5. **Checks after each boolean in long trees (about 0.38 s in the 200 feature part).** The validity check, the merge check and the zero thickness check take about 4 ms per feature. They already look only at new edges and faces (D77); they were left as they are.

## 4. What was fixed

Two costs that every rebuild paid, outside the features, were removed without changing any result:

1. **Equations were solved twice per rebuild.** The rebuild solved the part's equations, then asked for the names a formula can use, which solved them again. The names now come from the first solution (`namespace_from`).
2. **Cache keys built a whole document per feature.** To make each feature's cache key, the rebuild put the feature in a new document and wrote the whole document as file data. The key now uses the feature's own file data (`feature_to_json_data`), which is exactly the same data.

Measured on the 200 feature part (median of 30 runs):

| Case | Before | After |
| --- | --- | --- |
| Edit one dimension near the end (budget 3) | 88 ms | 74 ms |
| Rebuild with nothing changed | 22 ms | 11 ms |

Regression tests: `tests/perf/test_rebuild_overhead.py` checks that a rebuild solves the equations once, that a variable error is still reported, that the key data of every feature of every sample equals its file data, and that making keys never builds a document.

## 5. Budgets as tests

| PLAN 11.2 budget | Test | Result here |
| --- | --- | --- |
| 1. Window visible under 2 s, ready under 5 s | `tests/perf/test_budgets.py::test_startup_and_empty_part_memory` | visible 0.92 s, ready 1.33 s |
| 2. Open a sample with a valid cache under 2 s | `test_open_with_valid_cache` | passes |
| 3. Edit near the end of 200 features under 0.5 s | `test_edit_near_the_end_of_200_features` | 74 ms |
| 4. Full rebuild of each sample under 2 s | `test_full_rebuild_of_each_sample`, `test_full_rebuild_of_each_graph_sample` (new) | at most 1.61 s |
| 5. Sketch dragging at 60 updates per second, 200 entities | `tests/core/sketch/test_sketch_speed.py::test_drag_keeps_up_with_200_entities` | passes |
| 6. Viewport 60 fps on a 200 feature part | checked by hand in each owner review (needs a GPU) | not run |
| 7. Memory under 400 MB empty, under 1.5 GB with 200 features | `test_startup_and_empty_part_memory`, `test_200_feature_part_memory` | 390 MB empty when run alone; see note |
| 8. No leaks over 50 open, rebuild and close cycles | `test_no_leak_when_parts_open_and_close` | passes |

`test_every_budget_has_a_test` keeps this table and the tests in step. The timing tests keep their 50 percent margin for slower CI runners; no budget was changed.

Note on budget 7: in this Linux container the empty part memory test passes when the performance tests run alone (390 MB) but fails inside the full test run, where the started app measured above 400 MB. Other sessions saw the same in Linux containers (D378 measured 453 MB). The Windows and Mac CI runs are the reference for this budget.

## 6. Headroom pass (Phase 7D, D2660 to D2664)

Several timing tests passed on an idle machine and failed when the owner's PC was busy with other work. This pass removed work from the four with the least room. It was measured on the owner's Windows PC while other jobs kept it busy, so the old and the new code were timed in the same run, alternated, and CPU time is given beside wall time (best of six runs, seconds). No budget was changed.

| Budget item (test limit) | Before wall | Before CPU | After wall | After CPU |
| --- | --- | --- | --- | --- |
| Full rebuild of generated_200 (3 s) | 3.03 | 3.58 | 2.03 | 2.02 |
| Full rebuild of nut_and_bolt (3 s) | 1.78 | 4.05 | 1.56 | 3.61 |
| Edit near the end of 200 features (0.75 s) | 0.122 | 0.125 | 0.059 | 0.047 |
| Measure and section a 300,000 triangle mesh (3 s) | 2.49 | 2.41 | 0.41 | 0.42 |

1. A closed mesh is found by sorting one flat array of edge keys, not by a unique over rows (D2660).
2. A rebuild measures each solid once, the thread check measures only the bodies a cut changed, and identical bodies are looked for by their counts first (D2661).
3. The checks after a boolean find the new faces and edges with one kernel map subtraction per feature, and compare surfaces without working out face bounds (D2662).
4. A rebuild makes each kept feature's data once, and a typed plain value is read once (D2663).
5. Cuts on bodies of 100 to 999 faces are made locally when the tool meets only the inside of big flat faces, as in a perforated plate (D2664). All 35 samples give the same face names, volume and messages with it on and off.

What is left: the nut and bolt is now mostly its two thread cuts and the independent common of the thread check (D607), about half each. The lattice block's graph preview takes about 0.4 s of wall time but 2 s of CPU time in the kernel's parallel threads, so it is the next budget likely to fail on a busy machine.
