"""
Data model, JSON load/save and PNG rendering for the Gantt chart builder.

Week 1 starts on `semester_start`. A task with start=S, duration=D covers
S-1 to S-1+D on the x axis. Start/duration/milestone weeks may be fractional.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PALETTE = ["#377EB8", "#E4572E", "#3A9E4E", "#8456B8", "#6B6B6B",
           "#E0A82E", "#2AA6B8", "#C94F8A"]
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def local_today() -> date:
    return datetime.now(tz=timezone.utc).astimezone().date()


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

    @classmethod
    def starter(cls) -> Project:
        names = ["Planning", "Build", "Test"]
        return cls(categories=[Category(n, c) for n, c in zip(names, PALETTE)])


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def fmt_num(x: float) -> str:
    return str(int(x)) if float(x) == int(x) else f"{x:g}"


def parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        raise ValueError("Date must look like YYYY-MM-DD") from None


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


# ---------------------------------------------------------------- persistence

def project_to_dict(p: Project) -> dict[str, Any]:
    return {
        "title": p.title,
        "semester_start": p.semester_start.isoformat(),
        "weeks": p.weeks,
        "today": p.today,
        "axis_label": p.axis_label,
        "output": p.output,
        "categories": [{"name": c.name, "color": c.color} for c in p.categories],
        "tasks": [{"wbs": t.wbs, "name": t.name, "category": t.category,
                   "start": t.start, "duration": t.duration} for t in p.tasks],
        "milestones": [{"week": m.week, "label": m.label} for m in p.milestones],
    }


def project_from_dict(d: dict[str, Any]) -> Project:
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


def save_project(p: Project, path: Path) -> None:
    path.write_text(json.dumps(project_to_dict(p), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def load_project(path: Path) -> Project:
    return project_from_dict(json.loads(path.read_text(encoding="utf-8")))


def output_path(p: Project, project_file: Path) -> Path:
    out = Path(p.output.strip()) if p.output.strip() else project_file.with_suffix(".png")
    return out if out.is_absolute() else project_file.parent / out


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
