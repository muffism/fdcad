# Owner review checklist for v1.0

This is PLAN.md section 13 filled in for the v1.0 release. The steps are ordered by risk: the ones most likely to find a release blocker come first. Each step says what to do and what you should see. Tick a box when it passes; note the step number for anything that does not.

Build the installers first: run the Release workflow by hand with platforms "both" (Actions, Release, Run workflow). It builds and uploads both installers without publishing anything. The version shows as 1.0.0.dev0 until you tag.

## 1. Install and start (highest risk: the app must open on both platforms)

- [ ] 1.1 Windows: run `FDCAD-1.0.0.dev0-dev-windows-x64-setup.exe`. The setup window and the installed app show the FDCAD icon (a white block with a hole on a blue tile). FDCAD appears in the Start menu with an uninstall entry.
- [ ] 1.2 Windows: double click any `.fdprt` file (and an older `.fdef` file) in Explorer. FDCAD opens it, and the file shows the FDCAD icon.
- [ ] 1.3 Mac: open the DMG, drag FDCAD to Applications, right click it and choose Open. The Dock shows the FDCAD icon and the 3D view draws the part (not a grey box).
- [ ] 1.4 Mac: double click a `.fdprt` file in Finder. FDCAD opens it.
- [ ] 1.5 Both: the first start shows the Welcome window. Close it, quit and start again: it does not come back. Help, Welcome shows it again.
- [ ] 1.6 Both: turn on a high resolution display setting (Retina on the Mac, 150 percent scaling on Windows). Icons, text and the 3D view are sharp and sized right.

## 2. Files from earlier versions (data loss risk)

- [ ] 2.1 Open a part you saved with 0.1.0 or any earlier build. It rebuilds with no new errors.
- [ ] 2.2 Save it, close it and open it again. It looks the same.
- [ ] 2.3 File, Open Sample: open each sample below and check it rebuilds with no errors in the Errors tab: plate with holes, turned shaft, bracket, enclosure, lofted handle, swept spring, patterned flange, multibody split part, tapped housing, printable enclosure, configured bolt family, twisted bar, flowed strap, chain along curve, piped frame, split with pins, imported STEP with features, imported mesh with cut, sheet metal bracket (folded and flat) and the 200 feature part.

## 3. Crash safety

- [ ] 3.1 Make a small part, wait 5 minutes (one autosave), then end FDCAD from Task Manager or Activity Monitor. Start it again: it offers to recover the part, and the recovered part has your last change.
- [ ] 3.2 Make a feature fail on purpose: a fillet with a radius of 50 mm on the plate with holes. FDCAD keeps running, the feature turns red, and the Errors tab message says what failed and what to do next.

## 4. Upstream edits flow downstream (topological naming)

- [ ] 4.1 Bracket sample: double click the first sketch, change its width, exit the sketch. The holes, fillets and later features follow the new size.
- [ ] 4.2 Enclosure sample: change the shell thickness, then the box height. The fillets and the shell stay on the same faces.
- [ ] 4.3 Sheet metal bracket: change the thickness and a flange length, then Flatten. The flat pattern updates.
- [ ] 4.4 Configured bolt family: switch configurations in the Configurations tab. Each size rebuilds.

## 5. Save and export

- [ ] 5.1 Save, close and reopen the bracket. It is the same.
- [ ] 5.2 File, Export, STEP. Open the STEP file in another CAD program. The volume matches (Evaluate, Print Estimate shows the volume in FDCAD).
- [ ] 5.3 Export STL and 3MF, and Open in Slicer. The slicer shows the part the right way up and at the right size.

## 6. Speed and memory on the baseline machines (PLAN 11)

The budget tests pass in CI; these confirm them on your machines.

- [ ] 6.1 MacBook Air M1: FDCAD shows its window in under 2 s and is ready in under 5 s. Tools, Rebuild Statistics shows the memory: under 400 MB with an empty part.
- [ ] 6.2 Open the 200 feature part. Change a dimension near the end of the tree: the rebuild takes under 0.5 s. Memory stays under 1.5 GB.
- [ ] 6.3 Turn the 200 feature part with the mouse. It stays smooth.
- [ ] 6.4 Repeat 6.1 and 6.2 on the Windows laptop.

## 7. The 1.0 round itself

- [ ] 7.1 Help, About FDCAD: the version, the GPL v3 license, the third party licenses (Licenses tab, each text opens) and the not affiliated sentence.
- [ ] 7.2 Help, Open User Guide: the guide opens inside FDCAD with your network off. Links between pages work; Back and Contents work.
- [ ] 7.3 Help, Keyboard Shortcuts: type "extrude" in the filter. Change a key in Preferences and open the list again: it shows the new key.
- [ ] 7.4 Messages: give an extrude a depth of 0, and draw a sketch of three lines that do not close before using it in an Extruded Boss. Each message says what failed and what to do next.
- [ ] 7.5 Sheet metal: on the sheet metal bracket add a Hem, a Miter Flange and a Jog, then Flatten and Export Flat Pattern to DXF.
- [ ] 7.6 Fastening: on the printable enclosure, add a Hole Tool heat set insert and a Snap Hook. Undo both.
- [ ] 7.7 Node editor: File, Open a sample graph from the `graphs` folder inside the samples folder, open the Graph tab, change a Number Slider, then Add as Feature.

## 8. Release

- [ ] 8.1 Read `docs/RELEASE_NOTES_1.0.md` and `CHANGELOG.md` section 1.0.0. Set the date in both.
- [ ] 8.2 Run `uv run python tools/set_version.py 1.0.0`, then `uv lock`, and commit. The release workflow refuses a `v1.0.0` tag while the app still says 1.0.0.dev0.
- [ ] 8.3 Merge the pull request, or reply with the numbers of the steps that failed.
- [ ] 8.4 Tag `v1.0.0`. The release workflow builds both installers and publishes them with the 1.0.0 changelog section as notes.
