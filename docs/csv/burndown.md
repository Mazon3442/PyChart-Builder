# Burndown chart: CSV format

Work remaining over time, against the ideal pace (sprints, projects).

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Day` | yes | text. Name of the day, e.g. 1, Mon, Jan 6 | `label`, `period`, `date`, `label` |
| `Remaining` | yes | number. Work left (story points, hours, tasks) | - |

Rows are plotted in file order. The ideal line is drawn for you.

## Example

This is `examples/burndown.csv`:

```csv
day,remaining
Day 0,40
Day 1,38
Day 2,35
Day 3,35
Day 4,28
Day 5,24
Day 6,17
Day 7,12
Day 8,6
Day 9,2
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/burndown.csv --type burndown` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Draw the ideal line (straight down to zero)** (default: yes). Options: yes, no.
- **X-axis label (optional)** (default: Day).
- **Y-axis label (optional)** (default: Work remaining).

## Common mistakes

- **A required column is missing or misspelled** - here `Day` was typed as `days`:
  `burndown.csv is missing the column(s): Day. Found: days, remaining. See docs/csv/burndown.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `burndown.csv row 3, column "Remaining": must be a number (got "12k").`
- **An empty cell in a required column:**
  `burndown.csv row 5, column "Day": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
