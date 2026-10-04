# Bar / column chart: CSV format

Compare values across categories. Grouped, stacked, vertical or horizontal.

## What the file looks like

**Wide format.** The first column holds the label of each row (the header can be anything, e.g. `label`). Every other column is one **series** of numbers, and its header is the series name shown in the legend. Leave a cell empty if there is no value for that row.

Rows are drawn in file order.

## Example

This is `examples/bar.csv`:

```csv
label,2024,2025,2026
North,120,135,150
South,90,95,110
East,60,80,85
West,105,100,125
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/bar.csv --type bar` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Direction** (default: vertical). Options: vertical, horizontal.
- **Several series** (default: grouped). Options: grouped, stacked.
- **Print the value on each bar** (default: no). Options: yes, no.
- **X-axis label (optional)**.
- **Y-axis label (optional)**.

## Common mistakes

- **A cell with text in a number column** - for example `12k` or `$5`:
  `bar.csv row 3, column "2024": must be a number (got "12k").`
- **A column without a header** (it would have no series name):
  `bar.csv, column 3: the header is empty. Every column needs a name (it becomes the series name in the legend).`
- **The same series name twice:**
  `bar.csv, column 3: the name "2024" appears twice in the header.`
- **A row with no label** in the first column:
  `bar.csv row 4, column "label": the label is empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
