# Line chart: CSV format

Show how one or more values change across an ordered set of points (time, steps).

## What the file looks like

**Wide format.** The first column holds the label of each row (the header can be anything, e.g. `label`). Every other column is one **series** of numbers, and its header is the series name shown in the legend. Leave a cell empty if there is no value for that row.

Rows are drawn in file order, left to right.

## Example

This is `examples/line.csv`:

```csv
label,Visitors,Sign-ups
Jan,1200,90
Feb,1350,110
Mar,1280,105
Apr,1600,160
May,1750,190
Jun,2100,240
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/line.csv --type line` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Draw a dot at every point** (default: yes). Options: yes, no.
- **X-axis label (optional)**.
- **Y-axis label (optional)**.

## Common mistakes

- **A cell with text in a number column** - for example `12k` or `$5`:
  `line.csv row 3, column "Visitors": must be a number (got "12k").`
- **A column without a header** (it would have no series name):
  `line.csv, column 3: the header is empty. Every column needs a name (it becomes the series name in the legend).`
- **The same series name twice:**
  `line.csv, column 3: the name "Visitors" appears twice in the header.`
- **A row with no label** in the first column:
  `line.csv row 4, column "label": the label is empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
