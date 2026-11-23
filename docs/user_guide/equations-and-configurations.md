# Equations and configurations

Equations tie the sizes of a part together, so one change updates the whole part. Configurations keep several versions of one part in one file, such as a bolt in three sizes. A design table lists every configuration and its values in one grid, and can be read from or saved to a CSV file.

Where to find it: Tools, Equations; Tools, Configurations; Tools, Design Table; the Variables and Configurations tabs of the left panel; the Equations folder in the feature tree.

## Global variables

Global variables are named values you can use in any value field. Read [typing-values.md](typing-values.md) for the formula rules.

1. Open the Variables tab in the left panel.
2. Click Add Variable. With no variables, the table says "No variables yet. Use Add Variable to make one."
3. Type a Name, for example `Width`.
4. Type an Expression, for example `100mm`. The Kind and Value columns fill in.
5. In any value field, type `=Width` or `=Width/2` to use it.

Tips:

- Variable names are case sensitive.
- A new variable or value name cannot be a unit (mm, cm, m, in, ft, deg, rad), a formula function (such as sin or sqrt) or pi, because a name right after a number is read as a unit. Parts made earlier keep such names.
- A value with a length unit makes a Length variable. A value with an angle unit makes an Angle. A value with no unit makes a Number.
- Once a part has variables, an Equations folder appears in the feature tree. Double click it to open the equations manager.
- Click Remove Variable to delete the selected row.

### Text and yes or no variables

A variable can also hold text or yes or no.

- Type `yes`, `no`, `true` or `false` as a new variable's value in the equations manager: it becomes a yes or no variable. Formulas read it as 1 (yes) or 0 (no), for example `=if("Holes", 12mm, 8mm)`, and tick box formulas can use it.
- To make a text variable, click its row in the equations manager, click **Type...** and choose Text. Its value is plain text, such as `Front panel`. Formulas cannot use it, but sketch text can show it with a field such as `{Label}`.
- Type... also turns a variable back into a number, or into yes or no.
- A design table column can set text and yes or no variables for each configuration.

### Groups

Click one or more variables in the equations manager, click **Group...** and type a group name. Variables of a group are listed together, pointing at a name shows its group, and typing the group name in the filter box shows only that group. Leave the name empty to take variables out of their group.

## Equations

**Equations** opens the equations manager. It shows every variable, every formula on a feature value and every suppression formula in one window.

1. Choose Tools, **Equations**.
2. Find the three sections: Global Variables, Feature Values and Equations.
3. Click the add row of a section, type a name and press Enter. The name gets quotes and the cursor moves to the value cell with `=` filled in.
4. Type the value or formula.
5. Check the mark beside it: a tick means the formula is valid, a cross means it is not.
6. Read the Evaluates To column, and add a note in Comments if you like.
7. Click OK. All the changes are applied as one undo step.

Main options:

- Name: the variable, or the feature value the row sets.
- Value / Equation: a number with units, or a formula starting with `=`.
- Evaluates To: the result.
- Comments: a note for yourself.
- Delete Row: removes the selected row. A deleted equation keeps its current number as plain text.

What a formula can use:

- Numbers with units, and other names in quotes: `="Width" / 2`.
- The functions listed in [typing-values.md](typing-values.md), plus `asin`, `acos`, `atan`, `atan2`, `floor` and `ceil`.
- Comparisons `<`, `>`, `<=`, `>=`, `==` and `!=`, which give 1 or 0.
- `if(condition, then, else)`, and `and`, `or`, `not`.

Tips:

- The manager does not block the window. While it is open, double click a dimension in the view to put its name into the cell you are editing.
- Units stay strict in formulas: write `="Width" > 40mm`, not `> 40`.

Common errors:

- A circular reference: two or more values use each other. Every value in the loop shows an error. Change one of them to a plain value.
- "Uses ..., which has an error": fix the value it names first. Every other value still works.

## Feature values

Every typed value of a feature and every sketch dimension has a name of the form `value@Feature name`. For example, the depth of Extrude 1 is `"depth@Extrude 1"`, and dimension d1 of Sketch 1 is `"d1@Sketch 1"`.

1. Open the equations manager.
2. In the Equations section, type the feature value as the name, for example `depth@Extrude 1`.
3. Type the formula, for example `="Width" / 4`.
4. Click OK. The feature now follows the formula.

Tips:

- Use a feature value in other formulas too: `="depth@Extrude 1" * 2`.
- The feature id also works, for example `"depth@f6"`. It keeps working after a rename.

When you rename a feature or sketch, formulas that use its values follow the new name. For example `"depth@Extrude 1"` becomes `"depth@Base"`. Undo puts both back. Names that only start the same, such as "Extrude 10", are not changed.

## Named values

Give a dimension or a feature value a name, so formulas read well: `"wall@Shell 1"` instead of `"thickness@Shell 1"`.

1. In a sketch, select the dimension and type the name in the **Name** field of the Dimension panel.
2. In a feature's property panel, right click a value field and choose **Name This Value...**.
3. A name starts with a letter and has only letters, digits and underscores. Clear it to go back to the automatic name.

The equations manager and the design table column headers show the name. The automatic name keeps working in formulas. Renaming a named value rewrites every formula that used the old name, in the same undo step.

**Show All Dimensions** (View menu, or right click the part name in the tree) shows every sketch dimension and feature value of the part on the model at once; double click one to change it. Run it again to go back to showing only the selected feature's values. A named value's label starts with its name.

## Suppression formulas

A suppression formula turns a feature on or off from a condition.

1. Open the equations manager.
2. In the Feature Values section, type the feature's name, for example `Holes`.
3. Type a formula. Any result other than 0 means suppressed. The names `suppressed` and `unsuppressed` stand for 1 and 0.
4. Example: `=if("Width" > 80mm, unsuppressed, suppressed)` keeps the holes only on wide plates.
5. Click OK.

## Variables read from a CSV table

A variable can take its value from one cell of a CSV table, such as a list of screw sizes.

1. In the equations manager, click the variable's row.
2. Click **Read from CSV...** and choose the CSV file.
3. Enter the row: a label from the first column (such as M6), or a row number (1 is the first row under the header).
4. Enter the column: its header (such as Head). Case does not matter.
5. The value is read at once. Click OK to keep it.

The file is read again each time the part opens and on Rebuild (Ctrl+B). If the file has moved, FDCAD looks for a file of the same name next to the part. If the file cannot be read, the variable keeps the value read last and the status line says why. Typing another value for the variable stops reading it from the file; choosing Read from CSV and cancelling the file choice changes nothing.

## Equations in a text file

The equations manager can save its rows to a text file and read them back, so one file can set the sizes of several parts.

- Export...: saves every variable and equation to a text file.
- Import...: reads a text file into the manager. A row with the same name is replaced, new rows are added, and other rows stay. Click OK to apply it.
- Link...: reads the file now, and again each time the part opens and on Rebuild (Ctrl+B). The manager shows the linked file's name. If the file has moved, FDCAD looks for a file of the same name next to the part.
- Remove Link: the part stops reading the file. The values stay as they are.

The file has one row per line, in three sections:

```
# FDCAD equations
[variables]
"Width" = 40mm
"Depth" = ="Width" / 2  // half the width
[suppression]
"Holes" = =if("Width" > 80mm, unsuppressed, suppressed)
[equations]
"depth@Extrude 1" = ="Depth"
```

Lines starting with `#` are notes. Text after `//` is the row's comment. Rows for features or values the part does not have are left out, and the message names them.

## Configurations

**Configurations** opens the Configurations tab. Each configuration has its own values and its own suppressed features.

1. Choose Tools, **Configurations**, or open the Configurations tab in the left panel.
2. Click Add Configuration. It copies the active values and shows the new configuration.
3. Change values in the feature panels or the equations manager.
4. Double click a configuration, or click Show Configuration, to switch to it.

When you open a part whose file has damaged configuration entries, a warning bar says what was left out, such as an entry with no name or an active configuration that was not found. A configuration whose name repeats another or breaks the name rules is renamed with a number (the second "Long" becomes "Long 2"). Save the part to keep the fixed names.

Main options:

- Add Configuration, Rename and Delete. Names are case sensitive: "Long" and "long" are two configurations.
- Show Configuration: makes the selected one active. The active one shows in bold.
- Design Table: opens the design table.
- Preview: builds the selected configuration on a copy and shows it in a small window, without making it active. The part you are working on does not change.
- Own Colours (Colours by Configuration): keeps face, feature and body colours for each configuration. While it is on, colours you pick change only the configuration that is shown. Click it again to make every configuration use the colours shown.

Tips:

- The last configuration cannot be deleted.
- Right click a feature in the feature tree and choose Suppress in This Configuration to suppress it in the active configuration only.
- Each step is undoable.

## Scopes: This Configuration, All Configurations, Chosen Configurations

When a part has two or more configurations, the right click menu of every value field has a Configurations submenu. It says which configurations your next change applies to.

1. Right click a value field in a property panel.
2. Choose Configurations, then one of:
   - This Configuration: only the active configuration gets the new value.
   - All Configurations: every configuration gets the new value. The value is shared again.
   - Chosen Configurations...: tick the configurations that get the new value.
3. Type the new value and click OK.

Tips:

- Without a choice, a value that already differs between configurations changes only in the active one. A value that is shared changes in all of them.
- The field's tooltip shows the scope you chose.

## Design Table

**Design Table** shows every configuration as a row and every configured value as a column.

1. Choose Tools, **Design Table**, or click Design Table on the Configurations tab.
2. Click Add Column. At the Parameter prompt, pick or type a value: a variable, a feature value, a sketch dimension or a suppression.
3. Click Add Row to add a configuration. It is named Configuration 1, Configuration 2 and so on. Type a new name in the Configuration column if you like.
4. Fill in the cells.
5. Click OK. The table is applied as one undo step.

Columns use these names:

- `var.Width`: the variable Width.
- `f6.depth`: the depth of the feature with id f6.
- `f5.d1`: dimension d1 of sketch f5.
- `f9.suppressed`: whether feature f9 is suppressed.

A CSV for Import CSV must use these column names, not feature or variable names. Export CSV gives a file to start from. A cell with a choice that does not exist shows as an error on the feature when the part rebuilds.

What a cell can hold:

- A value or formula for typed values.
- `S` or `U` for suppressed or unsuppressed.
- `true` or `false` for tick boxes, and the plain word for choices.
- Empty: keep that value as it is.

Main options:

- Add Row and Delete Row: add or delete a configuration. Deleting happens when you click OK.
- Add Column and Delete Column. Deleting a column keeps the values.
- Add Values...: tick several values and add a column for each in one step. Variables and values set by a formula start ticked.
- Import CSV... and Export CSV....
- Copy Table and Paste Table: copy puts the table on the clipboard as tab separated text, ready to paste into a spreadsheet. Paste takes a table copied from a spreadsheet (tab separated) or comma separated text, so you can copy the whole table, or the configuration inputs of one part, and paste them into another part with the same features. Nothing changes until you click OK.
- Remove Table: drops the table and keeps the configurations.

Besides values, a column can hold:

- Description: a note for each configuration. It shows when you point at the configuration in the Configurations tab.
- Part Colour: the part's colour in each configuration, typed as # and six hex digits, such as #3366CC.
- A custom property, such as a part number: its text in each configuration.
- A sketch's plane: type the name of a plane, such as Top Plane, so a configuration draws the sketch on another plane.
- Whether a sketch dimension drives the sketch: true for a driving dimension, false for a reference dimension.

Click any cell of a number column: the line under the table shows how many configurations set it, and their sum, average, smallest and largest value. Empty cells are left out.

## Rules, themes and trying values

**Rules and Themes...** in the design table holds two lists.

Rules: each rule reads "if this value passes the test, that value must be one of these choices". For example: if Width > 50, Depth is one of 20, 30.

1. Click Add Rule. Pick the If value, the test (>, >=, <, <=, = or !=) and type the value to compare with.
2. Pick the Then value and type its choices, separated by commas.
3. Rules run from the top, so a later rule sees what an earlier one set. Use Move Up and Move Down to change the order. Untick On to turn a rule off and keep it.

When the design table is applied, the rules run in every configuration: a value that is not one of its choices is set to the first choice. After every rebuild, a rule that is not met shows in the status line, wherever the value was edited. **Apply Rules** runs the rules in every configuration at once, as one undo step.

Themes: a theme sets several values at once, such as a material's thickness and colour. Each row gives a theme name, a value and what to set it to; rows with the same name make one theme. Add the Theme column to the design table and type a theme's name in a row: the row's empty cells take the theme's values, and a column is added for each value the theme sets. Cells you type yourself win over the theme.

**Try Row** builds the values of the row you clicked, with the rules run, on a copy and shows it in a small window. No configuration is added and the part does not change.

## Design tables with CSV

A CSV file lets you edit the table in a spreadsheet.

1. Click Export CSV... to save the table.
2. Edit the file. The first row is `Configuration` and the column names. Each other row is one configuration.
3. Click Import CSV... to read it back. It replaces the table in the editor.
4. Click OK.

Example:

```
Configuration,var.D,var.L
Short,6,20
Long,6,40
```

Tips:

- A configuration with no row in the imported file is deleted when you click OK.
- The tutorial [configured-bolt-family.md](tutorials/configured-bolt-family.md) builds a bolt family this way.

Common errors:

- "Design table not applied": a cell is wrong. The message names its row and column. Nothing changes until you fix it.

## Custom properties

**Tools, Custom Properties** keeps named values with the part, such as a description, part number or revision. Each row is **Text**, **Number**, **Date** (typed as YYYY-MM-DD) or **Yes or No**. A value starting with = is a formula; it can use the part's variables, feature values and the part's own `"volume@Part"` (mm3), `"area@Part"` (mm2) and `"mass@Part"` (grams, from the part's Material). **In <configuration> only** sets a value used only while that configuration is active. **Work Out** shows the results. Plain number rows can be used in equations as `"Width@Properties"`. Exported 3MF files carry the properties.

## The printer's fit in formulas

Formulas can use the fit of the printer chosen in Preferences, Printing: `"fit_tolerance@Printer"` is the gap per side, and `"clearance_fit@Printer"`, `"slip_fit@Printer"` and `"press_fit@Printer"` are how much each fit preset adds to a hole's diameter. For example, a peg hole typed as `=8mm + "slip_fit@Printer"` follows the printer: change printer and every part that uses it rebuilds.

## Exporting every configuration

**File, Export, Export Configurations** writes one file per configuration. Tick the configurations, choose **Files** (STEP, STL, 3MF or part files) and a **Folder**. Each file is named after the part and the configuration, for example `Bracket Long.step`. The work runs in the background and the open part stays on its configuration. `Export log.txt` in the folder lists each configuration and whether it was written; a configuration that cannot be built is listed with the reason, and the others are still written. STL and 3MF use the part's saved mesh settings.

## Working in the equations manager

- While you type a formula, matching names and functions are offered in a list; pick one to put it in.
- Type in **Filter rows** to show only rows whose name, formula or comment hold the text. **Sort** puts each section's rows in name order.
- Select several rows with Ctrl or Shift and press Delete to remove them together.
- **Disable** keeps the selected equations but stops using them: the value keeps its current number until you enable the equation again (choose Disable again when all selected rows are disabled).
- **Replace Name**: when a row uses a name that no longer exists, for example after a feature was deleted, select the row and pick the name to use instead.

## Tick boxes set by formulas

A feature's tick boxes (Reverse, Merge result, Direction 2 and the others) can follow a formula, like suppression. In the equations manager's **Feature Values** section, type the tick box name and the feature, for example `reverse@Extrude 1`, then a formula that gives true or false: `=if("Width" > 50mm, true, false)`. Nonzero means ticked. The tick follows the formula on every rebuild, so a tick changed in the panel goes back to the formula's answer; delete the row to set it by hand again.

## Linked configurations

**Add Linked** in the configurations panel makes a new configuration that stays linked to the active one (its parent). Values you do not change in the child follow the parent: change the parent's depth and the child changes too. Values you change while the child is active become the child's own and stop following; set one back to the parent's value to make it follow again. The list shows "linked to" and how many own values each child has. A feature you add while a linked child is active is suppressed in the other configurations, so it belongs to that child. Deleting the parent leaves its children as ordinary configurations.

## Allowed values

In the equations manager, click a global variable and press **Allowed Values**. Type a list such as `10, 20, 30` or a range such as `5..50` (either end can be left empty: `5..` means 5 or more). Values are in the part's units, or degrees for an angle. After every rebuild, if the variable's value is not allowed, the status bar says so and what to do. FDCAD never changes the value for you. Leave the box empty to allow any value again.

## Goal Seek and Sweep

**Goal Seek and Sweep** (Tools menu) tries a variable at different values and reads a measured value each time: the part's volume, area or mass (mass needs a part material), or a value a Measurement or Bounding Box feature measures.

1. Pick the **Variable** and the **Measured value**.
2. In **Find**, choose **Goal Seek** to find the value that reaches a **Target**, or **Sweep** to list the result at each of a number of **Steps**.
3. **From** and **To** give the range to search or step through, in the part's unit (degrees for angles). They start at half the variable's value either side of it.
4. Click **Run**. Each trial rebuilds a copy of the part in the background; **Stop** ends it after the current trial.
5. Goal Seek shows the value it found and every trial. For a sweep, pick a row. Click **Use Value** to set the variable; the part rebuilds and Undo puts the old value back.

Measured values are in millimetres, mm^2, mm^3 and grams. If the target is not reached between From and To, the message gives the nearest result: widen the range or change the target. A trial whose part fails to build shows the failing feature instead of a result.

