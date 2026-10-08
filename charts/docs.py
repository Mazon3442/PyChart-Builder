"""
Generates the CSV documentation (docs/csv/*.md) from the chart type declarations and the files
in examples/, so what the docs say is always what the importer does.

    python -m charts.docs        rewrite docs/csv/
"""
from __future__ import annotations

from pathlib import Path

from . import CHART_TYPES
from .base import ChartType, Column
from .table import TableChart, parse_cell

ROOT = Path(__file__).resolve().parent.parent
KIND_TEXT = {"text": "text", "number": "number", "int": "whole number", "date": "date (YYYY-MM-DD)",
             "color": "hex color like #377EB8", "choice": "one of the listed words"}

SHARED_RULES = """\
# Importing charts from CSV

Every chart type can be built from a CSV file - a plain-text table you can save from Excel,
Google Sheets, LibreOffice or Numbers.

## Rules that apply to every chart

- **First row = column names.** The names tell the app what each column is.
- **Names are forgiving.** `Task Name`, `task_name` and `TASK-NAME` are the same thing.
  Extra columns that the chart doesn't use are ignored.
- **Encoding:** UTF-8. In Excel choose *Save As → CSV UTF-8 (Comma delimited)*. Google Sheets and
  LibreOffice save UTF-8 by default. Commas, semicolons or tabs may separate the columns.
- **Numbers:** plain digits with `.` as the decimal point - `12`, `3.5`, `-4`. No thousands separators,
  currency symbols or percent signs (`1200`, not `$1,200`).
- **Dates:** `YYYY-MM-DD`, for example `2026-08-24`. Set the cell format to *text* in Excel, or it may
  turn them into `8/24/26`.
- **Blank lines** are skipped. A cell that the chart needs but you left empty is an error.
- **All or nothing:** if anything is wrong the whole import is refused and nothing changes. The error
  message names the file, the row and the column.

Row numbers in messages count the header as row 1, so the first data row is row 2 - the same numbers
your spreadsheet shows.

## Two shapes of file

- **Wide** (bar, line, area, radar): the first column is the label of each row and every other column is
  one series of numbers. The column header becomes the series name in the legend.
- **Long** (everything else): one row per item, with named columns.

## Importing

- In the app, press **Ctrl+P** and choose **Import CSV as a new chart** (you pick the type), or
  **Import CSV into this chart** to replace the data of the chart you have open. Titles and settings are kept.
- From the command line:
  `python chart_app.py data.csv --type bar` opens the editor with the data loaded, and adding `--render`
  just writes the PNG next to the CSV file.
- **Ctrl+P → CSV format help** shows the expected columns for the chart you have open.

## The chart types

| Type (`--type`) | Chart | Shape | Page |
|---|---|---|---|
"""


def _columns_table(chart: ChartType) -> str:
    rows = ["| Column header | Required | What goes in it | Also accepted as |", "|---|---|---|---|"]
    for c in chart.csv_columns():
        what = KIND_TEXT.get(c.kind, c.kind) + (f". {c.help}" if c.help else "")
        also = ", ".join(f"`{a}`" for a in (c.key, *c.aliases) if a.lower() != c.label.lower()) or "-"
        rows.append(f"| `{c.label}` | {'yes' if c.required else 'no'} | {what} | {also} |")
    return "\n".join(rows)


def _problem(col: Column, bad: str) -> str | None:
    try:
        parse_cell(col, bad)
    except ValueError as e:
        return f"{e} (got \"{bad}\")"
    return None


def _mistakes(chart: ChartType, example: str) -> list[str]:
    name = f"{chart.id}.csv"
    header = example.splitlines()[0].split(",")
    out = []
    if chart.csv_layout == "wide":
        out.append(f'- **A cell with text in a number column** - for example `12k` or `$5`:\n  `{name} row 3, column '
                   f'"{header[1]}": must be a number (got "12k").`')
        out.append(f'- **A column without a header** (it would have no series name):\n  `{name}, column 3: the header is '
                   "empty. Every column needs a name (it becomes the series name in the legend).`")
        out.append(f'- **The same series name twice:**\n  `{name}, column 3: the name "{header[1]}" appears twice in the header.`')
        out.append(f'- **A row with no label** in the first column:\n  `{name} row 4, column "{header[0]}": the label is empty.`')
        return out
    cols = chart.csv_columns()
    required = [c for c in cols if c.required]
    target = required[0]
    names = {a.lower() for a in (target.key, target.label, *target.aliases)}
    found = [f"{h}s" if h.lower() in names else h for h in header]  # the same header with a typo
    typo = next(f for f, h in zip(found, header) if f != h)
    out.append(f"- **A required column is missing or misspelled** - here `{target.label}` was typed as "
               f"`{typo}`:\n  `{name} is missing the column(s): {target.label}. "
               f"Found: {', '.join(found)}. See docs/csv/{chart.id}.md.`")
    for c in cols:
        if c.kind in ("number", "int") and c.required:
            out.append(f'- **Text where a number belongs** - for example `12k` or `$5`:\n  `{name} row 3, column '
                       f'"{c.label}": {_problem(c, "12k")}.`')
            break
    for c in cols:
        if c.kind == "date":
            out.append(f'- **A date in the wrong format** - for example `24/08/2026`:\n  `{name} row 3, column '
                       f'"{c.label}": {_problem(c, "24/08/2026")}.`')
            break
    for c in cols:
        if c.required and c.kind in ("text", "date", "number"):
            out.append(f'- **An empty cell in a required column:**\n  `{name} row 5, column "{c.label}": can\'t be empty.`')
            break
    return out


def render_page(chart: ChartType) -> str:
    example = (ROOT / "examples" / f"{chart.id}.csv").read_text(encoding="utf-8").strip("\n")
    wide = chart.csv_layout == "wide"
    parts = [f"# {chart.label}: CSV format\n", f"{chart.description}\n"]
    if wide:
        parts.append("## What the file looks like\n\n"
                     "**Wide format.** The first column holds the label of each row (the header can be anything, "
                     "e.g. `label`). Every other column is one **series** of numbers, and its header is the series "
                     "name shown in the legend. Leave a cell empty if there is no value for that row.\n")
    else:
        parts.append("## Columns\n\nThe first row must contain these column names, in any order.\n\n"
                     + _columns_table(chart) + "\n")
    if chart.csv_notes:
        parts.append(f"{chart.csv_notes}\n")
    parts.append(f"## Example\n\nThis is `examples/{chart.id}.csv`:\n\n```csv\n{example}\n```\n")
    parts.append("## Import it\n\n"
                 "- In the app: **Ctrl+P → Import CSV as a new chart** (or **Import CSV into this chart** to replace "
                 "the data of the chart you have open).\n"
                 f"- From the command line: `python chart_app.py examples/{chart.id}.csv --type {chart.id}` "
                 "(add `--render` to only write the PNG).\n")
    if isinstance(chart, TableChart) and chart.settings:
        lines = []
        for s in chart.settings:
            default = f" (default: {s.default})" if str(s.default) else ""
            options = f" Options: {', '.join(s.choices)}." if s.choices else ""
            lines.append(f"- **{s.label}**{default}.{options}")
        parts.append("## Settings (set in the app, not in the CSV)\n\n" + "\n".join(lines) + "\n")
    parts.append("## Common mistakes\n\n" + "\n".join(_mistakes(chart, example)) + "\n\n"
                 "More rules that apply to every chart: [docs/csv/README.md](README.md).\n")
    return "\n".join(parts)


def render_index() -> str:
    rows = [f"| `{c.id}` | {c.label} | {'wide' if c.csv_layout == 'wide' else 'long'} | [{c.id}.md]({c.id}.md) |"
            for c in CHART_TYPES.values()]
    return SHARED_RULES + "\n".join(rows) + "\n"


def all_pages() -> dict[str, str]:
    pages = {"README.md": render_index()}
    pages.update({f"{c.id}.md": render_page(c) for c in CHART_TYPES.values()})
    return pages


def write_all(folder: Path = ROOT / "docs" / "csv") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in all_pages().items():
        (folder / name).write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    write_all()
    print(f"Wrote {len(CHART_TYPES) + 1} pages to {ROOT / 'docs' / 'csv'}")
