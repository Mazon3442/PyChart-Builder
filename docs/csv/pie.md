# Pie / donut chart: CSV format

Show how a whole splits into parts.

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Label` | yes | text. Name of the slice | - |
| `Value` | yes | number. Size of the slice (0 or more) | - |
| `Colour` | no | hex colour like #377EB8. Hex code like #377EB8; blank = automatic | `color` |

Slices with a value of 0 are skipped. The colour column is optional.

## Example

This is `examples/pie.csv`:

```csv
label,value
Rent,1200
Food,450
Transport,180
Fun,220
Savings,350
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/pie.csv --type pie` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Style** (default: pie). Options: pie, donut.
- **Print the percentage on each slice** (default: yes). Options: yes, no.

## Common mistakes

- **A required column is missing or misspelled** - here `Label` was typed as `labels`:
  `pie.csv is missing the column(s): Label. Found: labels, value. See docs/csv/pie.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `pie.csv row 3, column "Value": must be a number (got "12k").`
- **An empty cell in a required column:**
  `pie.csv row 5, column "Label": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
