# Radar / spider chart: CSV format

Compare several measures at once on a web, e.g. skills or product ratings.

## What the file looks like

**Wide format.** The first column holds the label of each row (the header can be anything, e.g. `label`). Every other column is one **series** of numbers, and its header is the series name shown in the legend. Leave a cell empty if there is no value for that row.

Each row becomes one spoke. Needs at least 3 rows.

## Example

This is `examples/radar.csv`:

```csv
label,Alex,Sam
Speed,8,6
Strength,5,9
Stamina,7,7
Skill,9,5
Teamwork,6,8
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/radar.csv --type radar` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Fill the shapes** (default: yes). Options: yes, no.

## Common mistakes

- **A cell with text in a number column** - for example `12k` or `$5`:
  `radar.csv row 3, column "Alex": must be a number (got "12k").`
- **A column without a header** (it would have no series name):
  `radar.csv, column 3: the header is empty. Every column needs a name (it becomes the series name in the legend).`
- **The same series name twice:**
  `radar.csv, column 3: the name "Alex" appears twice in the header.`
- **A row with no label** in the first column:
  `radar.csv row 4, column "label": the label is empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
