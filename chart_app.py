"""
PyChart Builder - a terminal app (Linux / Windows / macOS) that draws PNG charts.

    python chart_app.py                          open your most recent chart (or pick a type if you have none)
    python chart_app.py [project.json]           open (or start) a specific project file
    python chart_app.py project.json --render    just write the PNG and exit
    python chart_app.py data.csv --type bar      build a chart from a CSV file (add --render for just the PNG)
    python chart_app.py --list-types             show the chart types

Fill in the tabs, press F5, and a PNG chart is written next to the project file.
Ctrl+P opens the menu: switch between saved charts, start a new one, import a CSV, save a copy.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

from rich.text import Text
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Label, OptionList
from textual.widgets.option_list import Option

import chart_core as core
import charts
from charts import CHART_TYPES, ChartType, CsvError
from editor_base import EditorScreen
from editor_gantt import GanttEditor
from editor_table import TableEditor
from ui import CSS, ConfirmScreen, Field, FormScreen, Panel

NEW_PROJECT_NAME = "My {}"


# ------------------------------------------------------------------ dialogs

class PickerScreen(ModalScreen[str | None]):
    """Choose a chart type. Dismisses with the chart type id, or None if cancelled."""
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "close", "Cancel")]
    AUTO_FOCUS = "OptionList"

    def __init__(self, title: str = "Choose a chart type"):
        super().__init__()
        self.heading = title

    def compose(self) -> ComposeResult:
        with Panel(id="form"):
            yield Label(self.heading, id="form-title")
            yield OptionList(*(Option(Text.assemble((c.label, "bold"), ("\n  " + c.description, "dim")), id=c.id)
                               for c in CHART_TYPES.values()), id="chart-list")
            yield Label("↑/↓ choose · Enter select · esc cancel", classes="hint")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_close(self) -> None:
        self.dismiss(None)


class InfoScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "close", "Close"), ("enter", "close", "Close")]
    AUTO_FOCUS = "Button"

    def __init__(self, title: str, text: str):
        super().__init__()
        self.heading, self.text = title, text

    def compose(self) -> ComposeResult:
        with Panel(id="form"):
            yield Label(self.heading, id="form-title")
            yield Label(self.text)
            with Horizontal(id="form-buttons"):
                yield Button("Close", variant="primary", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


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
            kind = CHART_TYPES.get(core.project_type_of(path))
            saved = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone()
            out.append(f"  ·  {kind.label if kind else 'unknown type'}  ·  {saved:%Y-%m-%d %H:%M}", style="dim")
        else:
            out.append("  ·  not saved yet", style="dim")
        return out

    def compose(self) -> ComposeResult:
        with Panel(id="form"):
            yield Label("Projects", id="form-title")
            yield Label(f"Saved in {core.projects_dir()}", classes="hint")
            yield OptionList(*(Option(self.label(p), id=str(i)) for i, p in enumerate(self.entries)),
                             id="project-list")
            yield Label("Enter open · n new chart · s save a copy as · esc close", classes="hint")
            with Horizontal(id="form-buttons"):
                yield Button("Open", variant="primary", id="open")
                yield Button("New chart", id="new")
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


# ------------------------------------------------------------------------ app

def clean_path(raw: str) -> Path:
    """A path as typed or pasted (Windows 'Copy as path' wraps it in quotes)."""
    return Path(raw.strip().strip('"').strip("'")).expanduser()


def unused_project_path(stem: str) -> Path:
    base = core.project_filename(stem)[:-5]
    path = core.projects_dir() / f"{base}.json"
    n = 2
    while path.exists():
        path = core.projects_dir() / f"{base} {n}.json"
        n += 1
    return path


class ChartApp(App[None]):
    CSS = CSS
    BINDINGS: ClassVar[list[BindingType]] = [
        # Declaring the palette binding ourselves is what lets us rename its footer label.
        Binding("ctrl+p", "command_palette", "Settings", show=False, priority=True,
                tooltip="Theme, charts, import and export"),
        Binding("ctrl+s", "save", "Save"),
        Binding("f5", "export", "Export PNG"),
        Binding("f6", "view", "View PNG"),
    ]

    def __init__(self, path: Path | None = None, project: Any | None = None, dirty: bool = False):
        super().__init__()
        self.path = path or core.projects_dir() / "My Chart.json"
        self.project = project
        self.dirty = dirty
        self.last_png: Path | None = None

    @property
    def chart(self) -> ChartType:
        return charts.get(self.project.type)

    # ---- startup: the last chart opens by itself; with none saved you choose a type first
    def on_mount(self) -> None:
        if self.project is None:
            self.pick_new_chart(first_run=True)
        else:
            self.show_editor()

    def show_editor(self) -> None:
        editor: EditorScreen = GanttEditor() if self.chart.editor == "gantt" else TableEditor()
        if isinstance(self.screen, EditorScreen):
            self.switch_screen(editor)
        else:
            self.push_screen(editor)
        self.refresh_title()

    def refresh_title(self) -> None:
        self.title = "PyChart Builder"
        label = self.chart.label if self.project is not None else ""
        self.sub_title = f"{self.path.stem}{' *' if self.dirty else ''}  ·  {label}"

    def mark_dirty(self) -> None:
        self.dirty = True
        self.refresh_title()

    def editor(self) -> EditorScreen | None:
        return next((s for s in reversed(self.screen_stack) if isinstance(s, EditorScreen)), None)

    # ---- the Ctrl+P menu: Textual's built-in commands (theme, quit, ...) plus ours
    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        if self.project is None:
            return
        yield SystemCommand("Projects", "Switch chart, start a new one or save a copy", self.action_projects)
        yield SystemCommand("New chart", "Start a blank chart of any type",
                            lambda: self.projects_chosen(("new", None)))
        yield SystemCommand("Import CSV as a new chart", "Build a chart from a CSV file", self.import_new)
        yield SystemCommand("Import CSV into this chart", "Replace this chart's data with a CSV file",
                            self.import_here)
        yield SystemCommand("CSV format help", "What the CSV for this chart type should look like", self.csv_help)
        yield SystemCommand("Save project as", "Save the current chart under a new name",
                            lambda: self.projects_chosen(("saveas", None)))
        for path in core.list_projects():
            if path.resolve() != self.path.resolve():
                yield SystemCommand(f"Open project: {path.stem}", "Switch to this chart",
                                    lambda path=path: self.open_project(path))
        yield SystemCommand("Save", "Save the current project", self.action_save)
        yield SystemCommand("Export PNG", "Write the chart image", self.action_export)
        yield SystemCommand("View PNG", "Open the exported image", self.action_view)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("save", "export", "view", "projects"):
            return self.project is not None and not isinstance(self.screen, ModalScreen)
        return True

    # ---- projects
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
            self.pick_new_chart(first_run=False)
        elif action == "saveas":
            self.ask_project_name("Save a copy as", f"{self.path.stem} copy", self.save_as)

    def pick_new_chart(self, first_run: bool) -> None:
        def chosen(type_id: str | None) -> None:
            if type_id is None:
                if first_run:
                    self.exit()
                return
            chart = charts.get(type_id)
            suggestion = unused_project_path(NEW_PROJECT_NAME.format(chart.label.split(" / ")[0].lower())).stem
            self.ask_project_name("Name your chart", suggestion,
                                  lambda path: self.create_project(chart, path),
                                  on_cancel=(lambda: self.pick_new_chart(first_run)) if first_run else None)

        self.push_screen(PickerScreen("Choose a chart type" if not first_run else "No charts yet - choose a type"),
                         chosen)

    def ask_project_name(self, title: str, initial: str, then: Callable[[Path], None],
                         on_cancel: Callable[[], None] | None = None) -> None:
        def validate(raw: dict[str, str]) -> Path:
            path = core.projects_dir() / core.project_filename(raw["name"])
            if path.exists():
                raise ValueError("A project with that name already exists.")
            return path

        def done(result: Path | None) -> None:
            if isinstance(result, Path):
                then(result)
            elif on_cancel:
                on_cancel()

        self.push_screen(FormScreen(title, [Field("name", "Project name", initial)], validate), done)

    def save_current(self) -> bool:
        """Save unsaved work before switching away. False if it couldn't be saved."""
        if self.project is None or not self.dirty:
            return True
        try:
            core.save_project(self.project, self.path)
        except OSError as e:
            self.notify(f"Couldn't save {self.path.name}: {e}", severity="error")
            return False
        self.notify(f"Saved {self.path.stem}")
        return True

    def switch_to(self, path: Path, project: Any, dirty: bool = False) -> None:
        """Make `project` the open one. Unsaved work in the current project is saved first."""
        if not self.save_current():
            return
        self.path, self.project, self.dirty, self.last_png = path, project, dirty, None
        self.show_editor()
        self.notify(f"Opened {path.stem}")

    def open_project(self, path: Path) -> None:
        if self.project is not None and path.resolve() == self.path.resolve():
            return
        try:
            project = core.load_project(path)
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.notify(f"Couldn't open {path.name}: {e}", severity="error")
            return
        self.switch_to(path, project)

    def create_project(self, chart: ChartType, path: Path) -> None:
        project = chart.new(path.stem)
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

    # ---- CSV
    def import_new(self) -> None:
        labels = {c.label: c for c in CHART_TYPES.values()}

        def validate(raw: dict[str, str]) -> tuple[ChartType, Any, Path]:
            chart = labels[raw["type"]]
            csv_path = clean_path(raw["file"])
            project = chart.from_csv(csv_path, raw["name"].strip() or csv_path.stem)
            path = core.projects_dir() / core.project_filename(raw["name"].strip() or csv_path.stem)
            if path.exists():
                raise ValueError("A project with that name already exists - choose another name.")
            return chart, project, path

        def done(result: Any) -> None:
            if result is not None:
                _chart, project, path = result
                self.switch_to(path, project, dirty=True)

        self.push_screen(FormScreen("Import CSV as a new chart", [
            Field("type", "Chart type", self.chart.label, choices=list(labels)),
            Field("file", "CSV file (full path)"),
            Field("name", "Project name (blank = the file name)"),
        ], validate), done)

    def import_here(self) -> None:
        chart, project = self.chart, self.project

        def validate(raw: dict[str, str]) -> Any:
            return chart.from_csv(clean_path(raw["file"]), project.title)

        def done(imported: Any) -> None:
            if imported is None:
                return
            chart.replace_data(project, imported)
            self.mark_dirty()
            if ed := self.editor():
                ed.reload()
            self.notify("Data replaced from the CSV file.")

        self.push_screen(FormScreen(f"Import CSV into this {chart.label.lower()} - replaces its data", [
            Field("file", "CSV file (full path)")], validate), done)

    def csv_help(self) -> None:
        chart = self.chart
        self.push_screen(InfoScreen(f"CSV format - {chart.label}",
                                    f"{chart.csv_help}\n\nExample files are in the examples/ folder; "
                                    f"details in docs/csv/{chart.id}.md."))

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
            await asyncio.to_thread(self.chart.render, self.project, out)
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


def most_recent_project() -> tuple[Path, Any] | None:
    """The last project worked on, or None if nothing usable is saved yet."""
    for path in core.list_projects():
        try:
            return path, core.load_project(path)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Terminal chart builder: Gantt, bar, line, pie and more")
    ap.add_argument("file", nargs="?", help="project .json file, or a .csv file (needs --type); "
                                            "default: your most recent chart")
    ap.add_argument("--type", choices=list(CHART_TYPES), metavar="TYPE",
                    help="chart type for a CSV file or a new project (see --list-types)")
    ap.add_argument("--render", action="store_true", help="write the PNG and exit without opening the editor")
    ap.add_argument("--list-types", action="store_true", help="list the chart types and exit")
    args = ap.parse_args()

    if args.list_types:
        for c in CHART_TYPES.values():
            print(f"{c.id:<10} {c.label} - {c.description}")
        return

    path: Path | None = None
    project: Any = None
    dirty = False
    if args.file:
        given = Path(args.file).expanduser()
        if given.suffix.lower() == ".csv":
            if not args.type:
                ap.error("a CSV file needs --type (see --list-types), e.g. --type bar")
            try:
                project = charts.get(args.type).from_csv(given, given.stem)
            except CsvError as e:
                ap.exit(2, f"{e}\n")
            path, dirty = (given.with_suffix(".json") if args.render else unused_project_path(given.stem)), True
        elif given.exists():
            try:
                project, path = core.load_project(given), given
            except (OSError, ValueError, KeyError, TypeError) as e:
                ap.exit(1, f"Couldn't open {given}: {e}\n")
        else:
            if args.render:
                ap.error(f"{given} doesn't exist")
            path, project = given, charts.get(args.type or "gantt").new(given.stem)
    elif args.render:
        ap.error("--render needs a project or CSV file")
    elif found := most_recent_project():
        path, project = found
    if args.render:
        assert path is not None
        chart = charts.get(project.type)
        try:
            print(chart.render(project, core.output_path(project, path)))
        except ValueError as e:
            ap.exit(1, f"{e}\n")
        return
    ChartApp(path, project, dirty).run()


if __name__ == "__main__":
    main()
