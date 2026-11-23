# Owner review: the Datum look, the crash guard and portable FDCAD

Branch `phase7d` (DECISIONS D1033, D1034, D1035). What to try, in the order that shows the most first. Tick a line when it is good, or write a note beside it.

## 1. Start

* [ ] Start `FDCAD-portable.exe`. A blue start picture with the new mark shows while it unpacks, then the window opens.
* [ ] The new app icon, F and D, is in the title bar and on the taskbar.
* [ ] Close the open part. The start page shows the mark, New Part as the blue button, and recent parts as tiles.

## 2. Colours and shape

* [ ] Preferences, Theme: try Light Gray, Dark Grey, Beige and Stealth. Each should read as the same design in another colour.
* [ ] The command tools sit on a rounded card; the chosen tab is a white (or lighter) pill.
* [ ] Preferences now fits the screen and its pages scroll.

## 3. Icons

* [ ] Features tab: tools that add material are blue, tools that remove material are orange. Extruded Boss and Extruded Cut should be impossible to mix up.
* [ ] The same colours show beside each feature in the tree.
* [ ] The main tools look like small lit solids, not wire drawings.
* [ ] Look through the other tabs for any icon that looks wrong or unclear and note its name.

## 4. Room to work

* [ ] Every command tab fits your screen without a scroll bar (your screen is 1680 wide).
* [ ] Drag the border of the tree panel narrower. Start Extruded Boss: the panel widens to fit the fields, and OK and Cancel have their own row. Finish: the panel goes back.
* [ ] In a dropdown button (for example Circle), pick another tool: the button takes that tool's name and width.
* [ ] Open a part right after starting: no spare Untitled tab stays.

## 5. Crash guard

This cannot be tried without making FDCAD crash, so it is tested by a program that ends a second FDCAD on purpose. What it does: if FDCAD ever closes while rebuilding a feature, the next start says which feature, and that part opens stopped just before it, with a Suppress button. The user guide has a section on it (Getting started, "If FDCAD closes unexpectedly").

## 6. Portable

* [ ] `FDCAD-portable.exe` runs from any folder and keeps its settings in `FDCAD Data` beside it.
* [ ] The portable folder (zip) starts faster than the single file.

## Decisions I made that you may want to change

1. **The mark.** The amber block of D581 is replaced by an F and a D pushed back into solids, the D turned the other way and joined to the F at the corner (D1036, D1037, your requests). The F is the same drawing, at the same size, as when it stood alone. The D's side walls are a darker orange than the F's: my choice, so that the F reads as standing in front. The end of the F at the corner is a brighter orange so it does not blend with the D's side wall (D1038, your request). The front faces are an off white, the lightest of the three you were shown (D1039, your choice).
2. **Four rows of small tools, not three.** Rows are 24 px, the smallest size the polish spec allows. It is what lets every tab fit 1680 px.
3. **Dropdown buttons change width** when you pick another tool from them. The gain is about 140 px on the Sketch tab.
4. **Orange for removing tools.** If you would rather have one colour for all tools, it is one line to turn off (`CUT` in `tools/icon_duotone.py`, then run the tool on the old icons).
5. **Corners are rounder** (6 and 10 px, were 4 and 6).
