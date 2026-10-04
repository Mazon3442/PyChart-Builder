# Pareto chart: CSV format

Bars sorted largest to smallest plus a running-total line - find the vital few causes.

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Label` | yes | text | `category`, `cause` |
| `Value` | yes | number. Count or amount (0 or more) | `count` |

Rows are sorted largest first for you.

## Example

This is `examples/pareto.csv`:

```csv
label,value
Scratches,48
Dents,27
Wrong colour,12
Loose parts,8
Missing label,5
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/pareto.csv --type pareto` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **X-axis label (optional)**.
- **Y-axis label (optional)** (default: Count).

## Common mistakes

- **A required column is missing or misspelled** - here `Label` was typed as `labels`:
  `pareto.csv is missing the column(s): Label. Found: labels, value. See docs/csv/pareto.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `pareto.csv row 3, column "Value": must be a number (got "12k").`
- **An empty cell in a required column:**
  `pareto.csv row 5, column "Label": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
