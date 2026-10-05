"""
Shared pieces for every chart type: colours, number/date parsing, the projects folder,
and loading/saving project files (the chart type is stored in the JSON as "type").

The chart types themselves live in the `charts` package.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Protocol

# Colour choices offered in the picker, SWATCH_COLS per row. The first row is also
# what gets handed out automatically, in order, to things without a colour.
SWATCH_COLS = 8
SWATCHES = [
    "#377EB8", "#E4572E", "#3A9E4E", "#8456B8", "#E0A82E", "#2AA6B8", "#C94F8A", "#6B6B6B",
    "#1F4E79", "#A33A1A", "#1F6B30", "#573680", "#9A6F12", "#176B78", "#8C2F5E", "#333333",
    "#7FB2E0", "#F28C6B", "#7CCB8B", "#B592E0", "#F2CC73", "#74CDD9", "#E69AC1", "#A8A8A8",
    "#D62728", "#FF7F0E", "#BCBD22", "#17BECF", "#1F77B4", "#9467BD", "#8C564B", "#2CA02C",
]
PALETTE = SWATCHES[:SWATCH_COLS]
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def local_today() -> date:
    return datetime.now(tz=timezone.utc).astimezone().date()


def auto_color(used_colors: list[str]) -> str:
    """First swatch not in `used_colors` (cycling once they're all taken)."""
    used = {c.lower() for c in used_colors}
    for color in SWATCHES:
        if color.lower() not in used:
            return color
    return SWATCHES[len(used_colors) % len(SWATCHES)]


def color_cycle(n: int) -> list[str]:
    """`n` distinct-looking colours, for slices, groups and the like."""
    return [SWATCHES[i % len(SWATCHES)] for i in range(n)]


def text_color_for(background: str) -> str:
    """Black or white, whichever reads better on `background` (#RRGGBB)."""
    r, g, b = (int(background[k:k + 2], 16) for k in (1, 3, 5))
    return "black" if 0.299 * r + 0.587 * g + 0.114 * b > 160 else "white"


def fmt_num(x: float) -> str:
    return str(int(x)) if float(x) == int(x) else f"{x:g}"


def parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        raise ValueError("Date must look like YYYY-MM-DD") from None


# ---------------------------------------------------------------- persistence

class SavedProject(Protocol):
    """What every chart type's project object offers to the app."""
    type: str
    title: str
    output: str

    def to_dict(self) -> dict[str, Any]: ...


def save_project(p: SavedProject, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(p.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_project(path: Path) -> Any:
    """Load a project file. Files without a "type" are Gantt charts (the original format)."""
    from charts import get  # imported here: the chart modules import this one

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Not a chart project file.")
    return get(str(data.get("type", "gantt"))).from_dict(data)


def projects_dir() -> Path:
    """Where saved projects live (override with the PYGANTT_PROJECTS environment variable)."""
    override = os.environ.get("PYGANTT_PROJECTS")
    return Path(override).expanduser() if override else Path.home() / "Documents" / "PyGantt-Builder"


def list_projects(folder: Path | None = None) -> list[Path]:
    """Saved projects, most recently changed first."""
    folder = folder or projects_dir()
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)


def project_type_of(path: Path) -> str:
    """Chart type stored in a project file ('gantt' if the file doesn't say, '?' if unreadable)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("type", "gantt")) if isinstance(data, dict) else "?"
    except (OSError, ValueError):
        return "?"


_BAD_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                     *(f"LPT{i}" for i in range(1, 10))}


def project_filename(name: str) -> str:
    """Turn a project name into a file name that is valid on Linux and Windows."""
    safe = _BAD_FILENAME_CHARS.sub("-", name).strip(" .")
    if not safe:
        raise ValueError("Project name can't be empty.")
    if safe.upper() in _WINDOWS_RESERVED:
        safe += "_"
    return safe[:80] + ".json"


def output_path(p: SavedProject, project_file: Path) -> Path:
    """Where the PNG goes: the project's `output` setting (relative to the project file), or
    next to the project file with a .png extension. The result always ends in .png."""
    if not p.output.strip():
        return project_file.with_suffix(".png")
    out = Path(p.output.strip())
    if out.suffix.lower() != ".png":
        out = out.with_name(out.name + ".png")  # "report" -> "report.png", "v1.2" -> "v1.2.png"
    return out if out.is_absolute() else project_file.parent / out
