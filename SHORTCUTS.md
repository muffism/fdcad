# Shortcuts and Gestures

Default input mapping for FDCAD, taken from the owner's existing CAD setup. Everything here is customizable in Preferences (shortcut editor and gesture editor). A shortcut becomes active in the phase where its command is built.

## 1. Mac conversion rules

1. Ctrl becomes Cmd. Alt becomes Option. Shift stays Shift.
2. These keep the Control key on Mac, because the Cmd version is a macOS system shortcut:
   1. Force rebuild: Control+Q (Cmd+Q quits the app).
   2. Force rebuild all configurations: Control+Shift+Q.
   3. Hide all reference geometry: Control+H (Cmd+H hides the app).
   4. View selector: Control+Space (Cmd+Space opens Spotlight). Note: Control+Space also switches keyboard input source if more than one is enabled in macOS. If so, remap it in the shortcut editor.
   5. Show all hidden bodies: Control+Shift+Tab (Cmd+Shift+Tab is the app switcher).
3. Standard Mac app shortcuts stay as macOS defines them: Cmd+Q quits FDCAD, Cmd+H hides it, Cmd+M minimizes it, Cmd+comma opens Preferences.
4. Full screen: F11, and also Control+Cmd+F on Mac (F11 shows the desktop on most Mac keyboards).
5. Function keys on Mac need the fn key unless "Use F1, F2, etc. keys as standard function keys" is enabled in macOS keyboard settings. Mention this in the user guide.
6. Page Up and Page Down on Mac laptops are fn+Up and fn+Down.
7. The Delete command responds to both Delete (backspace) and fn+Delete on Mac.

The list below shows the Windows key. Apply the rules above for Mac.

## 2. File and edit

1. New: Ctrl+N
2. Open: Ctrl+O
3. Close: Ctrl+W
4. Save: Ctrl+S
5. Undo: Ctrl+Z
6. Redo: Ctrl+Y (also Cmd+Y on Mac; see DECISIONS D19)
7. Repeat last command: Enter, or Z
8. Cut, copy, paste: Ctrl+X, Ctrl+C, Ctrl+V
9. Delete: Delete
10. Rebuild: Ctrl+B
11. Rebuild all configurations: Ctrl+Shift+B
12. Force rebuild: Ctrl+Q
13. Force rebuild all configurations: Ctrl+Shift+Q
14. Paste appearance: Ctrl+Shift+V
15. Find in feature tree: Ctrl+F

## 3. View

1. Front, Back, Left, Right, Top, Bottom, Isometric: Ctrl+1 to Ctrl+7
2. Normal to: Ctrl+8, or N
3. View selector: Ctrl+Space
4. Zoom to fit: F
5. Zoom in: Shift+Z
6. Previous view: Ctrl+Shift+Z
7. Redraw: Ctrl+R
8. Wireframe: Shift+W
9. Hidden lines removed: Shift+Q
9a. Hidden lines visible: Shift+H (TR13, D686)
10. Toggle transparency: Shift+T (built in command, replaces the owner's macro)
11. Isolate: I
12. Hide or show selected bodies: H
13. Show hovered body: Shift+Tab
14. Show all hidden bodies: Ctrl+Shift+Tab
15. Hide all reference geometry: Ctrl+H
16. Snap options toolbar: F3
17. Toggle feature tree display column (visibility and colour per feature): F8
18. Toggle left panel: F9
19. Toggle toolbars and command tabs: F10
20. Full screen: F11

### Viewport navigation (viewport focused)

1. Rotate view: arrow keys, 15 degrees a step. Left and right turn about the screen vertical; up and down turn about the screen horizontal.
2. Pan view: Ctrl+arrows, 10 percent of the view width or height a step.
3. Rotate view 90 degrees: Shift+arrows.
4. Roll view: Alt+Left and Alt+Right, 15 degrees a step.
5. Mouse: wheel zooms at the cursor; middle drag rotates; Ctrl+middle drag pans; Shift+middle drag zooms (drag up to zoom in); Alt+middle drag rolls.

## 4. Sketch

1. Sketch: S
2. Line: L
3. Centerline: Alt+C
4. Corner rectangle: R
5. Circle: C
6. Point: P
7. Smart dimension: D
8. Offset entities: O
9. Trim: T
10. Mirror entities: W
11. Convert entities: Ctrl+Shift+C
12. Linear sketch pattern: Alt+L
13. Circular sketch pattern: Alt+P

## 5. Features

1. Extrude: Shift+E
2. Revolve: Shift+R
3. Swept boss: Shift+S (DECISIONS D14)
4. Extruded cut: Shift+C
5. Revolved cut: Ctrl+Shift+R
6. Swept cut: Ctrl+Shift+S
7. Lofted cut: Shift+L
8. Fillet: Shift+F
9. Chamfer: Ctrl+Shift+F
10. Draft: Shift+D
11. Move face: Shift+M (DECISIONS D28)

No default shortcut for lofted boss, shell or patterns; the owner can add them in the shortcut editor.

## 6. Tools and interface

1. Shortcut bar: Q
2. Measure: M
3. Accept suggested edge (chain and loop selection): Y
4. Move the confirmation corner (OK and Cancel) to the cursor: A
5. Flat tree view: Ctrl+T
6. Scroll feature tree to top: Home
7. Scroll feature tree to bottom: End
8. Next command tab: Ctrl+Page Down
9. Previous command tab: Ctrl+Page Up
10. Cancel current command: Escape
11. Next open part: Ctrl+Tab (Mac: Control+Tab), while the 3D view or the tree has focus (TR22, D683)
12. Previous open part: no default key; set one in the shortcut editor (D683)

### Node editor (Phase 7)

These keys work while the node editor has focus, so they do not take the keys from the rest of the app (DECISIONS D378):

1. Add node (opens the node search): Shift+A
2. Delete selected nodes and wires: Backspace, and the Delete key of the app (Edit, Delete) while the canvas has focus
3. Copy and paste nodes: Ctrl+C, Ctrl+V (through Edit, Copy and Paste while the node editor has focus, D685)
4. Group and ungroup nodes: Ctrl+G, Ctrl+Shift+G
5. Pan: middle drag, or hold Space and drag. Zoom: mouse wheel. Add a node at the cursor: double click the empty canvas.

## 7. Mouse gestures

Gestures are triggered by holding the right mouse button and dragging in a direction, then releasing. On a Mac trackpad, hold Control and drag (configurable). Each context has its own wheel. Four directions by default; eight available.

### Part (DECISIONS D16, owner may adjust)
1. Up: Top view
2. Left: Left view
3. Right: Right view
4. Down: Bottom view

### Sketch
1. Up: Smart dimension
2. Left: Line
3. Right: Circle
4. Down: Corner rectangle

## 8. Not mapped (out of scope)

These existed in the owner's setup but have no FDCAD equivalent:

1. Ctrl+D: make drawing from part
2. Ctrl+P: print
3. Ctrl+A: insert note
4. B: balloon
5. Single quote key: select annotation view
6. F7: spell checker
7. G: magnified selection
8. Ctrl+Enter: flip object normal
9. Ctrl+F1: task pane
10. Ctrl+F2: welcome screen
11. Shift+F3: toggle notes upper case

## 9. Conflicts to avoid when adding shortcuts

1. Never assign a Cmd shortcut on Mac that macOS reserves: Cmd+Q, Cmd+H, Cmd+M, Cmd+Space, Cmd+Tab, Cmd+Shift+Tab, Cmd+comma.
2. The shortcut editor must warn when a new shortcut is already used and show which command loses it.
