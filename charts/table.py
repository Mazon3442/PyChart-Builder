"""
Framework for every chart whose data is one or more simple tables (all but Gantt).

A chart type declares its settings and tables (`Setting`, `TableSpec`, `Column`) and a
`draw()` method. Everything else - the JSON format, the editor screen, CSV import and the
documentation page - is derived from those declarations, so the pieces can't disagree.

Rows are stored as plain lists of values, aligned with the table's columns.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from rich.text import Text

import chart_core as core
from chart_core import fmt_num

from .base import ChartType, Column, CsvError, cell, norm_header, read_csv

YES_NO = ("yes", "no")


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    kind: str = "text"            # text | int | choice
    default: Any = ""
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    help: str = ""


@dataclass(frozen=True)
class TableSpec:
    key: str
    label: str
    hint: str
    columns: tuple[Column, ...] = ()
    unique: str | None = None     # key of a column whose values must not repeat


@dataclass
class TableProject:
    type: str
    title: str = ""
    output: str = ""              # "" = <project file stem>.png
    settings: dict[str, Any] = field(default_factory=dict)
    tables: dict[str, list[list[Any]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "title": self.title, "output": self.output,
                "settings": self.settings, "tables": self.tables}


# ------------------------------------------------------------ cell parsing / formatting

def parse_cell(col: Column, raw: str) -> Any:
    """Turn what the user typed into the stored value. Raises ValueError("must be ...")."""
    raw = raw.strip()
    if not raw:
        if col.required:
            raise ValueError("can't be empty")
        return None
    if col.kind in ("number", "int"):
        try:
            x = float(raw)
        except ValueError:
            raise ValueError("must be a number") from None
        if not math.isfinite(x):
            raise ValueError("must be a number")
        if col.kind == "int":
            if x != int(x):
                raise ValueError("must be a whole number")
            x = int(x)
        if col.minimum is not None:
            if col.strict and x <= col.minimum:
                raise ValueError(f"must be more than {fmt_num(col.minimum)}")
            if not col.strict and x < col.minimum:
                raise ValueError(f"must be at least {fmt_num(col.minimum)}")
        return x
    if col.kind == "date":
        try:
            return date.fromisoformat(raw).isoformat()
        except ValueError:
            raise ValueError("must be a date like 2026-08-24 (YYYY-MM-DD)") from None
    if col.kind == "choice":
        for c in col.choices:
            if c.lower() == raw.lower():
                return c
        raise ValueError("must be one of: " + ", ".join(col.choices))
    if col.kind == "color":
        raw = raw if raw.startswith("#") else "#" + raw
        if not core.HEX_RE.match(raw):
            raise ValueError("must be a hex code like #377EB8")
        return raw.upper()
    return raw


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return fmt_num(value)
    return str(value)


def parse_setting(s: Setting, raw: str) -> Any:
    raw = raw.strip()
    if s.kind == "int":
        try:
            x = float(raw)
        except ValueError:
            raise ValueError(f"{s.label} must be a number.") from None
        if x != int(x) or (s.minimum is not None and x < s.minimum):
            raise ValueError(f"{s.label} must be a whole number of at least {fmt_num(s.minimum or 0)}.")
        return int(x)
    if s.kind == "choice":
        for c in s.choices:
            if c.lower() == raw.lower():
                return c
        raise ValueError(f"{s.label} must be one of: " + ", ".join(s.choices))
    return raw


# ---------------------------------------------------------------------- chart type

class TableChart(ChartType):
    """Base for table-driven charts. Subclasses set the class attributes and implement draw()."""

    editor = "table"
    settings: tuple[Setting, ...] = ()
    tables: tuple[TableSpec, ...] = ()
    min_rows = 1
    sample: dict[str, list[list[Any]]] = {}

    # ---- declarations the editor and CSV importer read
    def table(self, key: str) -> TableSpec:
        return next(t for t in self.tables if t.key == key)

    def columns(self, project: TableProject, key: str) -> list[Column]:
        return list(self.table(key).columns)

    def main_table(self) -> TableSpec:
        return self.tables[-1]

    def csv_columns(self) -> list[Column]:
        return [] if self.csv_layout == "wide" else list(self.main_table().columns)

    def default_settings(self) -> dict[str, Any]:
        return {s.key: s.default for s in self.settings}

    # ---- project lifecycle
    def new(self, title: str) -> TableProject:
        return TableProject(self.id, title=title, settings=self.default_settings(),
                            tables={t.key: [list(r) for r in self.starter_rows(t.key)] for t in self.tables})

    def starter_rows(self, key: str) -> list[list[Any]]:
        return []

    def from_dict(self, d: dict[str, Any]) -> TableProject:
        settings = self.default_settings()
        for s in self.settings:
            if s.key in d.get("settings", {}):
                try:
                    settings[s.key] = parse_setting(s, str(d["settings"][s.key])) if s.kind != "text" \
                        else str(d["settings"][s.key])
                except ValueError:
                    pass  # a hand-edited bad value falls back to the default
        raw_tables = d.get("tables", {})
        tables = {t.key: [list(r) for r in raw_tables.get(t.key, [])] for t in self.tables}
        p = TableProject(self.id, title=str(d.get("title", "")), output=str(d.get("output", "")),
                         settings=settings, tables=tables)
        self.check_shape(p)
        return p

    def check_shape(self, p: TableProject) -> None:
        """Make hand-edited files safe to open: every row must have one value per column."""
        for t in self.tables:
            n = len(self.columns(p, t.key))
            for row in p.tables[t.key]:
                if len(row) != n:
                    raise ValueError(f'Table "{t.label}" has a row with {len(row)} values; expected {n}.')

    def replace_data(self, project: TableProject, imported: TableProject) -> None:
        project.tables = imported.tables

    # ---- editing hooks (the series table of wide charts overrides these)
    def row_added(self, p: TableProject, table: str, index: int) -> None: ...
    def row_removed(self, p: TableProject, table: str, index: int) -> None: ...
    def rows_swapped(self, p: TableProject, table: str, i: int, j: int) -> None: ...

    def fill_row(self, p: TableProject, table: str, row: list[Any]) -> list[Any]:
        """Last chance to complete a new row (e.g. pick a colour). Raises ValueError to reject it."""
        return row

    # ---- rendering
    def render(self, project: TableProject, out: Path, dpi: int = 170) -> Path:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        self.check_ready(project)
        with matplotlib.rc_context({"text.parse_math": False}):  # users type "$5" and "$a$": show it as typed
            fig = self.draw(project, plt)
            out.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(out, dpi=dpi)
            plt.close(fig)
        return out

    def check_ready(self, p: TableProject) -> None:
        spec = self.main_table()
        if len(p.tables[spec.key]) < self.min_rows:
            raise ValueError(f"Add at least {self.min_rows} row{'s' if self.min_rows > 1 else ''} "
                             f"on the {spec.label} tab before exporting.")

    def draw(self, project: TableProject, plt: Any) -> Any:
        raise NotImplementedError

    def preview(self, project: TableProject) -> Text:
        out = Text()
        for t in self.tables:
            out.append(f"{t.label}: {len(project.tables[t.key])} row(s)\n")
        out.append("\nPress F5 to draw the real chart.", style="dim")
        return out

    # ---- CSV
    def from_csv(self, path: Path, title: str) -> TableProject:
        header, rows = read_csv(path)
        p = self.new(title)
        if self.csv_layout == "wide":
            self._csv_wide(p, path, header, rows)
        else:
            self._csv_long(p, path, header, rows)
        if len(p.tables[self.main_table().key]) < self.min_rows:
            raise CsvError(f"{path.name} needs at least {self.min_rows} data rows for this chart type.")
        self.check_csv(p, path)
        return p

    def check_csv(self, p: TableProject, path: Path) -> None:
        """Whole-file checks (links between rows and so on). Raise CsvError."""

    def _csv_long(self, p: TableProject, path: Path, header: list[str], rows: list[list[str]]) -> None:
        spec = self.main_table()
        cols = self.columns(p, spec.key)
        names = [norm_header(h) for h in header]
        index: dict[str, int] = {}
        for c in cols:
            for n in (c.key, c.label, *c.aliases):
                if norm_header(n) in names:
                    index[c.key] = names.index(norm_header(n))
                    break
        missing = [c.label for c in cols if c.required and c.key not in index]
        if missing:
            raise CsvError(f"{path.name} is missing the column(s): {', '.join(missing)}. "
                           f"Found: {', '.join(header)}. See docs/csv/{self.id}.md.")
        out: list[list[Any]] = []
        for line, raw_row in enumerate(rows, start=2):
            row: list[Any] = []
            for c in cols:
                raw = cell(raw_row, index[c.key]) if c.key in index else ""
                try:
                    row.append(parse_cell(c, raw))
                except ValueError as e:
                    got = f' (got "{raw}")' if raw else ""
                    raise CsvError(f'{path.name} row {line}, column "{c.label}": {e}{got}.') from None
            out.append(row)
        p.tables[spec.key] = out
        self.check_unique(p, path, spec, cols)

    def check_unique(self, p: TableProject, path: Path, spec: TableSpec, cols: list[Column]) -> None:
        if not spec.unique:
            return
        i = next(n for n, c in enumerate(cols) if c.key == spec.unique)
        seen: dict[Any, int] = {}
        for line, row in enumerate(p.tables[spec.key], start=2):
            if row[i] in seen:
                raise CsvError(f'{path.name} row {line}, column "{cols[i].label}": "{row[i]}" is already used '
                               f"on row {seen[row[i]]}; each value must be unique.")
            seen[row[i]] = line

    def _csv_wide(self, p: TableProject, path: Path, header: list[str], rows: list[list[str]]) -> None:
        series = header[1:]
        if not series:
            raise CsvError(f"{path.name} needs a label column followed by at least one column of numbers. "
                           f"Found only: {', '.join(header)}. See docs/csv/{self.id}.md.")
        seen: set[str] = set()
        for i, name in enumerate(series, start=2):
            if not name:
                raise CsvError(f"{path.name}, column {i}: the header is empty. Every column needs a name "
                               "(it becomes the series name in the legend).")
            if name.lower() in seen:
                raise CsvError(f'{path.name}, column {i}: the name "{name}" appears twice in the header.')
            seen.add(name.lower())
        colors: list[str] = []
        for name in series:
            colors.append(core.auto_color(colors))
        p.tables["series"] = [[n, c] for n, c in zip(series, colors)]
        data: list[list[Any]] = []
        for line, raw_row in enumerate(rows, start=2):
            label = cell(raw_row, 0)
            if not label:
                raise CsvError(f'{path.name} row {line}, column "{header[0]}": the label is empty.')
            row: list[Any] = [label]
            for i, name in enumerate(series, start=1):
                raw = cell(raw_row, i)
                if not raw:
                    row.append(None)
                    continue
                try:
                    row.append(parse_cell(Column(name, name, "number", required=False), raw))
                except ValueError as e:
                    raise CsvError(f'{path.name} row {line}, column "{name}": {e} (got "{raw}").') from None
            data.append(row)
        p.tables["data"] = data


# ------------------------------------------------------------ wide (series) charts

SERIES_TABLE = TableSpec(
    "series", "Series",
    "Each series is one set of bars/lines and gets one column on the Data tab. "
    "Colours are picked for you; choose your own if you like.",
    (Column("name", "Name", help="Shown in the legend"),
     Column("color", "Colour", "color", required=False, help="Hex code like #377EB8; blank = automatic")),
    unique="name",
)


class WideChart(TableChart):
    """A label column plus one numeric column per series (bar, line, area, radar)."""

    csv_layout = "wide"
    tables = (SERIES_TABLE,
              TableSpec("data", "Data",
                        "One row per category (the x axis). Leave a number blank for 'no value'.",
                        (Column("label", "Label"),)))

    def columns(self, project: TableProject, key: str) -> list[Column]:
        if key == "series":
            return list(SERIES_TABLE.columns)
        return [Column("label", "Label")] + [
            Column(f"s{i}", str(name), "number", required=False)
            for i, (name, _color) in enumerate(project.tables["series"])]

    def starter_rows(self, key: str) -> list[list[Any]]:
        return [["Series 1", core.SWATCHES[0]]] if key == "series" else []

    def fill_row(self, p: TableProject, table: str, row: list[Any]) -> list[Any]:
        if table == "series" and not row[1]:
            row[1] = core.auto_color([r[1] for r in p.tables["series"]])
        return row

    def row_added(self, p: TableProject, table: str, index: int) -> None:
        if table == "series":
            for r in p.tables["data"]:
                r.insert(index + 1, None)

    def row_removed(self, p: TableProject, table: str, index: int) -> None:
        if table == "series":
            for r in p.tables["data"]:
                del r[index + 1]

    def rows_swapped(self, p: TableProject, table: str, i: int, j: int) -> None:
        if table == "series":
            for r in p.tables["data"]:
                r[i + 1], r[j + 1] = r[j + 1], r[i + 1]

    def check_ready(self, p: TableProject) -> None:
        if not p.tables["series"]:
            raise ValueError("Add at least one series on the Series tab before exporting.")
        super().check_ready(p)

    # ---- helpers for draw()
    @staticmethod
    def labels(p: TableProject) -> list[str]:
        return [str(r[0]) for r in p.tables["data"]]

    @staticmethod
    def series(p: TableProject) -> list[tuple[str, str, list[float | None]]]:
        return [(name, color, [r[i + 1] for r in p.tables["data"]])
                for i, (name, color) in enumerate(p.tables["series"])]


# ------------------------------------------------------------------ drawing helpers

TITLE = dict(fontsize=16, fontweight="bold")


def new_figure(plt: Any, title: str, size: tuple[float, float] = (9.0, 5.5), **kwargs: Any) -> tuple[Any, Any]:
    fig, ax = plt.subplots(figsize=size, **kwargs)
    if title:
        fig.suptitle(title, **TITLE)
    return fig, ax


def tidy(ax: Any, x_label: str = "", y_label: str = "", grid: str = "y") -> None:
    if x_label:
        ax.set_xlabel(x_label, fontsize=12)
    if y_label:
        ax.set_ylabel(y_label, fontsize=12)
    if grid:
        ax.grid(axis=grid, color="#DDDDDD", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def rotate_if_crowded(ax: Any, labels: list[str]) -> None:
    if len(labels) > 8 or max((len(s) for s in labels), default=0) > 10:
        for tick in ax.get_xticklabels():
            tick.set_rotation(35)
            tick.set_ha("right")


def finish(fig: Any) -> Any:
    fig.tight_layout(rect=(0, 0, 1, 0.94) if fig._suptitle is not None else None)
    return fig


def is_on(value: Any) -> bool:
    return str(value).lower() == "yes"
