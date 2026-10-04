# Funnel chart: CSV format

Stages of a process where each stage is smaller than the last (sales, sign-ups).

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Stage` | yes | text | `label`, `name` |
| `Value` | yes | number. Count at this stage (0 or more) | - |

List the stages from widest to narrowest.

## Example

This is `examples/funnel.csv`:

```csv
stage,value
Visited site,5000
Viewed product,2800
Added to cart,900
Checked out,420
Paid,380
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/funnel.csv --type funnel` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Print the share of the first stage** (default: yes). Options: yes, no.

## Common mistakes

- **A required column is missing or misspelled** - here `Stage` was typed as `stages`:
  `funnel.csv is missing the column(s): Stage. Found: stages, value. See docs/csv/funnel.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `funnel.csv row 3, column "Value": must be a number (got "12k").`
- **An empty cell in a required column:**
  `funnel.csv row 5, column "Stage": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
