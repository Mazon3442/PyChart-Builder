# Scatter / bubble chart: CSV format

Plot pairs of numbers to see relationships. Add a size column to make it a bubble chart.

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `X` | yes | number | - |
| `Y` | yes | number | - |
| `Group` | no | text | `category`, `series` |
| `Size` | no | number. Bubble size (0 or more) | - |

Leave group empty if you have one set of points. Fill in size to get bubbles.

## Example

This is `examples/scatter.csv`:

```csv
x,y,group,size
1.5,12,Cats,3
2.1,15,Cats,5
2.8,19,Cats,4
3.4,22,Cats,8
4.0,26,Dogs,10
4.6,31,Dogs,12
5.2,33,Dogs,9
6.1,41,Dogs,15
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/scatter.csv --type scatter` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Draw a straight trend line** (default: no). Options: yes, no.
- **X-axis label (optional)**.
- **Y-axis label (optional)**.

## Common mistakes

- **A required column is missing or misspelled** - here `X` was typed as `xs`:
  `scatter.csv is missing the column(s): X. Found: xs, y, group, size. See docs/csv/scatter.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `scatter.csv row 3, column "X": must be a number (got "12k").`
- **An empty cell in a required column:**
  `scatter.csv row 5, column "X": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
