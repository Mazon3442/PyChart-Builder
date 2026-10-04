# Timeline / roadmap: CSV format

Events on a date line - project history, release plans, milestones.

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `Date` | yes | date (YYYY-MM-DD). YYYY-MM-DD | - |
| `Label` | yes | text | `event`, `name` |
| `Category` | no | text | `group` |

Row order doesn't matter - events are sorted by date.

## Example

This is `examples/timeline.csv`:

```csv
date,label,category
2026-01-12,Project kickoff,Planning
2026-02-02,Design approved,Planning
2026-03-16,Prototype ready,Build
2026-04-27,Beta release,Build
2026-05-18,Public launch,Release
2026-07-06,Version 2 planning,Planning
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/timeline.csv --type timeline` (add `--render` to only write the PNG).

## Common mistakes

- **A required column is missing or misspelled** - here `Date` was typed as `dates`:
  `timeline.csv is missing the column(s): Date. Found: dates, label, category. See docs/csv/timeline.md.`
- **A date in the wrong format** - for example `24/08/2026`:
  `timeline.csv row 3, column "Date": must be a date like 2026-08-24 (YYYY-MM-DD) (got "24/08/2026").`
- **An empty cell in a required column:**
  `timeline.csv row 5, column "Date": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
