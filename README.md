# PyChart Builder

Make charts from your keyboard. Type in your data (or load a CSV file), press **F5**, and get a
PNG you can drop into a document or slide. It runs in a terminal window on Windows and Linux (macOS
works from source), and 17 chart types are built in.

## Get it

Download the file for your system from the **Releases** page:

| System  | File                        | How to start it |
|---------|-----------------------------|-----------------|
| Windows | `gantt-builder-windows.exe` | Double-click it, or run `.\gantt-builder-windows.exe` in Windows Terminal or PowerShell. Windows may show a SmartScreen warning because the file isn't code-signed: choose *More info → Run anyway*. |
| Linux   | `gantt-builder-linux`       | `chmod +x gantt-builder-linux`, then `./gantt-builder-linux` |

You don't need Python or anything else installed. (The files are still called "gantt"; they'll be
renamed.)

## Your first chart

1. Start the app and pick a chart type.
2. Give it a name.
3. Add your data on the **Data** tab. Press `a` to add a row, `Enter` to edit one.
4. Press **F5** to draw the chart, then **F6** to open the PNG.

Press **Ctrl+S** to save (switching to another chart saves for you). The next time you start the app it reopens the chart
you were last working on.

## Charts

| Chart | Good for | Data |
|---|---|---|
| **Gantt chart** | Project schedules, with milestones and a "today" line | tasks, weeks |
| **Bar / column** | Comparing categories (grouped, stacked, horizontal) | label + numbers |
| **Line** | Change over time or steps | label + numbers |
| **Pie / donut** | Parts of a whole | label, value |
| **Area** | Totals over time (stacked or not) | label + numbers |
| **Scatter / bubble** | Relationships between two numbers | x, y, group, size |
| **Histogram** | How a set of numbers is spread out | values |
| **Box plot** | Comparing the spread of groups | group, value |
| **Heatmap** | Two categories against a number | row, column, value |
| **Timeline / roadmap** | Events on a date line | date, label |
| **Burndown** | Work remaining against the ideal pace | day, remaining |
| **Waterfall** | A value rising and falling to a total | label, change |
| **Funnel** | Stages that shrink (sales, sign-ups) | stage, value |
| **Pareto** | The vital few causes | label, value |
| **Radar / spider** | Several measures at once | label + numbers |
| **Treemap** | Sizes, optionally nested | label, value, parent |
| **Org chart** | Who reports to whom | id, label, parent |

Each chart has a **Settings** tab, one or more data tabs, and a **Preview** tab. The Gantt chart has
Categories, Tasks and Milestones; the others have a **Data** tab. Bar, line, area and radar charts
also have a **Series** tab, with one row per set of bars or lines. Colours are picked for you; choose
one from the swatches if you like. You never need to type a hex code.

## Keys

| Key | Action |
|-----|--------|
| `a` | Add a row (on a data tab) |
| `Enter` | Edit the selected row |
| `d` | Delete the selected row |
| `[` / `]` | Move the row up / down |
| `←` / `→` | Switch tabs (inside a text box they move the cursor; press `↑` to get back to the tab bar) |
| `↑` / `↓` | Move between boxes and list items in forms and menus |
| `Ctrl+S` | Save |
| `F5` | Draw the chart and save the PNG |
| `F6` | Open the PNG in your image viewer |
| `Ctrl+L` | Import a CSV file into this chart (replaces its data) |
| `Ctrl+P` | The menu: everything below, plus theme and quit. Type to search. |
| `Ctrl+Q` | Quit |

**Ctrl+P** lists, in order: Projects, New chart, Save project as, Save, Export PNG, View PNG,
the two CSV imports, CSV format help, Theme and Quit. Type `Open project:` and a name to jump
straight to a saved chart.

## Your charts and files

Each chart is one `.json` file in `Documents/PyGantt-Builder/`, and its PNG is written next to it.

In **Ctrl+P → Projects** you can open, create, copy and **delete** charts (select one and press
`d`; it asks before deleting, and deleted charts can't be recovered). To keep charts somewhere else,
set the `PYGANTT_PROJECTS` environment variable to that folder. You can also open a file directly:
`./gantt-builder-linux path/to/chart.json`. A ready-made example is in
[`examples/deer_alarm.json`](examples/deer_alarm.json).

## Loading data from a CSV file

Any chart can be built from a CSV file saved from Excel, Google Sheets or LibreOffice.

- **Ctrl+L** (or **Ctrl+P → Import CSV into this chart**) replaces the open chart's data.
- **Ctrl+P → Import CSV as a new chart** starts a new chart from the file.

Both open your system's file dialog, already filtered to `.csv` files. Windows and macOS have one
built in. On Linux the app uses `zenity` (GTK: Thunar, GNOME, XFCE) or `kdialog` (KDE) if either is
installed, for example `sudo pacman -S zenity` or `sudo apt install zenity`. Without one, the app asks
you to type or paste the file's path instead.

The columns each chart expects, with examples and the error messages you might see, are in
[docs/csv/](docs/csv/README.md). **Ctrl+P → CSV format help** shows them inside the app. Sample
files for every chart are in [examples/](examples/).

You can also make a PNG straight from a CSV without opening the editor:

```
./gantt-builder-linux data.csv --type bar --render   # writes data.png
./gantt-builder-linux --list-types                   # the chart type names
```

## If something doesn't work

- **F6 does nothing, or no image appears.** The app asks your system to open the PNG with the default
  viewer for PNG files. If that program isn't installed, the app shows an error. On Linux, set one
  with `xdg-mime default <viewer>.desktop image/png`. The window may also open on another workspace.
- **No file dialog when importing a CSV (Linux).** Install `zenity` or `kdialog`, as above. Until you
  do, typing the path works.
- **A function key does nothing.** Some terminals and desktops capture F-keys. Use the **Ctrl+P**
  menu instead; it has Export PNG and View PNG.
- **A CSV won't load.** The message says which row or column is wrong. See
  [docs/csv/](docs/csv/README.md) for what each chart needs.

---

## For developers

Run from source (Python 3.10+; the code is tested on 3.12):

```
pip install -r requirements.txt
python chart_app.py [project.json]
```

Tests, and regenerating the CSV docs after changing a chart's columns:

```
pip install -r requirements-dev.txt
python -m pytest tests
python -m charts.docs
```

The chart types live in `charts/`.

**Releases.** Pushing to GitHub runs `.github/workflows/build.yml`: it runs the tests, builds the
Windows and Linux binaries with PyInstaller, and smoke-tests each by rendering sample charts.
Pushing a tag that starts with `v` (such as `v2.3`) publishes both binaries as a GitHub Release.
To build for your own OS: `pip install -r requirements.txt pyinstaller`, then `python build.py`
(output in `dist/`). PyInstaller can't cross-compile.
