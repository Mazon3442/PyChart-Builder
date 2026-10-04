# Org chart / hierarchy: CSV format

A tree of boxes - who reports to whom, or any parent/child structure.

## Columns

The first row must contain these column names, in any order.

| Column header | Required | What goes in it | Also accepted as |
|---|---|---|---|
| `ID` | yes | text. A short unique name, e.g. ceo or A1 | - |
| `Label` | yes | text. Text shown in the box | `name`, `title` |
| `Parent` | no | text. ID of the box above; blank = top | `reports to` |

A parent must match another row's id exactly; leave it empty for the top box. Several top boxes are allowed.

## Example

This is `examples/orgchart.csv`:

```csv
id,label,parent
ceo,Dana Reyes - CEO,
cto,Lee Park - CTO,ceo
cfo,Sam Ortiz - CFO,ceo
dev1,Web team,cto
dev2,Mobile team,cto
acct,Accounting,cfo
pay,Payroll,acct
```

## Import it

- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace the data of the chart you have open).
- From the command line: `python chart_app.py examples/orgchart.csv --type orgchart` (add `--render` to only write the PNG).

## Settings (set in the app, not in the CSV)

- **Box width (characters)** (default: 16).

## Common mistakes

- **A required column is missing or misspelled** - here `ID` was typed as `ids`:
  `orgchart.csv is missing the column(s): ID. Found: ids, label, parent. See docs/csv/orgchart.md.`
- **An empty cell in a required column:**
  `orgchart.csv row 5, column "ID": can't be empty.`

More rules that apply to every chart: [docs/csv/README.md](README.md).
