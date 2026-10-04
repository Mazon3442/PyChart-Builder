# Waterfall chart: CSV format

How a starting value rises and falls to an end value (budgets, profit bridges).

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Label` | yes | text | - |
| `Change` | yes | number. Amount added (positive) or taken away (negative) | `amount`, `value` |

Use a negative number for a decrease. The first row is usually the starting value.

## Example

This is `examples/waterfall.csv`:

```csv
label,change
Start,1000
Sales,450
Refunds,-120
Costs,-380
Other income,90
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/waterfall.csv --type waterfall` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Add a total bar at the end** (default: yes). Options: yes, no.
- **Label for the total bar** (default: Total).
- **X-axis label (optional)**.
- **Y-axis label (optional)**.

## Common mistakes

- **A required column is missing or misspelled** - here `Label` was typed as `labels`:
  `waterfall.csv is missing the column(s): Label. Found: labels, change. See docs/csv/waterfall.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `waterfall.csv row 3, column "Change": must be a number (got "12k").`
- **An empty cell in a required column:**
  `waterfall.csv row 5, column "Label": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
