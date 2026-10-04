# Treemap: CSV format

Rectangles sized by value, optionally grouped into parents (budgets, disk usage).

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Label` | yes | text | - |
| `Value` | no | number. Size (more than 0). Leave blank for a parent: its size is the sum of its children. | - |
| `Parent` | no | text. Label of the row this one sits inside; blank = top level | - |

Leave value empty for a parent row - its size is the sum of its children. A parent must match another row's label exactly.

## Example

This is `examples/treemap.csv`:

```csv
label,value,parent
Housing,,
Rent,1200,Housing
Utilities,260,Housing
Food,,
Groceries,400,Food
Eating out,180,Food
Transport,210,
Savings,350,
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/treemap.csv --type treemap` (add `--render` to only write the PNG).

## Common mistakes

- **A required column is missing or misspelled** - here `Label` was typed as `labels`:
  `treemap.csv is missing the column(s): Label. Found: labels, value, parent. See docs/csv/treemap.md.`
- **An empty cell in a required column:**
  `treemap.csv row 5, column "Label": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
