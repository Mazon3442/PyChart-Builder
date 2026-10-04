# Box plot: CSV format

Compare how several groups of numbers are spread: median, quartiles and outliers.

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Group` | yes | text | `label`, `category` |
| `Value` | yes | number | - |

Rows with the same group name end up in the same box.

## Example

This is `examples/boxplot.csv`:

```csv
group,value
Class A,72
Class A,75
Class A,80
Class A,68
Class A,90
Class A,77
Class B,60
Class B,64
Class B,70
Class B,85
Class B,55
Class B,66
Class C,88
Class C,92
Class C,79
Class C,95
Class C,84
Class C,91
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/boxplot.csv --type boxplot` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Show every data point too** (default: yes). Options: yes, no.
- **X-axis label (optional)**.
- **Y-axis label (optional)**.

## Common mistakes

- **A required column is missing or misspelled** - here `Group` was typed as `groups`:
  `boxplot.csv is missing the column(s): Group. Found: groups, value. See docs/csv/boxplot.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `boxplot.csv row 3, column "Value": must be a number (got "12k").`
- **An empty cell in a required column:**
  `boxplot.csv row 5, column "Group": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
