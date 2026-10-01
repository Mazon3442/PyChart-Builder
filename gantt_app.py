"""
Gantt chart builder - a terminal app (Linux / Windows / macOS).

    python gantt_app.py [project.json]        open the editor
    python gantt_app.py project.json --render  just write the PNG and exit

Fill in the tabs, press F5, and a PNG chart is written next to the project file.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, ScrollableContainer, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

import gantt_core as core
from gantt_core import Category, Milestone, Project, Task, fmt_num

Item = Category | Task | Milestone


# ------------------------------------------------------------------ dialogs

@dataclass
class Field:
    key: str
    label: str
    value: str = ""
    choices: list[str] | None = None  # set -> dropdown instead of text box


class FormScreen(ModalScreen[Item | None]):
    """Modal form. `validate(raw: dict[str, str])` returns a result or raises ValueError."""
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "cancel", "Cancel")]
    AUTO_FOCUS = "Input, Select"

    def __init__(self, title: str, fields: list[Field], validate: Callable[[dict[str, str]], Item]):
        super().__init__()
        self.form_title, self.fields, self.validate = title, fields, validate

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="form"):
            yield Label(self.form_title, id="form-title")
            for f in self.fields:
                yield Label(f.label, classes="field-label")
                if f.choices is None:
                    yield Input(value=f.value, id=f"f-{f.key}")
                else:
                    yield Select([(c, c) for c in f.choices], value=f.value,
                                 allow_blank=False, id=f"f-{f.key}")
            yield Label("", id="form-error")
            with Horizontal(id="form-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")

    def submit(self) -> None:
        raw: dict[str, str] = {}
        for f in self.fields:
            widget = self.query_one(f"#f-{f.key}")
            assert isinstance(widget, (Input, Select))
            raw[f.key] = str(widget.value)
        try:
            result = self.validate(raw)
        except ValueError as e:
            self.query_one("#form-error", Label).update(str(e))
            return
        self.dismiss(result)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.submit() if event.button.id == "save" else self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "no", "No"), ("y", "yes", "Yes"), ("n", "no", "No")]
    AUTO_FOCUS = "Button"

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="form"):
            yield Label(self.message)
            with Horizontal(id="form-buttons"):
                yield Button("Yes (y)", variant="warning", id="yes")
                yield Button("No (n)", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


# -------------------------------------------------------------- field parsing

def need(raw: str, what: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError(f"{what} can't be empty.")
    return raw


def number(raw: str, what: str, minimum: float, strict: bool = False) -> float:
    try:
        x = float(raw)
    except ValueError:
        raise ValueError(f"{what} must be a number.") from None
    if x < minimum or (strict and x == minimum):
        raise ValueError(f"{what} must be {'>' if strict else '>='} {fmt_num(minimum)}.")
    return x


def next_wbs(tasks: list[Task]) -> str:
    m = re.match(r"^(.*?)(\d+)$", tasks[-1].wbs.strip()) if tasks else None
    return f"{m.group(1)}{int(m.group(2)) + 1}" if m else ""


# ------------------------------------------------------------------------ app

TABLES = {"categories": "Categories", "tasks": "Tasks", "milestones": "Milestones"}

CSS = """
FormScreen, ConfirmScreen { align: center middle; }
#form { width: 70; height: auto; max-height: 100%; border: thick $primary;
        background: $surface; padding: 0 2; }
#form-title { text-style: bold; margin: 1 0; }
.field-label { margin-top: 1; color: $text-muted; }
#form Input { border: none; height: 1; padding: 0 1; background: $boost; }
#form-error { color: $error; height: auto; margin-top: 1; }
#form-buttons { height: auto; margin: 1 0; align-horizontal: right; }
#form-buttons Button { margin-left: 2; }
Input.-invalid { background: $error 30%; }
#settings Input { border: none; height: 1; padding: 0 1; background: $boost; }
#settings .field-label { margin-top: 1; }
.hint { color: $text-muted; padding: 0 1; height: auto; }
DataTable { height: 1fr; }
#preview { width: auto; padding: 1; }
"""


class GanttApp(App[None]):
    CSS = CSS
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+s", "save", "Save"),
        Binding("f5", "export", "Export PNG"),
        Binding("f6", "view", "View PNG"),
        Binding("a", "add_item", "Add"),
        Binding("enter", "edit_item", "Edit", show=True),
        Binding("d,delete", "delete_item", "Delete"),
        Binding("[", "move(-1)", "Move up"),
        Binding("]", "move(1)", "Move down"),
    ]

    def __init__(self, path: Path, project: Project):
        super().__init__()
        self.path = path
        self.project = project
        self.dirty = False
        self.last_png: Path | None = None

    # ---- layout
    def compose(self) -> ComposeResult:
        p = self.project
        yield Header()
        with TabbedContent(id="tabs"):
            with TabPane("Settings", id="tab-settings"), VerticalScroll(id="settings"):
                for key, label, value in [
                    ("title", "Chart title", p.title),
                    ("start", "Week 1 starts on (YYYY-MM-DD)", p.semester_start.isoformat()),
                    ("weeks", "Number of weeks (grows automatically if tasks run past it)", str(p.weeks)),
                    ("today", "Today line: 'auto' = today's date, blank = none, or YYYY-MM-DD", p.today),
                    ("axis", "X-axis label (blank = generated from the start date)", p.axis_label),
                    ("output", "PNG file name (blank = same name as the project file)", p.output),
                ]:
                    yield Label(label, classes="field-label")
                    yield Input(value=value, id=f"set-{key}")
            with TabPane("Categories", id="tab-categories"):
                yield Label("Categories give tasks their bar colour and legend entry.", classes="hint")
                yield DataTable(id="categories", cursor_type="row", zebra_stripes=True)
            with TabPane("Tasks", id="tab-tasks"):
                yield Label("Row order = order on the chart.  a add · enter edit · d delete · [ ] reorder", classes="hint")
                yield DataTable(id="tasks", cursor_type="row", zebra_stripes=True)
            with TabPane("Milestones", id="tab-milestones"):
                yield Label("Diamonds above the chart. Use \\n in a label for a line break; week may be fractional (14.3).", classes="hint")
                yield DataTable(id="milestones", cursor_type="row", zebra_stripes=True)
            with TabPane("Preview", id="tab-preview"), ScrollableContainer():
                yield Static(id="preview")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#categories", DataTable).add_columns("", "Name", "Colour", "Tasks")
        self.query_one("#tasks", DataTable).add_columns("WBS", "Task", "Category", "Start wk", "Weeks", "Ends wk")
        self.query_one("#milestones", DataTable).add_columns("Week", "Label")
        self.refresh_all()

    def refresh_title(self) -> None:
        self.title = "Gantt chart builder"
        self.sub_title = f"{self.path.name}{' *' if self.dirty else ''}"

    def mark_dirty(self) -> None:
        self.dirty = True
        self.refresh_title()

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

    def refresh_table(self, kind: str, cursor: int | None = None) -> None:
        table = self.query_one(f"#{kind}", DataTable)
        row = table.cursor_row if cursor is None else cursor
        table.clear()
        for cells in self.rows(kind):
            table.add_row(*cells)
        if table.row_count:
            table.move_cursor(row=max(0, min(row, table.row_count - 1)))

    def refresh_all(self) -> None:
        for kind in TABLES:
            self.refresh_table(kind)
        self.refresh_title()

    def items(self, kind: str) -> list[Any]:
        return getattr(self.project, kind)

    # ---- which table is active (actions only apply when one is focused)
    def current_table(self) -> DataTable[Any] | None:
        f = self.focused
        return f if isinstance(f, DataTable) else None

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("add_item", "edit_item", "delete_item", "move"):
            return self.current_table() is not None
        return True

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        tab = (event.pane.id or "").removeprefix("tab-")
        if tab in TABLES:
            self.query_one(f"#{tab}", DataTable).focus()
        elif tab == "preview":
            self.query_one("#preview", Static).update(self.build_preview())
        self.refresh_bindings()

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
                if raw.strip().lower() != "auto":
                    core.parse_date(raw) if raw.strip() else None
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

    # ---- add / edit / delete / move
    def action_add_item(self) -> None:
        if table := self.current_table():
            self.open_form(table.id or "", None)

    def action_edit_item(self) -> None:
        if (table := self.current_table()) and table.row_count:
            self.open_form(table.id or "", table.cursor_row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        self.open_form(event.data_table.id or "", event.cursor_row)

    def action_delete_item(self) -> None:
        if not (table := self.current_table()) or not table.row_count:
            return
        kind, i = table.id or "", table.cursor_row
        if kind == "categories":
            used = sum(t.category == self.project.categories[i].name for t in self.project.tasks)
            if used:
                self.notify(f"{used} task(s) still use this category.", severity="warning")
                return
        del self.items(kind)[i]
        self.mark_dirty()
        self.refresh_all()

    def action_move(self, delta: int) -> None:
        if not (table := self.current_table()) or not table.row_count:
            return
        kind, i = table.id or "", table.cursor_row
        items, j = self.items(kind), i + delta
        if 0 <= j < len(items):
            items[i], items[j] = items[j], items[i]
            self.mark_dirty()
            self.refresh_table(kind, cursor=j)

    def open_form(self, kind: str, index: int | None) -> None:
        p = self.project
        items = self.items(kind)
        old = items[index] if index is not None else None
        verb = "Add" if old is None else "Edit"

        if kind == "categories":
            title = f"{verb} category"
            fields = [Field("name", "Name", old.name if old else ""),
                      Field("color", "Colour (hex, e.g. #377EB8)",
                            old.color if old else core.PALETTE[len(items) % len(core.PALETTE)])]

            def validate(raw: dict[str, str]) -> Item:
                name = need(raw["name"], "Name")
                if any(c.name == name and c is not old for c in items):
                    raise ValueError("A category with that name already exists.")
                color = raw["color"].strip()
                if not core.HEX_RE.match(color):
                    raise ValueError("Colour must look like #RRGGBB.")
                return Category(name, color)

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
                            old.category if old and old.category in names else names[0], choices=names),
                      Field("start", "Start week (1 = first week)", fmt_num(old.start) if old else "1"),
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

        def done(result) -> None:
            if result is None:
                return
            if kind == "categories" and old and old.name != result.name:
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

        self.push_screen(FormScreen(title, fields, validate), done)

    # ---- preview (rough text version of the chart)
    def build_preview(self) -> Text:
        p = self.project
        if not p.tasks:
            return Text("No tasks yet - add some on the Tasks tab.", style="dim")
        weeks = core.effective_weeks(p)
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
            today = core.today_date(p)
        except ValueError:
            today = None
        if today:
            out.append(f"\nToday: {today:%b} {today.day} (week {((today - p.semester_start).days) / 7 + 1:.1f})", style="red")
        for m in p.milestones:
            out.append(f"\n◆ week {fmt_num(m.week)}: {m.label.replace(chr(10), ' ')}")
        out.append("\n\nRough preview - press F5 for the real chart.", style="dim")
        return out

    # ---- files
    def action_save(self) -> None:
        core.save_project(self.project, self.path)
        self.dirty = False
        self.refresh_title()
        self.notify(f"Saved {self.path}")

    async def action_export(self) -> None:
        out = core.output_path(self.project, self.path)
        try:
            await asyncio.to_thread(core.render, self.project, out)
        except (ValueError, OSError) as e:
            self.notify(str(e), severity="error", title="Export failed")
            return
        self.last_png = out
        self.notify(f"{out}\nPress F6 to open it.", title="Chart exported")

    def action_view(self) -> None:
        png = self.last_png or core.output_path(self.project, self.path)
        if not png.exists():
            self.notify("Nothing exported yet - press F5 first.", severity="warning")
            return
        open_file(png)

    async def action_quit(self) -> None:
        if not self.dirty:
            self.exit()
            return
        self.push_screen(ConfirmScreen("You have unsaved changes. Quit anyway?"),
                         lambda yes: self.exit() if yes else None)


def open_file(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    ap = argparse.ArgumentParser(description="Terminal Gantt chart builder")
    ap.add_argument("project", nargs="?", default="gantt_project.json", help="project JSON file (created if missing)")
    ap.add_argument("--render", action="store_true", help="write the PNG and exit without opening the editor")
    args = ap.parse_args()

    path = Path(args.project)
    project = core.load_project(path) if path.exists() else Project.starter()
    if args.render:
        print(core.render(project, core.output_path(project, path)))
        return
    GanttApp(path, project).run()


if __name__ == "__main__":
    main()
