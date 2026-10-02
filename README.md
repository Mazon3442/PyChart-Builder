# Gantt chart builder

A terminal app: enter your tasks, press **F5**, get a PNG Gantt chart.
Works on Linux and Windows.

## Run it

Download the file for your system from the **Releases** page (or the latest
**Actions** run → Artifacts):

| System  | File                       | How to run |
|---------|----------------------------|------------|
| Windows | `gantt-builder-windows.exe` | Open **Windows Terminal** (or PowerShell) in the folder and run `.\gantt-builder-windows.exe`. Double-clicking works too. Windows may show a "SmartScreen" warning because the file isn't code-signed: *More info → Run anyway*. |
| Linux   | `gantt-builder-linux`       | `chmod +x gantt-builder-linux` then `./gantt-builder-linux` |

Charts are saved in `Documents/PyGantt-Builder/`, one `.json` file per chart, and the
PNG is written next to it. The app reopens your most recent chart. Press **Ctrl+P** (Settings) to
switch between charts, start a new one, or save a copy; the same menu changes the theme. You can also open any file
directly: `./gantt-builder-linux path/to/chart.json`. Try the included `deer_alarm.json`
for an example. (Set the `PYGANTT_PROJECTS` environment variable to keep charts in a
different folder.)

No Python needed for the downloads. To run from source instead:

```
pip install -r requirements.txt
python gantt_app.py [project.json]
```

## Using it

Tabs: **Settings**, **Categories**, **Tasks**, **Milestones**, **Preview**.
Start with Categories (they give bars their colour), then Tasks. Colours are picked for
you automatically. Choose one from the swatches if you like; no hex codes needed. A new
task starts the week after the previous one ends.

| Key | Action |
|-----|--------|
| `a` | Add (on a Categories / Tasks / Milestones tab) |
| `Enter` | Edit the selected row |
| `d` | Delete the selected row |
| `[` / `]` | Move the row up / down (row order = order on the chart) |
| `←` / `→` | Switch tabs (inside a text box they move the cursor; press `↑` to get back to the tab bar) |
| `↑` / `↓` | Move between boxes on the Settings tab and in dialogs |
| `Ctrl+P` | **Settings** menu: change theme, open another chart, new project, save a copy, save, export, quit |
| `Ctrl+S` | Save the project |
| `F5` | Export the PNG |
| `F6` | Open the PNG |
| `Ctrl+Q` | Quit |

Tip: `python gantt_app.py project.json --render` writes the PNG without opening the editor.

## Building the executables

Push to GitHub: the workflow in `.github/workflows/build.yml` builds the Windows
and Linux binaries and renders the sample chart with each as a smoke test.
Download them from the run's Artifacts. Push a tag such as `v1.0` to publish
both as a GitHub Release.

To build for your own OS locally: `pip install -r requirements.txt pyinstaller`
then `python build.py` (output in `dist/`). PyInstaller can't cross-compile.
