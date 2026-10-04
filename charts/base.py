"""
The interface every chart type implements, plus the CSV reader they share.

A chart type is registered in `charts/__init__.py`. The app only talks to this interface:
it never needs to know how a particular chart is drawn or stored.
"""
from __future__ import annotations

import csv
import io
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CsvError(ValueError):
    """A CSV file couldn't be imported. The message says where and why, in plain English."""


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    kind: str = "text"            # text | number | int | date | choice | color
    required: bool = True
    default: str = ""             # what the "add row" form starts with
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    strict: bool = False          # value must be > minimum rather than >= minimum
    aliases: tuple[str, ...] = ()  # other CSV header names that mean this column
    help: str = ""                # one line for the docs and the form


class ChartType(ABC):
    id: str = ""             # stored in the project file as "type"
    label: str = ""          # shown in the picker
    description: str = ""    # one line, shown in the picker
    editor: str = "table"    # which editor screen the app opens: "gantt" or "table"
    csv_layout: str = "long"  # "long": one row per record; "wide": label + one column per series
    csv_notes: str = ""      # extra sentence for the CSV help and docs

    @abstractmethod
    def new(self, title: str) -> Any:
        """A starter project."""

    @abstractmethod
    def from_dict(self, d: dict[str, Any]) -> Any:
        """Rebuild a project from its JSON."""

    @abstractmethod
    def from_csv(self, path: Path, title: str) -> Any:
        """A new project built from a CSV file. Raises CsvError."""

    @abstractmethod
    def render(self, project: Any, out: Path, dpi: int = 170) -> Path:
        """Draw the PNG. Raises ValueError (with a user-readable message) if there's nothing to draw."""

    @abstractmethod
    def replace_data(self, project: Any, imported: Any) -> None:
        """Swap `project`'s data for the data of `imported`, keeping its title and settings."""

    def csv_columns(self) -> list[Column]:
        """The columns a long-format CSV may contain (empty for wide charts)."""
        return []

    @property
    def csv_help(self) -> str:
        """Short description of the expected CSV, shown in the app."""
        if self.csv_layout == "wide":
            text = ("First column: a label for each row (any header). Every other column is one series of "
                    "numbers and its header is the series name. Leave a cell empty for 'no value'.")
        else:
            cols = self.csv_columns()
            text = "Header row required. Columns: " + ", ".join(c.label for c in cols if c.required)
            optional = [c.label for c in cols if not c.required]
            text += (f". Optional: {', '.join(optional)}" if optional else "") + "."
        return f"{text} {self.csv_notes}".strip()

    def preview(self, project: Any) -> Any:
        """Rough text rendering for the Preview tab (a rich Text), or None."""
        return None


# ------------------------------------------------------------------- CSV reading

def norm_header(name: str) -> str:
    """'  Task Name ' / 'task_name' / 'TASK-NAME' all become 'task name'."""
    return re.sub(r"[\s_\-]+", " ", name.strip().lower())


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    """Header row and data rows of a CSV file. Blank lines are skipped.

    Accepts UTF-8 with or without a BOM, and `,` `;` or tab as the separator (spreadsheet
    programs in some countries save `;`). Raises CsvError for anything unreadable.
    """
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise CsvError(f"Couldn't read {path}: {e.strerror or e}") from None
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvError(f"{path.name} isn't UTF-8 text. In Excel use \"Save As → CSV UTF-8\".") from None
    if not text.strip():
        raise CsvError(f"{path.name} is empty.")

    first = text.splitlines()[0]
    delimiter = max(",;\t", key=first.count) if any(d in first for d in ",;\t") else ","
    try:
        rows = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter)
                if any(cell.strip() for cell in r)]
    except csv.Error as e:
        raise CsvError(f"{path.name} isn't valid CSV: {e}") from None
    header, body = [h.strip() for h in rows[0]], rows[1:]
    if not body:
        raise CsvError(f"{path.name} has a header row but no data rows.")
    return header, body


def cell(row: list[str], i: int) -> str:
    return row[i].strip() if i < len(row) else ""


def csv_number(path: Path, line: int, column: str, raw: str) -> float:
    try:
        value = float(raw)
    except ValueError:
        raise CsvError(f'{path.name} row {line}, column "{column}": "{raw}" is not a number '
                       "(use a plain number like 12 or 3.5).") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise CsvError(f'{path.name} row {line}, column "{column}": "{raw}" is not a usable number.')
    return value
