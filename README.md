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

Your chart is saved as `gantt_project.json` in the folder you run it from. Give it
a different name with `./gantt-builder-linux mychart.json`. The PNG is written
next to the project file. Try the included `deer_alarm.json` for an example.

No Python needed for the downloads. To run from source instead:

```
pip install -r requirements.txt
python gantt_app.py [project.json]
```

## Using it

Tabs: **Settings**, **Categories**, **Tasks**, **Milestones**, **Preview**.
Start with Categories (they give bars their colour), then Tasks.

| Key | Action |
|-----|--------|
| `a` | Add (on a Categories / Tasks / Milestones tab) |
| `Enter` | Edit the selected row |
| `d` | Delete the selected row |
| `[` / `]` | Move the row up / down (row order = order on the chart) |
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
