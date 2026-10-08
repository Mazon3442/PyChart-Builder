# Gantt chart: CSV format

Tasks as bars over weeks, with milestones and a 'today' line.

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `task` | yes | text. Task name | `task name`, `name` |
| `start` | yes | number. Week the task starts (1 = first week; may be fractional) | `start week` |
| `duration` | yes | number. Length in weeks (more than 0) | `weeks`, `duration weeks` |
| `category` | no | text. Groups tasks and gives them a color; blank = "Tasks" | `group` |
| `wbs` | no | text. Number printed inside the bar, e.g. 2.1 | - |
| `color` | no | hex color like #377EB8. Hex color for the category (the first row of each category counts) | `colour` |

Milestones aren't imported - add them in the app.

## Example

This is `examples/gantt.csv`:

```csv
wbs,task,category,start,duration
1.1,Write requirements,Planning,1,2
1.2,Choose parts,Planning,2,2
2.1,Build prototype,Build,4,4
2.2,Write firmware,Build,5,5
3.1,Test with users,Test,10,2
3.2,Fix bugs,Test,11,2
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/gantt.csv --type gantt` (add `--render` to only write the PNG).

## Common mistakes

- **A required column is missing or misspelled** - here `task` was typed as `tasks`:
  `gantt.csv is missing the column(s): task. Found: wbs, tasks, category, start, duration. See docs/csv/gantt.md.`
- **Text where a number belongs** - for example `12k` or `$5`:
  `gantt.csv row 3, column "start": must be a number (got "12k").`
- **An empty cell in a required column:**
  `gantt.csv row 5, column "task": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
