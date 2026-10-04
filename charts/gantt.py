"""
Gantt chart: data model, JSON, CSV import and PNG rendering.

Week 1 starts on `semester_start`. A task with start=S, duration=D covers
S-1 to S-1+D on the x axis. Start/duration/milestone weeks may be fractional.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from rich.text import Text

import chart_core as core
from chart_core import PALETTE, fmt_num, local_today, parse_date

from .base import ChartType, Column, CsvError, cell, csv_number, norm_header, read_csv


@dataclass
class Category:
    name: str
    color: str


@dataclass
class Task:
    wbs: str
    name: str
    category: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start - 1 + self.duration


@dataclass
class Milestone:
    week: float
    label: str  # may contain "\n"


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


@dataclass
class Project:
    title: str = "My Project"
    semester_start: date = field(default_factory=lambda: _monday(local_today()))
    weeks: int = 12
    today: str = "auto"      # "" = no line, "auto" = real today, or YYYY-MM-DD
    axis_label: str = ""     # "" = generated from semester_start
    output: str = ""         # "" = <project file stem>.png
    categories: list[Category] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    milestones: list[Milestone] = field(default_factory=list)
    type: str = "gantt"

    @classmethod
    def starter(cls) -> Project:
        names = ["Planning", "Build", "Test"]
        return cls(categories=[Category(n, c) for n, c in zip(names, PALETTE)])

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "gantt",
            "title": self.title,
            "semester_start": self.semester_start.isoformat(),
            "weeks": self.weeks,
            "today": self.today,
            "axis_label": self.axis_label,
            "output": self.output,
            "categories": [{"name": c.name, "color": c.color} for c in self.categories],
            "tasks": [{"wbs": t.wbs, "name": t.name, "category": t.category,
                       "start": t.start, "duration": t.duration} for t in self.tasks],
            "milestones": [{"week": m.week, "label": m.label} for m in self.milestones],
        }


def auto_color(categories: list[Category]) -> str:
    """First swatch no category uses yet (cycling once they're all taken)."""
    return core.auto_color([c.color for c in categories])


def today_date(p: Project) -> date | None:
    s = p.today.strip().lower()
    if not s:
        return None
    return local_today() if s == "auto" else parse_date(s)


def effective_weeks(p: Project) -> int:
    """Chart width: the configured weeks, widened if anything runs past it."""
    ends = [t.end for t in p.tasks] + [m.week for m in p.milestones]
    return max([p.weeks] + [math.ceil(e) for e in ends])


def axis_label(p: Project) -> str:
    s = p.semester_start
    return p.axis_label.strip() or f"Week (week 1 starts {s:%a %b} {s.day})"


def month_labels(start: date, weeks: int) -> list[tuple[float, str]]:
    """(x position in weeks, 'Aug') for each month, centred on its visible span."""
    end = start + timedelta(days=weeks * 7)
    out = []
    first = start.replace(day=1)
    while first < end:
        nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        lo, hi = max(first, start), min(nxt, end)
        if (hi - lo).days >= 4:  # skip slivers that would collide with neighbours
            mid = ((lo - start).days + (hi - start).days) / 14
            out.append((mid, f"{first:%b}"))
        first = nxt
    return out


# ------------------------------------------------------------------- rendering

def render(p: Project, out: Path, dpi: int = 170) -> Path:
    """Draw the chart to `out` (PNG). Raises ValueError if there is nothing to draw."""
    if not p.tasks:
        raise ValueError("Add at least one task before exporting.")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    colors = {c.name: c.color for c in p.categories}
    tasks, n = p.tasks, len(p.tasks)
    weeks = effective_weeks(p)

    # Layout in inches so the look stays consistent from 5 tasks to 50.
    row_in = 0.32
    axes_w = max(5.0, 0.6 * weeks)
    axes_h = (n + 0.6) * row_in
    left = max(2.0, 0.085 * max(len(t.name) for t in tasks) + 0.4)
    right = 0.9
    head = 1.6 if p.milestones else 1.0
    used = [c for c in p.categories if any(t.category == c.name for t in tasks)]
    bottom = 0.75 + 0.27 * math.ceil(max(len(used), 1) / 3)
    axes_w += max(0.0, 0.125 * len(p.title) + 0.6 - (left + axes_w + right))  # room for title
    width, height = left + axes_w + right, head + axes_h + bottom

    fig = plt.figure(figsize=(width, height))
    ax = fig.add_axes((left / width, bottom / height, axes_w / width, axes_h / height))

    for i, t in enumerate(tasks):
        x0 = t.start - 1
        ax.barh(i, t.duration, left=x0, height=0.6,
                color=colors.get(t.category, "#888888"), zorder=3)
        if t.wbs:
            ax.text(x0 + 0.12, i, t.wbs, va="center", ha="left",
                    color="white", fontsize=9.5, fontweight="bold", zorder=4)

    today = today_date(p)
    if today is not None:
        today_x = ((today - p.semester_start).days + 1) / 7  # counting day 1 as week 1's Monday
        if 0 <= today_x <= weeks:
            ax.axvline(today_x, color="#C0392B", linestyle="--", linewidth=1.8, zorder=5)
            ax.text(today_x + 0.12, -1.15, f"Today\n({today:%b} {today.day})",
                    color="#C0392B", fontsize=9, va="center", ha="left")

    for x, label in month_labels(p.semester_start, weeks):
        ax.text(x, -2.0, label, ha="center", va="center",
                fontsize=11, style="italic", color="#555555")

    for m in p.milestones:
        ax.plot(m.week, -1.8, marker="D", markersize=13, color="#111111",
                clip_on=False, zorder=6)
        ax.plot([m.week, m.week], [-2.6, -3.1], color="#888888", linewidth=1, clip_on=False)
        ax.text(m.week, -3.15, m.label, ha="center", va="bottom", fontsize=9.5, clip_on=False)

    ax.set_yticks(range(n))
    ax.set_yticklabels([t.name for t in tasks], fontsize=11)
    ax.set_ylim(n - 0.4, -1.0)
    ax.set_xlim(0, weeks)
    ax.set_xticks(range(1, weeks + 1))
    ax.set_xlabel(axis_label(p), fontsize=12)
    ax.grid(axis="x", color="#DDDDDD", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)

    fig.suptitle(p.title, fontsize=16, fontweight="bold", y=1 - 0.1 / height)

    if used:
        handles = [Patch(facecolor=c.color, label=c.name) for c in used]
        fig.legend(handles=handles, loc="lower right", ncol=3, frameon=False,
                   fontsize=11, bbox_to_anchor=(0.97, 0.0))

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------- CSV

GANTT_CSV_COLUMNS = [
    Column("task", "task", help="Task name", aliases=("task name", "name")),
    Column("start", "start", "number", minimum=1, help="Week the task starts (1 = first week; may be fractional)",
           aliases=("start week",)),
    Column("duration", "duration", "number", minimum=0, strict=True, help="Length in weeks (more than 0)",
           aliases=("weeks", "duration weeks")),
    Column("category", "category", required=False, help='Groups tasks and gives them a colour; blank = "Tasks"',
           aliases=("group",)),
    Column("wbs", "wbs", required=False, help="Number printed inside the bar, e.g. 2.1"),
    Column("color", "color", "color", required=False,
           help="Hex colour for the category (the first row of each category counts)", aliases=("colour",)),
]


def project_from_csv(path: Path, title: str) -> Project:
    header, rows = read_csv(path)
    names = [norm_header(h) for h in header]
    aliases = {"task": ("task", "task name", "name"), "start": ("start", "start week"),
               "duration": ("duration", "weeks", "duration weeks"), "category": ("category", "group"),
               "wbs": ("wbs",), "color": ("color", "colour")}
    col: dict[str, int] = {}
    for key, options in aliases.items():
        for o in options:
            if o in names:
                col[key] = names.index(o)
                break
    missing = [k for k in ("task", "start", "duration") if k not in col]
    if missing:
        raise CsvError(f'{path.name} is missing the column(s): {", ".join(missing)}. '
                       f'Found: {", ".join(header)}. See docs/csv/gantt.md.')

    project = Project(title=title, categories=[])
    colors: dict[str, str] = {}
    for line, row in enumerate(rows, start=2):
        name = cell(row, col["task"])
        if not name:
            raise CsvError(f'{path.name} row {line}, column "task": the task name is empty.')
        start = csv_number(path, line, "start", cell(row, col["start"]))
        duration = csv_number(path, line, "duration", cell(row, col["duration"]))
        if start < 1:
            raise CsvError(f'{path.name} row {line}, column "start": must be 1 or more (week 1 is the first week).')
        if duration <= 0:
            raise CsvError(f'{path.name} row {line}, column "duration": must be more than 0.')
        category = cell(row, col["category"]) if "category" in col else ""
        category = category or "Tasks"
        if category not in colors:
            raw = cell(row, col["color"]) if "color" in col else ""
            if raw and not raw.startswith("#"):
                raw = "#" + raw
            if raw and not core.HEX_RE.match(raw):
                raise CsvError(f'{path.name} row {line}, column "color": "{raw}" is not a hex code like #377EB8.')
            colors[category] = raw or auto_color(project.categories)
            project.categories.append(Category(category, colors[category]))
        project.tasks.append(Task(cell(row, col["wbs"]) if "wbs" in col else "", name, category, start, duration))
    return project


# --------------------------------------------------------------- text preview

def build_preview(p: Project) -> Text:
    if not p.tasks:
        return Text("No tasks yet - add some on the Tasks tab.", style="dim")
    weeks = effective_weeks(p)
    colors = {c.name: c.color for c in p.categories}
    name_w = min(40, max(len(t.name) for t in p.tasks))
    out = Text(no_wrap=True)
    out.append(f"{'Week':<{name_w + 1}}" + "".join(f"{w:<4}" for w in range(1, weeks + 1)) + "\n", style="bold")
    for t in p.tasks:
        out.append(f"{t.name[:name_w]:<{name_w}} ")
        for half in range(weeks * 2):  # 4 characters per week => half-week resolution
            mid = (half + 0.5) / 2
            filled = t.start - 1 <= mid < t.end
            out.append("██" if filled else "··", style=colors.get(t.category, "red") if filled else "grey35")
        out.append("\n")
    try:
        today = today_date(p)
    except ValueError:
        today = None
    if today:
        out.append(f"\nToday: {today:%b} {today.day} (week {((today - p.semester_start).days) / 7 + 1:.1f})", style="red")
    for m in p.milestones:
        out.append(f"\n◆ week {fmt_num(m.week)}: {m.label.replace(chr(10), ' ')}")
    out.append("\n\nRough preview - press F5 for the real chart.", style="dim")
    return out


# ------------------------------------------------------------------ chart type

class GanttChart(ChartType):
    id = "gantt"
    label = "Gantt chart"
    description = "Tasks as bars over weeks, with milestones and a 'today' line."
    editor = "gantt"
    csv_notes = "Milestones aren't imported - add them in the app."

    def csv_columns(self) -> list[Column]:
        return GANTT_CSV_COLUMNS

    def new(self, title: str) -> Project:
        p = Project.starter()
        p.title = title
        return p

    def from_dict(self, d: dict[str, Any]) -> Project:
        base = Project.starter()
        return Project(
            title=d.get("title", base.title),
            semester_start=parse_date(d["semester_start"]) if "semester_start" in d else base.semester_start,
            weeks=int(d.get("weeks", base.weeks)),
            today=d.get("today", base.today),
            axis_label=d.get("axis_label", ""),
            output=d.get("output", ""),
            categories=[Category(c["name"], c["color"]) for c in d.get("categories", [])],
            tasks=[Task(t.get("wbs", ""), t["name"], t["category"],
                        float(t["start"]), float(t["duration"])) for t in d.get("tasks", [])],
            milestones=[Milestone(float(m["week"]), m.get("label", "")) for m in d.get("milestones", [])],
        )

    def from_csv(self, path: Path, title: str) -> Project:
        return project_from_csv(path, title)

    def render(self, project: Project, out: Path, dpi: int = 170) -> Path:
        import matplotlib
        with matplotlib.rc_context({"text.parse_math": False}):  # task names like "$5 budget" show as typed
            return render(project, out, dpi)

    def replace_data(self, project: Project, imported: Project) -> None:
        project.categories, project.tasks = imported.categories, imported.tasks

    def preview(self, project: Project) -> Text:
        return build_preview(project)
