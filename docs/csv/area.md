# Area chart: CSV format

Like a line chart with the area filled in. Stack series to show a total.

## What the file looks like

**Wide format.** The first column holds the label of each row (the header can be anything, e.g. `label`). Every other column is one **series** of numbers, and its header is the series name shown in the legend. Leave a cell empty if there is no value for that row.

Rows are drawn in file order. Needs at least 2 rows.

## Example

This is `examples/area.csv`:

```csv
label,Desktop,Mobile,Tablet
Q1,40,30,10
Q2,42,38,11
Q3,41,47,12
Q4,39,58,12
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/area.csv --type area` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Stack the series** (default: yes). Options: yes, no.
- **X-axis label (optional)**.
- **Y-axis label (optional)**.

## Common mistakes

- **A cell with text in a number column** - for example `12k` or `$5`:
  `area.csv row 3, column "Desktop": must be a number (got "12k").`
- **A column without a header** (it would have no series name):
  `area.csv, column 3: the header is empty. Every column needs a name (it becomes the series name in the legend).`
- **The same series name twice:**
  `area.csv, column 3: the name "Desktop" appears twice in the header.`
- **A row with no label** in the first column:
  `area.csv row 4, column "label": the label is empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
