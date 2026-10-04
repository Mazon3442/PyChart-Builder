# Histogram: CSV format

How a set of numbers is spread out. Counts how many fall into each range.

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Value` | yes | number | `values`, `data`, `number`, `x` |

One measurement per row, not counts. The number of bars is set in the app.

## Example

This is `examples/histogram.csv`:

```csv
value
62
65
68
70
71
72
72
73
74
75
75
76
78
80
81
83
85
90
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/histogram.csv --type histogram` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Number of bars (bins)** (default: 10).
- **X-axis label (optional)** (default: Value).
- **Y-axis label (optional)** (default: Count).

## Common mistakes

- **A required column is missing or misspelled** - here `Value` was typed as `values`:
  `histogram.csv is missing the column(s): Value. Found: values. See docs/csv/histogram.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `histogram.csv row 3, column "Value": must be a number (got "12k").`
- **An empty cell in a required column:**
  `histogram.csv row 5, column "Value": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
