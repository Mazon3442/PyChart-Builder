"""
Gantt chart builder - a terminal app (Linux / Windows / macOS).

    python gantt_app.py                        open the editor on your most recent project
    python gantt_app.py [project.json]         open (or start) a specific project file
    python gantt_app.py project.json --render  just write the PNG and exit

Fill in the tabs, press F5, and a PNG chart is written next to the project file.
Ctrl+P opens the project menu: switch between saved charts, start a new one, save a copy.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

from rich.text import Text
from textual import events
from textual.actions import SkipAction
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, ScrollableContainer, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Select,
    Static,
    TabbedContent,
    TabPane,
    Tabs,
)
from textual.widgets.option_list import Option

import gantt_core as core
from gantt_core import Category, Milestone, Project, Task, fmt_num

Item = Category | Task | Milestone
Result = Item | Path


# ------------------------------------------------------------------- widgets

class Panel(VerticalScroll, can_focus=False):
    """A scrolling box that never takes focus itself, so arrow keys land on the fields inside."""


class ItemTable(DataTable[Any]):
    """Table whose left/right arrows switch tabs (a row cursor has no use for them)."""

    def action_cursor_left(self) -> None:
        if isinstance(self.app, GanttApp):
            self.app.action_switch_tab(-1)

    def action_cursor_right(self) -> None:
        if isinstance(self.app, GanttApp):
            self.app.action_switch_tab(1)


AUTO, CUSTOM = -1, -2   # ColorPicker selections that aren't a swatch
CELL = 5                # width of one swatch in characters


class ColorPicker(Widget, can_focus=True):
    """Grid of colour swatches plus an 'auto-pick' choice. Arrow keys or mouse to choose."""

    DEFAULT_CSS = """
    ColorPicker { height: 7; width: 42; border: round $panel; }
    ColorPicker:focus { border: round $accent; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "move(-1, 0)", show=False),
        Binding("right", "move(1, 0)", show=False),
        Binding("up", "move(0, -1)", show=False),
        Binding("down", "move(0, 1)", show=False),
    ]

    class Changed(Message):
        def __init__(self, picker: ColorPicker) -> None:
            super().__init__()
            self.picker = picker
            self.value = picker.value

    def __init__(self, value: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        lowered = [s.lower() for s in core.SWATCHES]
        if not value:
            self.sel = AUTO
        else:
            self.sel = lowered.index(value.lower()) if value.lower() in lowered else CUSTOM

    @property
    def value(self) -> str:
        """Hex code of the chosen swatch, or '' for auto-pick / a custom colour."""
        return core.SWATCHES[self.sel] if self.sel >= 0 else ""

    def choose(self, sel: int) -> None:
        if sel != self.sel:
            self.sel = sel
            self.refresh()
            self.post_message(self.Changed(self))

    def action_move(self, dx: int, dy: int) -> None:
        cols, n, s = core.SWATCH_COLS, len(core.SWATCHES), self.sel
        if s < 0:
            if dy > 0 or (s == CUSTOM and dx):
                self.choose(0)
            elif dy < 0 and s == AUTO:
                raise SkipAction()  # leave the picker upwards
            return
        row, col = divmod(s, cols)
        col = max(0, min(cols - 1, col + dx))
        row += dy
        if row < 0:
            self.choose(AUTO)
        elif row * cols + col >= n:
            raise SkipAction()  # leave the picker downwards
        else:
            self.choose(row * cols + col)

    def on_click(self, event: events.Click) -> None:
        pos = event.get_content_offset(self)
        if pos is None:
            return
        if pos.y == 0:
            self.choose(AUTO)
            return
        col, idx = pos.x // CELL, (pos.y - 1) * core.SWATCH_COLS + pos.x // CELL
        if col < core.SWATCH_COLS and 0 <= idx < len(core.SWATCHES):
            self.choose(idx)

    def render(self) -> Text:
        out = Text(no_wrap=True)
        auto = self.sel == AUTO
        out.append((" ✓ " if auto else "   ") + "Auto-pick a colour for me".ljust(core.SWATCH_COLS * CELL - 3),
                   style="bold reverse" if auto else "bold")
        for i, color in enumerate(core.SWATCHES):
            if i % core.SWATCH_COLS == 0:
                out.append("\n")
            r, g, b = (int(color[k:k + 2], 16) for k in (1, 3, 5))
            fg = "black" if 0.299 * r + 0.587 * g + 0.114 * b > 160 else "white"
            out.append(f"  {'✓' if i == self.sel else ' '}  ", style=f"{fg} on {color}")
        return out


# ------------------------------------------------------------------ dialogs

@dataclass
class Field:
    key: str
    label: str
    value: str = ""
    choices: list[str] | None = None  # set -> dropdown instead of text box
    picker: bool = False              # set -> colour swatches above the text box


class FormScreen(ModalScreen[Result | None]):
    """Modal form. `validate(raw: dict[str, str])` returns a result or raises ValueError."""
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "cancel", "Cancel"),
        Binding("up", "nav_focus(-1)", show=False),
        Binding("down", "nav_focus(1)", show=False),
    ]
    AUTO_FOCUS = "Input, Select"

    def __init__(self, title: str, fields: list[Field], validate: Callable[[dict[str, str]], Result]):
        super().__init__()
        self.form_title, self.fields, self.validate = title, fields, validate

    def compose(self) -> ComposeResult:
        with Panel(id="form"):
            yield Label(self.form_title, id="form-title")
            for f in self.fields:
                yield Label(f.label, classes="field-label")
                if f.choices is not None:
                    yield Select([(c, c) for c in f.choices], value=f.value,
                                 allow_blank=False, id=f"f-{f.key}")
                elif f.picker:
                    yield ColorPicker(f.value, id=f"p-{f.key}")
                    yield Label("Or type your own hex code (optional)", classes="field-label")
                    yield Input(value=f.value, id=f"f-{f.key}", placeholder="#RRGGBB")
                else:
                    yield Input(value=f.value, id=f"f-{f.key}")
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

    def on_color_picker_changed(self, event: ColorPicker.Changed) -> None:
        key = (event.picker.id or "")[2:]
        self.query_one(f"#f-{key}", Input).value = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.submit() if event.button.id == "save" else self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_nav_focus(self, delta: int) -> None:
        """↑/↓ move between fields (the colour picker uses them itself until you leave it)."""
        if delta > 0:
            self.focus_next()
        else:
            self.focus_previous()


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "no", "No"), ("y", "yes", "Yes"), ("n", "no", "No")]
    AUTO_FOCUS = "Button"

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Panel(id="form"):
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


class ProjectsScreen(ModalScreen[tuple[str, Path | None] | None]):
    """Project menu. Dismisses with ('open', path), ('new', None), ('saveas', None) or None."""
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "close", "Close"), ("n", "new", "New"), ("s", "save_as", "Save as"),
    ]
    AUTO_FOCUS = "OptionList"

    def __init__(self, current: Path):
        super().__init__()
        self.current = current.resolve()
        self.entries = core.list_projects()
        if self.current not in [e.resolve() for e in self.entries]:
            self.entries.insert(0, current)  # not saved yet, or lives outside the projects folder

    def label(self, path: Path) -> Text:
        here = path.resolve() == self.current
        out = Text()
        out.append("● " if here else "  ", style="green")
        out.append(path.stem, style="bold" if here else "")
        if path.exists():
            saved = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone()
            out.append(f"  ·  {saved:%Y-%m-%d %H:%M}", style="dim")
        else:
            out.append("  ·  not saved yet", style="dim")
        return out

    def compose(self) -> ComposeResult:
        with Panel(id="form"):
            yield Label("Projects", id="form-title")
            yield Label(f"Saved in {core.projects_dir()}", classes="hint")
            yield OptionList(*(Option(self.label(p), id=str(i)) for i, p in enumerate(self.entries)),
                             id="project-list")
            yield Label("Enter open · n new · s save a copy as · esc close", classes="hint")
            with Horizontal(id="form-buttons"):
                yield Button("Open", variant="primary", id="open")
                yield Button("New project", id="new")
                yield Button("Save as…", id="saveas")

    def on_mount(self) -> None:
        for i, p in enumerate(self.entries):
            if p.resolve() == self.current:
                self.query_one(OptionList).highlighted = i

    def open_highlighted(self) -> None:
        i = self.query_one(OptionList).highlighted
        if i is not None:
            self.dismiss(("open", self.entries[i]))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(("open", self.entries[event.option_index]))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "open":
                self.open_highlighted()
            case "new":
                self.dismiss(("new", None))
            case "saveas":
                self.dismiss(("saveas", None))
            case _:
                self.dismiss(None)

    def action_new(self) -> None:
        self.dismiss(("new", None))

    def action_save_as(self) -> None:
        self.dismiss(("saveas", None))

    def action_close(self) -> None:
        self.dismiss(None)


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


def next_start(tasks: list[Task]) -> str:
    """A new task starts the week after the previous one ends."""
    return fmt_num(tasks[-1].start + tasks[-1].duration) if tasks else "1"


def parse_color(raw: str, others: list[Category]) -> str:
    """Hex colour as typed, or the next free swatch when left blank."""
    raw = raw.strip()
    if not raw:
        return core.auto_color(others)
    if re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raw = "#" + raw
    if not core.HEX_RE.match(raw):
        raise ValueError("That isn't a hex code like #377EB8. Pick a swatch or leave it blank for auto.")
    return raw


# ------------------------------------------------------------------------ app

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

CSS = """
FormScreen, ConfirmScreen, ProjectsScreen { align: center middle; }
#form { width: 70; height: auto; max-height: 100%; border: thick $primary;
        background: $surface; padding: 0 2; }
#form-title { text-style: bold; margin: 1 0; }
.field-label { margin-top: 1; color: $text-muted; width: 100%; }
#form Input { border: none; height: 1; padding: 0 1; background: $boost; }
#form-error { color: $error; height: auto; margin-top: 1; }
#form-buttons { height: auto; margin: 1 0; align-horizontal: right; }
#form-buttons Button { margin-left: 2; }
#project-list { height: auto; max-height: 14; margin-top: 1; }
Input.-invalid { background: $error 30%; }
#settings Input { border: none; height: 1; padding: 0 1; background: $boost; }
#settings .field-label { margin-top: 1; }
.hint { color: $text-muted; padding: 0 1; height: auto; width: 100%; }
DataTable { height: 1fr; }
#preview { width: auto; padding: 1; }
"""


class GanttApp(App[None]):
    CSS = CSS
    ENABLE_COMMAND_PALETTE = False  # Ctrl+P is the project menu instead
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+p", "projects", "Projects"),
        Binding("ctrl+s", "save", "Save"),
        Binding("f5", "export", "Export PNG"),
        Binding("f6", "view", "View PNG"),
        Binding("a", "add_item", "Add"),
        Binding("enter", "edit_item", "Edit", show=True),
        Binding("d,delete", "delete_item", "Delete"),
        Binding("[", "move(-1)", "Move up"),
        Binding("]", "move(1)", "Move down"),
        Binding("up", "nav_focus(-1)", show=False),
        Binding("down", "nav_focus(1)", show=False),
    ]

    def __init__(self, path: Path, project: Project):
        super().__init__()
        self.path = path
        self.project = project
        self.dirty = False
        self.last_png: Path | None = None

    # ---- layout
    def settings_values(self) -> dict[str, str]:
        p = self.project
        return {"title": p.title, "start": p.semester_start.isoformat(), "weeks": str(p.weeks),
                "today": p.today, "axis": p.axis_label, "output": p.output}

    def compose(self) -> ComposeResult:
        values = self.settings_values()
        yield Header(icon=" ")  # Textual disables the icon when the command palette is off
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

    def refresh_title(self) -> None:
        self.title = "Gantt chart builder"
        self.sub_title = f"{self.path.stem}{' *' if self.dirty else ''}"

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
        if action == "projects":
            return not isinstance(self.screen, ModalScreen)
        return True

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        tab = (event.pane.id or "").removeprefix("tab-")
        if tab in TABLES:
            self.query_one(f"#{tab}", DataTable).focus()
        else:
            # Keep focus somewhere ←/→ still switch tabs (not inside a text box).
            self.query_one(TabbedContent).query_one(Tabs).focus()
            if tab == "preview":
                self.query_one("#preview", Static).update(self.build_preview())
        self.refresh_bindings()

    # ---- keyboard navigation
    def action_switch_tab(self, delta: int) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = TAB_ORDER[(TAB_ORDER.index(tabs.active) + delta) % len(TAB_ORDER)]  # wraps, like the tab bar

    def action_nav_focus(self, delta: int) -> None:
        """↑/↓ move between boxes (tables, lists and the colour picker use them for themselves)."""
        if delta > 0:
            self.screen.focus_next()
        else:
            self.screen.focus_previous()

    # ---- settings
    def load_settings(self) -> None:
        for key, value in self.settings_values().items():
            box = self.query_one(f"#set-{key}", Input)
            box.value = value
            box.remove_class("-invalid")

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
                      Field("color", "Colour (leave on Auto and one is picked for you)",
                            old.color if old else "", picker=True)]

            def validate(raw: dict[str, str]) -> Item:
                name = need(raw["name"], "Name")
                if any(c.name == name and c is not old for c in items):
                    raise ValueError("A category with that name already exists.")
                return Category(name, parse_color(raw["color"], [c for c in items if c is not old]))

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

        def done(result: Result | None) -> None:
            if result is None or isinstance(result, Path):
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

    # ---- projects (Ctrl+P)
    def action_projects(self) -> None:
        if self.check_action("projects", ()):
            self.push_screen(ProjectsScreen(self.path), self.projects_chosen)

    def projects_chosen(self, result: tuple[str, Path | None] | None) -> None:
        if result is None:
            return
        action, path = result
        if action == "open" and path is not None:
            self.open_project(path)
        elif action == "new":
            self.ask_project_name("New project", "", self.create_project)
        elif action == "saveas":
            self.ask_project_name("Save a copy as", f"{self.path.stem} copy", self.save_as)

    def ask_project_name(self, title: str, initial: str, then: Callable[[Path], None]) -> None:
        def validate(raw: dict[str, str]) -> Result:
            path = core.projects_dir() / core.project_filename(raw["name"])
            if path.exists():
                raise ValueError("A project with that name already exists.")
            return path

        def done(result: Result | None) -> None:
            if isinstance(result, Path):
                then(result)

        self.push_screen(FormScreen(title, [Field("name", "Project name", initial)], validate), done)

    def switch_to(self, path: Path, project: Project) -> None:
        """Make `project` the open one. Unsaved work in the current project is saved first."""
        if self.dirty:
            try:
                core.save_project(self.project, self.path)
            except OSError as e:
                self.notify(f"Couldn't save {self.path.name}: {e}", severity="error")
                return
            self.notify(f"Saved {self.path.stem}")
        self.path, self.project, self.dirty, self.last_png = path, project, False, None
        self.load_settings()
        for kind in TABLES:
            self.refresh_table(kind, cursor=0)
        self.refresh_title()
        self.notify(f"Opened {path.stem}")

    def open_project(self, path: Path) -> None:
        if path.resolve() == self.path.resolve():
            return
        try:
            project = core.load_project(path)
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.notify(f"Couldn't open {path.name}: {e}", severity="error")
            return
        self.switch_to(path, project)

    def create_project(self, path: Path) -> None:
        project = Project.starter()
        project.title = path.stem
        try:
            core.save_project(project, path)
        except OSError as e:
            self.notify(f"Couldn't create {path.name}: {e}", severity="error")
            return
        self.switch_to(path, project)

    def save_as(self, path: Path) -> None:
        """Write the current chart to a new file and carry on editing that one."""
        try:
            core.save_project(self.project, path)
        except OSError as e:
            self.notify(f"Couldn't save {path.name}: {e}", severity="error")
            return
        self.path, self.dirty, self.last_png = path, False, None
        self.refresh_title()
        self.notify(f"Saved a copy as {path.stem}")

    # ---- files
    def action_save(self) -> None:
        try:
            core.save_project(self.project, self.path)
        except OSError as e:
            self.notify(str(e), severity="error", title="Save failed")
            return
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


def most_recent_project() -> tuple[Path, Project]:
    """The last project worked on, or a fresh one if none are saved yet."""
    for path in core.list_projects():
        try:
            return path, core.load_project(path)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return core.projects_dir() / "My Project.json", Project.starter()


def main() -> None:
    ap = argparse.ArgumentParser(description="Terminal Gantt chart builder")
    ap.add_argument("project", nargs="?", help="project JSON file (default: your most recent project)")
    ap.add_argument("--render", action="store_true", help="write the PNG and exit without opening the editor")
    args = ap.parse_args()

    if args.project:
        path = Path(args.project)
        project = core.load_project(path) if path.exists() else Project.starter()
    elif args.render:
        ap.error("--render needs a project file")
    else:
        path, project = most_recent_project()
    if args.render:
        print(core.render(project, core.output_path(project, path)))
        return
    GanttApp(path, project).run()


if __name__ == "__main__":
    main()
