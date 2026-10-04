# Importing charts from CSV

Every chart type can be built from a CSV file - a plain-text table you can save from Excel,
Google Sheets, LibreOffice or Numbers.

## Rules that apply to every chart

- **First row = column names.** The names tell the app what each column is.
- **Names are forgiving.** `Task Name`, `task_name` and `TASK-NAME` are the same thing.
  Extra columns that the chart doesn't use are ignored.
- **Encoding:** UTF-8. In Excel choose *Save As → CSV UTF-8 (Comma delimited)*. Google Sheets and
  LibreOffice save UTF-8 by default. Commas, semicolons or tabs may separate the columns.
- **Numbers:** plain digits with `.` as the decimal point - `12`, `3.5`, `-4`. No thousands separators,
  currency symbols or percent signs (`1200`, not `$1,200`).
- **Dates:** `YYYY-MM-DD`, for example `2026-08-24`. Set the cell format to *text* in Excel, or it may
  turn them into `8/24/26`.
- **Blank lines** are skipped. A cell that the chart needs but you left empty is an error.
- **All or nothing:** if anything is wrong the whole import is refused and nothing changes. The error
  message names the file, the row and the column.

Row numbers in messages count the header as row 1, so the first data row is row 2 - the same numbers
your spreadsheet shows.

## Two shapes of file

- **Wide** (bar, line, area, radar): the first column is the label of each row and every other column is
  one series of numbers. The column header becomes the series name in the legend.
- **Long** (everything else): one row per item, with named columns.

## Importing

- In the app, press **Ctrl+P** and choose **Import CSV as a new chart** (you pick the type), or
  **Import CSV into this chart** to replace the data of the chart you have open. Titles and settings are kept.
- From the command line:
  `python chart_app.py data.csv --type bar` opens the editor with the data loaded, and adding `--render`
  just writes the PNG next to the CSV file.
- **Ctrl+P → CSV format help** shows the expected columns for the chart you have open.

## The chart types

| Type (`--type`) | Chart | Shape | Page |
|---|---|---|---|
| `gantt` | Gantt chart | long | [gantt.md](gantt.md) |
| `bar` | Bar / column chart | wide | [bar.md](bar.md) |
| `line` | Line chart | wide | [line.md](line.md) |
| `pie` | Pie / donut chart | long | [pie.md](pie.md) |
| `area` | Area chart | wide | [area.md](area.md) |
| `scatter` | Scatter / bubble chart | long | [scatter.md](scatter.md) |
| `histogram` | Histogram | long | [histogram.md](histogram.md) |
| `boxplot` | Box plot | long | [boxplot.md](boxplot.md) |
| `heatmap` | Heatmap | long | [heatmap.md](heatmap.md) |
| `timeline` | Timeline / roadmap | long | [timeline.md](timeline.md) |
| `burndown` | Burndown chart | long | [burndown.md](burndown.md) |
| `waterfall` | Waterfall chart | long | [waterfall.md](waterfall.md) |
| `funnel` | Funnel chart | long | [funnel.md](funnel.md) |
| `pareto` | Pareto chart | long | [pareto.md](pareto.md) |
| `radar` | Radar / spider chart | wide | [radar.md](radar.md) |
| `treemap` | Treemap | long | [treemap.md](treemap.md) |
| `orgchart` | Org chart / hierarchy | long | [orgchart.md](orgchart.md) |
