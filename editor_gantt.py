"""Editor screen for Gantt charts: settings, categories, tasks and milestones."""
from __future__ import annotations

import re
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import DataTable, Footer, Header, Input, Label, Static, TabbedContent, TabPane

import chart_core as core
from chart_core import fmt_num
from charts.gantt import Category, Milestone, Task
from editor_base import EditorScreen
from ui import Field, FormScreen, ItemTable, Panel, need, number, parse_color

Item = Category | Task | Milestone

TABLES = {"categories": "Categories", "tasks": "Tasks", "milestones": "Milestones"}
TAB_ORDER = ["tab-settings", "tab-categories", "tab-tasks", "tab-milestones", "tab-preview"]
SETTINGS = [
    ("title", "Chart title"),
    ("start", "Week 1 starts on (YYYY-MM-DD)"),
    ("weeks", "Number of weeks (grows automatically if tasks run past it)"),
    ("today", "Today line: 'auto' = today's date, blank = none, or YYYY-MM-DD"),
    ("axis", "X-axis label (blank = generated from the start date)"),
    ("output", "PNG file name (blank = same name as the project file)"),
]


def next_wbs(tasks: list[Task]) -> str:
    m = re.match(r"^(.*?)(\d+)$", tasks[-1].wbs.strip()) if tasks else None
    return f"{m.group(1)}{int(m.group(2)) + 1}" if m else ""


def next_start(tasks: list[Task]) -> str:
    """A new task starts the week after the previous one ends."""
    return fmt_num(tasks[-1].start + tasks[-1].duration) if tasks else "1"


class GanttEditor(EditorScreen):
    def table_kinds(self) -> list[str]:
        return list(TABLES)

    def tab_ids(self) -> list[str]:
        return TAB_ORDER

    # ---- layout
    def settings_values(self) -> dict[str, str]:
        p = self.project
        return {"title": p.title, "start": p.semester_start.isoformat(), "weeks": str(p.weeks),
                "today": p.today, "axis": p.axis_label, "output": p.output}

    def compose(self) -> ComposeResult:
        values = self.settings_values()
        yield Header()
        with TabbedContent(id="tabs"):
            with TabPane("Settings", id="tab-settings"), Panel(id="settings"):
                yield Label("↑/↓ move between boxes. ↑ from the first box goes back to the tab bar, "
                            "where ←/→ switch tabs.", classes="hint")
                for key, label in SETTINGS:
                    yield Label(label, classes="field-label")
                    yield Input(value=values[key], id=f"set-{key}")
            with TabPane("Categories", id="tab-categories"):
                yield Label("Categories give tasks their bar colour. Colours are picked for you automatically; "
                            "choose your own if you like (no hex codes needed).  a add · enter edit · d delete",
                            classes="hint")
                yield ItemTable(id="categories", cursor_type="row", zebra_stripes=True)
            with TabPane("Tasks", id="tab-tasks"):
                yield Label("Row order = order on the chart. A new task starts the week after the previous one ends.  "
                            "a add · enter edit · d delete · [ ] reorder · ←/→ switch tab", classes="hint")
                yield ItemTable(id="tasks", cursor_type="row", zebra_stripes=True)
            with TabPane("Milestones", id="tab-milestones"):
                yield Label("Diamonds above the chart. Use \\n in a label for a line break; "
                            "week may be fractional (14.3).", classes="hint")
                yield ItemTable(id="milestones", cursor_type="row", zebra_stripes=True)
            with TabPane("Preview", id="tab-preview"), ScrollableContainer():
                yield Static(id="preview")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#categories", DataTable).add_columns("", "Name", "Colour", "Tasks")
        self.query_one("#tasks", DataTable).add_columns("WBS", "Task", "Category", "Start wk", "Weeks", "Ends wk")
        self.query_one("#milestones", DataTable).add_columns("Week", "Label")
        self.refresh_all()

    def reload(self) -> None:
        for key, value in self.settings_values().items():
            box = self.query_one(f"#set-{key}", Input)
            box.value = value
            box.remove_class("-invalid")
        for kind in TABLES:
            self.refresh_table(kind, cursor=0)
        self.app.refresh_title()  # type: ignore[attr-defined]

    # ---- tables
    def rows(self, kind: str) -> list[tuple[Any, ...]]:
        p = self.project
        colors = {c.name: c.color for c in p.categories}
        if kind == "categories":
            return [(Text("██", style=c.color), c.name, c.color,
                     str(sum(t.category == c.name for t in p.tasks))) for c in p.categories]
        if kind == "tasks":
            return [(t.wbs, t.name, Text(t.category, style=colors.get(t.category, "red")),
                     fmt_num(t.start), fmt_num(t.duration), fmt_num(t.end)) for t in p.tasks]
        return [(fmt_num(m.week), m.label.replace("\n", "\\n")) for m in p.milestones]

    def items(self, kind: str) -> list[Any]:
        return getattr(self.project, kind)

    def delete_blocked(self, kind: str, index: int) -> str | None:
        if kind == "categories":
            used = sum(t.category == self.project.categories[index].name for t in self.project.tasks)
            if used:
                return f"{used} task(s) still use this category."
        return None

    # ---- settings
    def on_input_changed(self, event: Input.Changed) -> None:
        widget_id = event.input.id or ""
        if not widget_id.startswith("set-"):
            return
        key, raw, p = widget_id[4:], event.value, self.project
        new: tuple[str, Any]
        try:
            if key == "title":
                new = ("title", raw)
            elif key == "start":
                new = ("semester_start", core.parse_date(raw))
            elif key == "weeks":
                new = ("weeks", int(number(raw, "Weeks", 1)))
            elif key == "today":
                if raw.strip() and raw.strip().lower() != "auto":
                    core.parse_date(raw)
                new = ("today", raw.strip())
            elif key == "axis":
                new = ("axis_label", raw)
            else:
                new = ("output", raw)
        except ValueError:
            event.input.add_class("-invalid")
            return
        event.input.remove_class("-invalid")
        if getattr(p, new[0]) != new[1]:
            setattr(p, new[0], new[1])
            self.mark_dirty()

    # ---- forms
    def open_form(self, kind: str, index: int | None) -> None:
        p = self.project
        items = self.items(kind)
        old = items[index] if index is not None else None
        verb = "Add" if old is None else "Edit"

        if kind == "categories":
            title = f"{verb} category"
            fields = [Field("name", "Name", old.name if old else ""),
                      Field("color", "Colour (leave on Auto and one is picked for you)",
                            old.color if old else "", picker=True)]

            def validate(raw: dict[str, str]) -> Item:
                name = need(raw["name"], "Name")
                if any(c.name == name and c is not old for c in items):
                    raise ValueError("A category with that name already exists.")
                return Category(name, parse_color(raw["color"], [c.color for c in items if c is not old]))

        elif kind == "tasks":
            if not p.categories:
                self.notify("Add a category first (Categories tab).", severity="warning")
                return
            names = [c.name for c in p.categories]
            title = f"{verb} task"
            fields = [Field("wbs", "WBS number (optional, printed inside the bar)",
                            old.wbs if old else next_wbs(items)),
                      Field("name", "Task name", old.name if old else ""),
                      Field("category", "Category",
                            old.category if old and old.category in names
                            else items[-1].category if items and items[-1].category in names  # same as the last task
                            else names[0], choices=names),
                      Field("start", "Start week (1 = first week)",
                            fmt_num(old.start) if old else next_start(items)),
                      Field("duration", "Duration in weeks", fmt_num(old.duration) if old else "1")]

            def validate(raw: dict[str, str]) -> Item:
                return Task(raw["wbs"].strip(), need(raw["name"], "Task name"), raw["category"],
                            number(raw["start"], "Start week", 1),
                            number(raw["duration"], "Duration", 0, strict=True))

        else:
            title = f"{verb} milestone"
            fields = [Field("week", "Week position (e.g. 14.3; 16 = end of week 16)",
                            fmt_num(old.week) if old else ""),
                      Field("label", "Label (\\n = line break)",
                            old.label.replace("\n", "\\n") if old else "")]

            def validate(raw: dict[str, str]) -> Item:
                return Milestone(number(raw["week"], "Week", 0),
                                 need(raw["label"], "Label").replace("\\n", "\n"))

        def done(result: Item | None) -> None:
            if result is None:
                return
            if isinstance(old, Category) and isinstance(result, Category) and old.name != result.name:
                for t in p.tasks:  # keep tasks attached when a category is renamed
                    if t.category == old.name:
                        t.category = result.name
            if index is None:
                items.append(result)
                index_after = len(items) - 1
            else:
                items[index] = result
                index_after = index
            self.mark_dirty()
            self.refresh_all()
            self.query_one(f"#{kind}", DataTable).move_cursor(row=index_after)

        self.app.push_screen(FormScreen(title, fields, validate), done)
