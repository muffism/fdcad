# Getting started

This page shows you around the FDCAD window. It covers the command tabs, the left panel, the confirmation corner and the shortcut bar. It also explains how to make, open and save parts, how undo works, how to read errors and warnings, and how to change your preferences.

Where to find it: the File, Edit, View, Insert, Tools and Help menus at the top of the window, and the command tabs below them.

On a Mac, read Ctrl as Cmd and Alt as Option in every key on these pages. A few keys keep Control on a Mac: Force Rebuild (Control+Q), Hide All Reference Geometry (Control+H), Show All Hidden Bodies (Control+Shift+Tab) and View Selector (Control+Space). Function keys need the fn key unless "Use F1, F2, etc. keys as standard function keys" is on in the macOS keyboard settings.

## Safe graphics

FDCAD never needs a graphics card, but a broken graphics driver can stop the 3D view from drawing or FDCAD from starting. Safe graphics draws in software instead: slower, but it works everywhere.

- Tick **Safe graphics (draw in software)** on the General page of Preferences. It takes effect the next time FDCAD starts.
- Or start FDCAD with `--safe-graphics`, or set the environment variable `FDCAD_SAFE_GRAPHICS=1`.
- If a start does not get as far as showing the window, the next start uses safe graphics by itself and says so in the status bar. Tick the preference to keep it.

## The window

The window has five areas.

1. Top: the menu bar and the command tabs.
2. Left: the left panel with its tabs.
3. Centre: the 3D view. A small view toolbar sits at the top of it. The XYZ triad sits in the bottom left corner.
4. Top right of the 3D view: the confirmation corner, shown while you edit a sketch or a feature.
5. Bottom: the status bar. It shows messages, the sketch status, the cursor coordinates and the unit selector.

Each open part is a tab above the 3D view. You can have several parts open at once.

On Windows and Linux every menu works from the keyboard: Alt and the underlined letter opens a menu (Alt+F for File). In an open menu, type the first letter of an entry to go to it. When only one entry starts with that letter it runs, or its submenu opens; when several do, each press moves to the next one, and Enter runs it.

**Tips**

1. **Toggle Left Panel** (F9) hides or shows the left panel.
2. **Toggle Command Tabs** (F10) hides or shows the command tabs.
3. **Full Screen** (F11) fills the screen. On a Mac, Control+Cmd+F also works.
4. Outside a sketch, the status bar shows the X, Y and Z of the model point under the cursor.

With several parts open, **Next Part** (Ctrl+Tab, Control+Tab on a Mac) brings the next one forward while the 3D view or the tree has focus. **Previous Part** has no key until you set one in the shortcut editor.

## Command tabs

The command tabs hold the tools as buttons, in groups.

1. Features: Sketch, Add Material, Remove Material, Modify, Reference and Curves, and Direct Editing. Tools most parts use (Hole Tool, Rib, Draft, Shell, Mirror) have their own button. Close variants of one tool share a button with a dropdown arrow: click the icon to run the tool shown, or the label and arrow to open the list.
2. Sketch: Sketch, Draw, Modify, Tools and Text.
3. Bodies: Bodies (combine, split, move, scale, delete), Deform and Import.
4. 3D Print: Print Features (Split for Printing, Mounting Boss, Snap Hook with Snap Hook Groove, Lip and Groove, Vent), Print and Check.
5. Sheet Metal: the sheet metal tools. See [Sheet metal](sheet-metal.md).
6. Evaluate: Measure, Section View, Rebuild and the curvature graph. See [Evaluate](evaluate.md).
7. Graph: the node editor. See [Node editor](node-editor.md).

**Steps**

1. Click a tab name to show its tools.
2. Hover a button to read its tooltip. The tooltip gives the name, one sentence on what it does and its shortcut.
3. A button with a small arrow holds several tools. Click the arrow to choose one. The button then shows the tool you used last, also after a restart.

**Tips**

1. **Next Command Tab** (Ctrl+PgDown) and **Previous Command Tab** (Ctrl+PgUp) step through the tabs.
2. Right click the tab bar to show or hide single tabs.
3. Opening a sketch switches to the Sketch tab for you.
4. Right click a command button and choose **Add to My Commands** to put it on your own My Commands tab, with large buttons and their names. **Remove from My Commands** takes it off; the tab goes when it is empty.
5. Right click a command button and choose **Hide Button** to hide it. **Show Hidden Buttons** on the tab bar's right click menu brings them all back.
6. **Simple Mode** on the tab bar's right click menu shows only the Features, Sketch, Evaluate and My Commands tabs, with the tools most parts need. Untick it to see everything again.

## Left panel

The left panel has these tabs: Feature Tree, Properties, Variables, Errors and Configurations. Each tab is an icon; hover it to see its name. The Errors tab shows the number of errors beside its icon.

With no part open, the feature tree is replaced by a boxed line: "No part is open. Use New Part or Open to start." The filter box and the state choice above it stay in place but are greyed.

### Feature tree

The feature tree lists everything in the part in build order: the origin, the Front, Top and Right planes, then each sketch and feature. New features get names like "Extrude 1", "Cut 1" or "Fillet 1". A sketch moves under the first feature that uses it. A Solid Bodies folder appears at the top when the part has more than one body.

**Steps**

1. Click a feature to select it. Its dimensions show on the model. Double click a dimension to change it.
2. Right click a feature for Edit Feature, Edit Sketch, Rename, Suppress, Unsuppress, Delete, Roll Back to Here, Move Up, Move Down and Parents and Children. Move Up and Move Down move the feature one place, as dragging it would, without a drag. Parents and Children lists what the feature uses and what uses it; double click a row to walk to that feature and see its own parents and children.
3. Right click the part row and tick **Parent and Child Arrows** to draw arrows in the tree from the feature under the mouse (or the picked one) to its parents (blue) and children (orange). An item inside a closed folder or feature points at that row. The arrows are off when FDCAD starts.
4. Drag a feature up or down to reorder it. FDCAD blocks a move that would put a feature above something it uses.

**Folders and comments**

1. Select neighbouring features (Ctrl click or Shift click to pick several), right click and choose **Add to New Folder**. The folder row opens and closes like any other; double click its name or press F2 to rename it. Right click it for **Remove Folder**, which keeps the features where they are (Delete on a folder row does the same). Features keep their order; a feature moved away from the others leaves the folder.
2. Right click a feature and choose **Comment...** to add a short note. A small dot on the row's icon shows it has one; hover over the row to read it. Clear the text to remove it. Deleting a feature also takes it out of its folder and drops its comment.
3. Folders and comments are saved with the part and do not change the model.

**Rollback bar**

The rollback bar is the line at the bottom of the tree. Drag it up to see the part as it was at that point. Features below the bar are greyed out and not built.

1. Select the bar and use the Up and Down arrow keys to move it one feature at a time.
2. New features go just above the bar.
3. **Roll Back One Feature**, **Roll Forward**, **Roll to Previous** and **Roll to End** are in the Edit menu under Rollback Bar and in the right click menu.
4. The bar position is saved with the part.
5. **Delete Below Rollback Bar** (in the same menu) deletes every feature below the bar after asking. Undo brings them back.

**Freeze bar**

On a large part, the freeze bar saves rebuild time. Features above it are not rebuilt: they keep the result they had when they were frozen, and they cannot be edited until you move the bar above them.

1. Right click a feature and choose **Freeze Up to Here**. A Freeze bar row appears below it.
2. To edit a frozen feature, right click it and choose **Move Freeze Bar Above Here**, or right click the Freeze bar and choose **Unfreeze All**.
3. Each move is one undo step, and the bar's place is saved with the part.

**Copy Values to Others** (right click a feature) gives other features of the same kind its values, for example every hole the size of this one. Tick the features in the list; their picks, names and Boss or Cut choice stay. **Edit by Rule** (Edit menu) finds the features of one kind whose value passes a test, such as fillets with a radius under 2 mm, shows them, and sets the value you type on all of them. Each is one undo step.

**Remove History** (Edit menu) turns the part into one plain body, after asking: the shape stays, but the features and sketches are replaced by one Imported STEP feature. Use it to share a simple part without its design. Undo brings the features back.

**Purge Unused** (Edit menu) lists what the part keeps but does not use: sketches no feature uses, suppressed features and variables nothing uses. Every row starts ticked: untick what you want to keep, such as a layout sketch, and press OK. A suppressed feature takes the features built on it with it. One undo brings everything back.

**Tips**

1. **Find in Feature Tree** (Ctrl+F) finds a feature by name. Right click the tree for **Recently Edited**: the features you last made or changed, newest first; pick one to edit it.
2. **Flat Tree View** (Ctrl+T) shows every feature on its own row, with no nesting.
3. **Scroll Feature Tree to Top** (Home) and **Scroll Feature Tree to Bottom** (End) jump to the ends of a long tree.
4. An under defined sketch shows "(-)" before its name. An over defined sketch shows "(+)".

### Property panel

The property panel (the Properties tab) takes over the left panel while you edit a feature or a sketch tool. Its header has the feature name, the words OK and Cancel, and two small icon buttons: Help (the same icon as Help for This Tool) and Pin. Hover an icon to see its word. Below it are groups of options, such as Direction 1 and Direction 2. Every number field accepts units and formulas, see [Typing values](typing-values.md).

1. OK, or Enter, applies the feature.
2. Cancel, or Esc, closes the panel without changing the part.
3. A small tab strip at the top lets you look at the tree without leaving the tool.

### Variables and Configurations

The Variables tab lists the global variables of the part. The Configurations tab lists the configurations. See [Equations and configurations](equations-and-configurations.md).

## Confirmation corner

While you edit a sketch or a feature, the top right corner of the 3D view shows two marks.

1. In a sketch, the sketch mark exits and keeps your changes. The red X exits and discards them, after a question.
2. In a feature, the check mark accepts the feature. The red X closes it without changes.

Press **Move Confirmation Corner to Cursor** (A) to bring the corner to the mouse.

## Context toolbar and right click menus

When you click a face, plane, sketch or feature, a small row of buttons appears near the cursor with the common actions for it. For a plane it offers Sketch, Normal To and Hide or Show. It fades when you move away.

Right click anything for a menu of what you can do with it. Most entries show the same icon as the command has in the menu bar and the command tabs. An entry whose command has no icon shows none. **Context Menu** (Shift+F10 or the Menu key) opens the menu for the current selection.

## Shortcuts with other keyboard layouts

Single letter shortcuts (S for Sketch, F for Zoom to Fit and so on) follow the key's position, so they work with a Cyrillic, Greek or other non Latin layout: press the key where the letter is on a US keyboard. With an input method on (for example for Japanese or Chinese), a letter typed as composition runs its shortcut too. When the input method is composing something else in the 3D view, the status bar says single letter shortcuts are paused: turn the input method off, or switch it to direct input.

## Shortcut bar

Press **Shortcut Bar** (Q) in the 3D view. A small bar opens at the cursor with the most used commands for what you are doing. It has one set for the part and one for sketches.

1. Type in its search box to find any command by name.
2. Use Up and Down to move, Enter to run and Esc to close.
3. Change its contents in Preferences, on the Shortcut Bar tab.

## New Part, Open, Save and Save As

1. **New Part** (Ctrl+N) asks for the units of the part: millimetres or inches. The choice sets how a number without a unit is read. A new part is named Untitled, the next Untitled 2, then Untitled 3 and so on, so tabs and the question about unsaved changes tell them apart. A name you closed is used again. Save As starts from that name.
2. **Open** (Ctrl+O) opens a `.fdprt` part (older `.fdef` parts open too). It also opens STEP files (`.step`, `.stp`) and meshes (`.stl`, `.3mf`, `.obj`) as a new part. See [Import, export and print](import-export-print.md).
3. **Save** (Ctrl+S) saves the active part. The first save asks for a name.
4. **Save As** (Ctrl+Shift+S) saves the part under a new name.
5. **Close** (Ctrl+W) closes the active part. It asks first if there are unsaved changes.
6. File, Open Recent lists the parts you used last. File, Open Sample opens the sample parts. On Windows the parts you open and save also show in the system's recent list (the FDCAD taskbar jump list and Start). On a Mac, right click FDCAD in the Dock for New Part and your recent parts. Double clicking a part while FDCAD is open opens it in that window instead of starting a second FDCAD.

**Tips**

1. Click the unit in the status bar to change the units used to show and type sizes. The geometry does not change: a size typed as a bare number gets the old unit, so "25" in a millimetre part reads "25mm" after the switch to inches. New bare numbers use the new units. Undo puts both back.
2. FDCAD saves a recovery copy every 5 minutes. After a crash it offers to recover your parts.

**Common errors**

1. "Could not save ...". Choose another folder and try again.
2. "Could not open ...". The message gives the reason. Check that the file is a FDCAD part or a supported import format.

## Copy and paste

1. **Sketch entities**: in an open sketch, select entities and press Ctrl+C, then Ctrl+V. The copy follows the cursor; click to place it. Relations and dimensions among the copied entities come with them. Relations and dimensions to items that were not copied are left out, and the status bar says how many.
2. **A whole sketch**: select a sketch in the tree, press Ctrl+C, select a plane or flat face, and press Ctrl+V (with nothing selected, FDCAD asks for one). The new sketch has the same entities and dimensions, with its origin on the new plane's origin. Links to edges of the part cannot carry over and are dropped.
3. **A feature with its sketch**: select a cut, boss or hole made from a sketch, press Ctrl+C, select a flat face, and press Ctrl+V. The new feature has the same values and a copy of its sketch, centered on the face. If the sketch was tied to edges of the part, FDCAD asks whether to keep those ties (the copy then stays where the original was, as fixed geometry) or remove them.
4. Ctrl and drag a tree row onto a face of the part does the same as copy and paste there, centered where you drop it.
5. Pasting into another open part: picked faces and edges (for example the face of Up To Face) belong to the first part, so they are cleared and the status bar names them; edit the feature and pick them again. Formulas become their values, because names differ between parts, and ties to part edges are removed.

Each paste is one undo step.

What you copy stays on the system clipboard after FDCAD closes, so you can paste it after you start FDCAD again. A sketch or feature is then pasted as into another part (item 5).

### Library features

To keep a feature for use in other parts, right click a sketch, or a feature made from a sketch, in the tree and choose **Save as Library Feature...**. It is saved with its sketch in a `.fdlib` file. To use it, select a plane or flat face and choose **Tools, Insert Library Feature**, then the file. It is placed like a paste from another part: centred on the face, with picks of faces cleared and formulas turned into values.

## Undo and redo

Every change to the part can be undone, including sketch edits, renames and fix buttons.

1. **Undo** (Ctrl+Z) takes back the last change.
2. **Redo** (Ctrl+Y; on a Mac Command+Shift+Z or Command+Y) makes it again.
3. **Repeat Last Command** (Enter or Z) runs the last command again while the 3D view has focus.
4. **Delete** (Delete) deletes the selected feature while the feature tree has focus. If its sketch is used by nothing else, FDCAD asks whether to delete the sketch too.
5. **Escape** cancels a command while the 3D view or the sketch has focus; with the keyboard in the property panel, click Cancel instead.

**Working without dragging.** Click a handle arrow in the 3D view without dragging it: the arrow then follows the cursor until you click again. While it follows, the arrow keys nudge the value by the ruler step (Shift: a tenth of it), Enter keeps the value and Escape puts it back. In a sketch with no tool active, the arrow keys move the picked points and curves by 1 mm (Shift: 0.1 mm), keeping their relations, one undo step each; with a point picked, Tab picks the next sketch point. To step through the items under the cursor, Alt click or use Select Other.

## Errors, warnings and fix buttons

FDCAD never crashes when a feature fails. The feature is marked instead.

1. A feature with an error has red text and a red dot. It builds no geometry.
2. A feature with a warning has a warning colour and dot. It still builds. Features it uses get a smaller dot.
3. The part name at the top of the tree gets a mark when any feature has a problem. Click it to list every error and warning.
4. Click a marked feature to see its message beside the row, with Edit Feature and Edit Sketch buttons.
5. The Errors tab lists every problem of the last rebuild, errors first. It highlights the faces and edges involved in red.

Some problems come with fix buttons, for example "Add 0.01 mm" for a zero thickness wall, "Fillet the rest" for edges that cannot be rounded, or "Move the hinge to ..." for a hinge that is off the edge where its two bodies meet. FDCAD never changes your geometry by itself. A fix runs only when you click its button, and you can undo it.

Two features that end at the same number make one face. When you change one number, the face splits and a feature that picked it can fail. The message then says the picked face was one face of both features, how far apart their faces are now, and highlights the pieces. For two blind extrudes it offers two buttons, such as "Use Dropout's Depth for Both": the button adds a length variable that holds that depth and sets both depths to it, so the faces meet again and move together. A pocket whose floor sat level with a plate's top gets a formula such as `=14mm - Plate_depth`, which keeps them level at every value. Nothing changes until you click a button, and you can undo it.

A yellow warning can also mean that a reference was found again by its position after an edit. Check the feature. A red "missing reference" error means you must pick the face or edge again. When an earlier feature took the face away, the error names it: click **Show Cause** to select that feature.

When a feature makes a separate body, the warning offers Keep separate body. Your choice is saved with the part, so the warning stays hidden after you reopen it. To see the warning again, right click the feature and choose Warn About Separate Bodies.

## Message bars

Some messages show in a bar above the view, not in a window. A warning bar starts with a warning mark. An information bar starts with an information mark and has a quiet grey edge. A green edge is used only for something that worked, never for a notice. The kind of a bar never depends on its colour alone, because of the mark.

The button that does what the message asks (Suppress, Save All) is outlined and comes first. **Don't Show Again** and **Close** are plain buttons. Close is a cross icon, and its tooltip says Close.

Opening a part that has damaged parts in its file shows one warning bar that says what was left out, for example a configuration entry with no name. It also says when a saved view, tree folder or configuration was renamed because its name was taken, empty or too long (for example Top 2 or Folder 1). Check the part, then save it to keep it as it is now, or open another copy of the file. This bar has no Don't Show Again, since each damaged file is its own news.

## Rebuild and Rebuild Statistics

FDCAD rebuilds the part in the background after each change. The status bar shows the feature being built, and a Cancel button beside the progress bar stops the rebuild.

A rebuild expected to take more than a few seconds runs in a separate helper program, so the window stays free and Cancel works at once, however large the part. A slow part that was saved opens showing its saved shape and is rebuilt behind it. If the helper stops while building a feature, FDCAD stays open: a bar over the view names the feature, the rebuild stops just before it, and a Suppress button turns it off, as after an unexpected close (see [If FDCAD closes unexpectedly](#if-fdcad-closes-unexpectedly)).

1. **Rebuild** (Ctrl+B) rebuilds the features that changed.
2. **Force Rebuild** (Ctrl+Q) rebuilds every feature from scratch, ignoring saved results.

**Simplify threads while editing** (Preferences, General): modelled threads show as cosmetic threads while you edit, which rebuilds much faster on parts with many threads. Force Rebuild models them; exports say so in their note when a part still has simplified threads.
3. **Rebuild Statistics** (Tools menu, or the Evaluate tab) lists how long each feature took, whether it was rebuilt or reused from the cache, and the memory in use. Use it to find slow features.

## Preferences

**Preferences** (Ctrl+,) opens the preferences dialog. Its tabs are:

1. General: default units for new parts, colour theme (Beige, Light Gray, Dark Grey, Stealth (black) or Follow system; Light Gray is the default; while a Windows contrast theme is on, FDCAD uses its colours instead), navigation (Mouse or Trackpad), Reduce motion (no view or interface animations) and the autosave interval.
2. Sketch: snapping and sketch display options. See [Sketching](sketching.md).
3. Shortcuts: change any key. Search for a command, click the shortcut field and press the new key. If the key is in use, FDCAD says which command loses it. Reset to Defaults puts back the original keys, or with All Input Settings also the search words, mouse gestures and shortcut bar. Theme, units, autosave and the other pages keep their settings.
4. Gestures: choose the command for each right drag direction, with 4 or 8 directions.
5. Shortcut Bar: choose the commands in the shortcut bar.
6. Printing: printer profiles and material densities. See [Import, export and print](import-export-print.md).

## Help menu

The Help menu works without an internet connection.

1. **Welcome** shows the short tour from the first start again: how to start a sketch, the command tabs, the left panel, Preferences and themes, and this guide. The tour shows by itself only once. Close it with Start Modeling or the window's close button, or click **Start Lessons**.
1. **Lessons** opens a small window with a short lesson, such as Your First Part or Cuts, Holes and Patterns. Do each step in your own way: a step is ticked when the part shows it, for example when the sketch is fully defined or the part has a fillet. **Resume Later** closes the window and keeps your ticks; choose Lessons again to go on. **Start Over** clears the ticks of the lesson shown.
2. **Open User Guide** opens this guide inside FDCAD. Use Back, Forward and Contents at the top to move between pages. FDCAD does not open web pages from the guide. **Help for This Tool** opens it at the section for the panel that is open, the sketch tool in use or the last command you ran. It has no key yet; give it one in the shortcut editor.
3. **Keyboard Shortcuts** lists every command with its group and its keys, including the keys you changed. Type in the box at the top to filter by command name or key. Change Shortcuts opens Preferences. On Windows the default keys never pair Ctrl with Alt (that pair is AltGr on many keyboards and types letters), never use the Windows key, and never use Alt with a letter that opens a menu, so keep to the same rules when you choose your own.
4. **What's New** lists the newest changes to FDCAD, at any time.
5. **About FDCAD** shows the version and the license. FDCAD is free software under the GNU General Public License, version 3 or later. The Licenses tab shows the FDCAD license, the third party notices and the license texts of the parts FDCAD uses.

Every feature panel has a **?** button in its header that opens this guide at that tool's page. The first time you use a tool, its panel shows a one line hint with a **Show Me** link to the same page; **Turn off hints** stops them.

Error and warning messages always say what failed and what to do next, for example "Extrude 1: Depth must be greater than zero. Enter a positive depth." When a message is not enough, look up the tool's page in this guide.

Next, read [View and selection](view-and-selection.md), then [Sketching](sketching.md).

## Part notes

**Tools, Part Notes** keeps a page of plain text in the part, for notes such as which variables to change, what the part is for or how to print it. Write headings, lists or simple tables as plain text. The notes are saved with the part and changing them is one undo step. Nothing in the notes ever runs, and a link stays plain text: FDCAD never opens it.

## Save a Copy and the tree filter

**File, Save a Copy** writes the part to a new file and leaves the open part as it is, with its own name. **Save a Copy and Open** also opens the new file in a new tab.

**File, Save Increment** saves the part under the next numbered name in the same folder and keeps working in the new file: Bracket becomes Bracket 01, then Bracket 02. A name that already ends in a number keeps its style (box_7 becomes box_8, v009 becomes v010). Names already taken are skipped. The earlier files stay as they were, so you keep each step.

**File, Open for Viewing** opens a part to look at: turn, zoom and measure as usual, but nothing in it changes, so you cannot alter a finished part by accident. The tab says (view only) and a bar above the view has an **Edit** button that switches to full editing.

**File, Save All** saves every open part with unsaved changes. **File, Close All** closes every part; it asks about each unsaved part first, and Cancel keeps them all open. **File, Revert to Saved** throws away the changes since the last save and opens the saved file again, after asking.

In Preferences, **Older copies to keep** makes each save first keep the old file as a numbered copy (name.backup1, name.backup2 and so on, newest first) in a Backups folder beside the part, or in the folder you type. **Open the parts from last time at start** reopens the saved parts that were open when FDCAD closed.

When no part is open, the start page fills the window. It has **New Part** and **Open...** buttons and your recent parts as pictures (with no recent parts, a boxed line in the middle of the page says what to do), pinned parts first. Double click a part to open it. Right click a part to **Pin** or **Unpin** it, **Remove from List**, or **Show in Folder**. Each save keeps a small picture of the 3D view in the part file, so the start page can show it. You can also drop a part file anywhere on the window to open it.

The box above the feature tree filters it: type part of a name to see only the rows that hold it, with the rows above them. The list beside it shows only features with errors or warnings, suppressed features, or features with comments. Clear the box and choose All to see the whole tree.

## Undo To and deleting

**Edit, Undo To** lists the last steps of the part, newest first. Choose one to undo it and every step after it at once.

Deleting a feature that others use opens a list of every feature and sketch that depends on it, directly or through another. All are ticked, so Delete removes them all with it as one undo step; untick the ones to keep (they then show what they lost). When global variables were used only by the features being deleted, the same dialog lists them too, unticked: tick the ones to delete as well, and the rest stay in the equations manager. A variable no formula used is never listed. With faces picked in the 3D view, the Delete key offers **Delete Feature** (the feature that made the face) or **Delete Face**.

## Stopping slow work

Press **Esc** while the part is rebuilding to stop the rebuild: after you confirm, the part shows the last features that finished. With a feature panel open, Esc first stops a slow preview (the panel stays open); press Esc again to close the panel.

Slow rebuilds, exports and sending the part to the slicer show a progress bar in the status bar. The same progress shows on FDCAD's taskbar button on Windows and as a badge with the percentage on its Dock icon on a Mac, so you can see it while you work in another program.

## Templates

To start new parts with the same settings, set up a part (units, global variables, part colour, material, custom properties, mesh export settings and the printer you use) and choose **File, Save as Template**. Type a name. **New Part** then offers your templates: choose one and the new part starts with those settings and no features. The template's printer becomes the active printer if it is still in your printer list.

## Pausing rebuilds on heavy parts

**Edit, Pause Rebuilds** stops FDCAD from rebuilding after each change. Make several edits; the status bar says the part is out of date. Then:

- **Rebuild** (Ctrl+B) applies the edits and leaves the pause.
- **Rebuild and Stay Paused** applies them and keeps collecting.
- **Discard Paused Edits** undoes the edits made since the pause (or since the last Rebuild and Stay Paused).

While rebuilds are paused, a bar above the view says so. Some messages show in such bars: they stay until you press **Close** (the cross at the right of the bar), or until they no longer apply. When the disk that holds your parts or their recovery copies has less than 500 MB free, or (on Windows) less than 300 MB of memory is free, a bar says so with a **Save All** button, so you can save before anything is lost. **Don't Show Again** hides that message for good; to see it again, pick it under **Hidden messages** in Preferences and press **Show Again**.

Right click a feature in the tree and tick **Checkpoint** to stop every rebuild just after that feature, so you can check the part up to there. **Edit, Continue Rebuild** goes on past it once. Untick Checkpoint to remove it.

## Replacing a sketch or plane everywhere

Right click a sketch, plane or feature in the tree and choose **Replace Everywhere**. Pick the item to use instead (the list shows items of the same kind that come before every feature that uses the old one) and tick **Delete the old one** if you no longer need it. Every feature that used the old item now uses the new one, as one undo step. When you delete an item that other features use, the Delete dialog also offers **Replace Instead**, which does the same and then deletes the old item.

## Property panel tips

- **Pin**, the pin icon in the panel header, keeps you making the same feature: after OK, the command starts again for the next one. While it is on, the pin is drawn pushed in. Unpin it, or press Cancel, to stop.
- **Shift and Enter** does the same once without the pin: it accepts the panel and starts the same tool again, empty.
- The panel title turns red while the feature cannot be built yet, for example before you pick what it needs. Hover the title for what to do.
- Fold a group with its arrow and it stays folded the next time that panel opens, until you open it again.
- Right click a list of picks for **Delete** (the selected picks) and **Clear Selections** (all of them). Lists of several picks grow taller as you add picks.
- Tab moves through the fields, Space ticks a tick box and the arrow keys change a choice.

## Portable FDCAD (Windows)

FDCAD can run without being installed.

1. **Single file:** copy `FDCAD-portable.exe` anywhere, for example to a USB stick, and double click it. It unpacks itself each time it starts, so it takes longer to start than an installed FDCAD.
2. **Portable folder:** unzip the portable folder and start `FDCAD.exe` inside it. It starts as fast as an installed FDCAD. The file `portable.txt` beside `FDCAD.exe` is what makes the folder portable; keep it there.

A portable FDCAD keeps everything it writes in a folder named `FDCAD Data` beside the program: preferences (`settings.ini`), autosaves, logs, templates and the rebuild cache. It writes nothing to the registry and does not add parts to the Windows recent list. To move your settings to another PC, copy the program together with `FDCAD Data`. To start fresh, delete `FDCAD Data`.

If the place cannot be written, for example a read only disk, FDCAD still starts and uses your user profile like an installed copy.

## If FDCAD closes unexpectedly

FDCAD autosaves parts with unsaved changes and offers them again at the next start.

If FDCAD closed while it was rebuilding a feature, it also remembers which feature that was. The next time you open that part:

1. The status bar says which feature FDCAD was rebuilding.
2. The part opens with the rebuild stopped just before that feature, so you see the part as it was up to there. A bar over the view names the feature.
3. Change the feature (for example a smaller fillet radius), or choose the Suppress button in the bar to turn it off. Either way the rest of the part rebuilds.
4. To try the feature again as it is, use Edit, Force Rebuild.

FDCAD also writes what it was doing to a file named `crash.log`, in the same folder as its log (Help, Diagnostics, Open Log Folder). A problem report (below) includes it.

## Reporting a problem

FDCAD never sends anything by itself. A problem report is a text file that you send yourself, from your own mail app.

1. Use **Report Problem** in an error message, **Help, Diagnostics, Report a Problem**, or the **Report Problem** button in the status bar after FDCAD closed unexpectedly.
2. FDCAD saves the report in its log folder as `FDCAD-report-` with the date and time, and puts it on the clipboard.
3. Your mail app opens with a message to FDCAD@proton.me. Say what you were doing, attach the report file or paste it in, read it, then press Send.

The report holds the FDCAD version, your system details, the end of the log, the last crash from `crash.log` and the error details. Your login name is replaced by `<user>` and your home folder by `<home>`, so the report does not carry your name. Part file names stay, so rename a part in the text first if its name is private.

If no mail app opens, a message says where the report is saved, with a button to open its folder. Email the file to FDCAD@proton.me from any mail service.

