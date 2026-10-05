# PyChart Builder

A terminal app that draws charts: enter your data (or load a CSV), press **F5**, get a PNG.
Works on Linux, Windows and macOS.

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

On first launch you pick a chart type. After that the app reopens your most recent chart;
**Ctrl+P → New chart** starts another one.

## Run it

Download the file for your system from the **Releases** page (or the latest
**Actions** run → Artifacts):

| System  | File                       | How to run |
|---------|----------------------------|------------|
| Windows | `gantt-builder-windows.exe` | Open **Windows Terminal** (or PowerShell) in the folder and run `.\gantt-builder-windows.exe`. Double-clicking works too. Windows may show a "SmartScreen" warning because the file isn't code-signed: *More info → Run anyway*. |
| Linux   | `gantt-builder-linux`       | `chmod +x gantt-builder-linux` then `./gantt-builder-linux` |

(The download names still say "gantt"; they'll be renamed.)

Charts are saved in `Documents/PyGantt-Builder/`, one `.json` file per chart, and the
PNG is written next to it. Press **Ctrl+P** (Settings) to switch between charts, start a new one,
import a CSV, or save a copy; the same menu changes the theme. You can also open any file
directly: `./gantt-builder-linux path/to/chart.json`. Try the included `deer_alarm.json`
for an example. (Set the `PYGANTT_PROJECTS` environment variable to keep charts in a
different folder.)

No Python needed for the downloads. To run from source instead:

```
pip install -r requirements.txt
python chart_app.py [project.json]
```

## Using it

Each chart has the tabs **Settings**, one or more data tabs, and **Preview**. The Gantt chart has
Categories, Tasks and Milestones; the other charts have a **Data** tab (bar, line, area and radar also
have a **Series** tab, one row per set of bars or lines, and each series becomes a column on the Data tab).
Colours are picked for you automatically; choose one from the swatches if you like. No hex codes needed.

| Key | Action |
|-----|--------|
| `a` | Add a row (on a data tab) |
| `Enter` | Edit the selected row |
| `d` | Delete the selected row |
| `[` / `]` | Move the row up / down |
| `←` / `→` | Switch tabs (inside a text box they move the cursor; press `↑` to get back to the tab bar) |
| `↑` / `↓` | Move between boxes on the Settings tab and in dialogs |
| `Ctrl+P` | **Settings** menu: theme, open another chart, new chart, import CSV, save a copy, save, export, quit |
| `Ctrl+S` | Save the project |
| `F5` | Export the PNG |
| `F6` or `Ctrl+O` | Open the PNG (Ctrl+O is for terminals that swallow F-keys) |
| `Ctrl+Q` | Quit |

## Loading data from a CSV file

Every chart can be built from a CSV file saved from Excel, Google Sheets or LibreOffice.
Press **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the
chart that's open), or from the command line:

```
python chart_app.py data.csv --type bar            open the editor with the data loaded
python chart_app.py data.csv --type bar --render   just write data.png
python chart_app.py --list-types                   see the type names
```

What each chart's columns must be called, with examples and the error messages you might see, is in
[docs/csv/](docs/csv/README.md) (**Ctrl+P → CSV format help** shows it inside the app). Ready-made
sample files for every chart are in [examples/](examples/).

## Development

```
pip install -r requirements-dev.txt
python -m pytest tests
python -m charts.docs        # regenerate docs/csv after changing a chart's columns
```

The chart types live in `charts/`; see [PLAN.md](PLAN.md) for the design.

## Building the executables

Push to GitHub: the workflow in `.github/workflows/build.yml` runs the tests, builds the Windows
and Linux binaries and renders the sample chart with each as a smoke test.
Download them from the run's Artifacts. Push a tag such as `v1.0` to publish
both as a GitHub Release.

To build for your own OS locally: `pip install -r requirements.txt pyinstaller`
then `python build.py` (output in `dist/`). PyInstaller can't cross-compile.
