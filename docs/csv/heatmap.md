# Heatmap: CSV format

A grid of colored cells - darker means bigger. Good for comparing two categories.

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Row` | yes | text | `y` |
| `Column` | yes | text | `col`, `x` |
| `Value` | yes | number | - |

Each row/column pair may appear only once. Missing pairs are drawn grey.

## Example

This is `examples/heatmap.csv`:

```csv
row,column,value
Mon,Morning,12
Mon,Afternoon,30
Mon,Evening,18
Tue,Morning,15
Tue,Afternoon,34
Tue,Evening,22
Wed,Morning,9
Wed,Afternoon,41
Wed,Evening,27
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/heatmap.csv --type heatmap` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Print the number in each cell** (default: yes). Options: yes, no.
- **Colors** (default: Blues). Options: Blues, Greens, Reds, YlOrRd, viridis, coolwarm.
- **X-axis label (optional)**.
- **Y-axis label (optional)**.

## Common mistakes

- **A required column is missing or misspelled** - here `Row` was typed as `rows`:
  `heatmap.csv is missing the column(s): Row. Found: rows, column, value. See docs/csv/heatmap.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `heatmap.csv row 3, column "Value": must be a number (got "12k").`
- **An empty cell in a required column:**
  `heatmap.csv row 5, column "Row": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
