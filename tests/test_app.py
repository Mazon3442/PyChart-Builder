"""Drive the real terminal app with Textual's test pilot."""
import asyncio
import shutil
from pathlib import Path

import chart_app
import filepicker
import pytest
import chart_core as core
import charts
import ui
from charts import CHART_TYPES
from editor_gantt import GanttEditor
from editor_table import TableEditor
from textual.widgets import DataTable

ROOT = Path(__file__).resolve().parent.parent
SIZE = (120, 40)


REAL_PICK_CSV = filepicker.pick_csv


@pytest.fixture(autouse=True)
def no_native_dialog(monkeypatch):
    """Never pop a real file dialog from a test: by default there is none, so the form is used."""
    monkeypatch.setattr(filepicker, "pick_csv", lambda start=None: (False, None))


def run(coro):
    return asyncio.run(coro)


async def type_text(pilot, text):
    for ch in text:
        await pilot.press("space" if ch == " " else ch)


def save_chart(chart_id, path, csv_name=None):
    chart = CHART_TYPES[chart_id]
    project = chart.from_csv(ROOT / "examples" / f"{csv_name or chart_id}.csv", path.stem)
    core.save_project(project, path)
    return project


def test_first_run_asks_for_a_chart_type_then_a_name(projects):
    async def go():
        app = chart_app.ChartApp(None, None)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, chart_app.PickerScreen)
            await pilot.press("down", "down", "down")  # gantt, bar, line, pie
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, chart_app.FormScreen)
            await pilot.press("enter")  # accept the suggested name
            await pilot.pause()
            assert isinstance(app.screen, TableEditor)
            assert app.project.type == "pie"
            assert app.path.exists() and app.path.parent == projects

    run(go())


def test_escape_on_first_run_quits(projects):
    async def go():
        app = chart_app.ChartApp(None, None)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert not app.is_running

    run(go())


def test_name_dialog_cancel_returns_to_the_picker_on_first_run(projects):
    async def go():
        app = chart_app.ChartApp(None, None)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, chart_app.FormScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, chart_app.PickerScreen)

    run(go())


def test_most_recent_chart_is_loaded_by_default(projects):
    save_chart("bar", projects / "older.json")
    newer = projects / "newer.json"
    save_chart("pie", newer)
    import os
    os.utime(projects / "older.json", (1, 1))
    path, project = chart_app.most_recent_project()
    assert path.name == "newer.json" and project.type == "pie"


def test_most_recent_skips_unreadable_files(projects):
    save_chart("bar", projects / "good.json")
    (projects / "bad.json").write_text("{not json", encoding="utf-8")
    import os
    os.utime(projects / "good.json", (1, 1))
    path, _project = chart_app.most_recent_project()
    assert path.name == "good.json"


def test_nothing_saved_means_nothing_to_load(projects):
    assert chart_app.most_recent_project() is None


def test_gantt_project_opens_in_the_gantt_editor(projects):
    path = projects / "deer.json"
    shutil.copy(ROOT / "examples" / "deer_alarm.json", path)
    project = core.load_project(path)

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, GanttEditor)
            assert app.screen.query_one("#tasks", DataTable).row_count == len(project.tasks)

    run(go())


def test_adding_a_series_and_rows_in_a_bar_chart(projects):
    path = projects / "b.json"
    project = CHART_TYPES["bar"].new("b")
    core.save_project(project, path)

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            ed = app.screen
            assert isinstance(ed, TableEditor)
            # a second series
            ed.query_one("TabbedContent").active = "tab-series"
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await type_text(pilot, "Costs")
            await pilot.press("enter")
            await pilot.pause()
            assert [s[0] for s in project.tables["series"]] == ["Series 1", "Costs"]
            assert project.tables["series"][1][1], "a colour was picked automatically"
            # a data row with two values
            ed.query_one("TabbedContent").active = "tab-data"
            await pilot.pause()
            assert [str(c.label) for c in ed.query_one("#data", DataTable).ordered_columns] == \
                ["Label", "Series 1", "Costs"]
            await pilot.press("a")
            await pilot.pause()
            await type_text(pilot, "Jan")
            await pilot.press("tab")
            await type_text(pilot, "5")
            await pilot.press("tab")
            await type_text(pilot, "7.5")
            await pilot.press("enter")
            await pilot.pause()
            assert project.tables["data"] == [["Jan", 5.0, 7.5]]
            assert app.dirty
            # export and save
            await pilot.press("f5")
            await pilot.pause(0.5)
            assert core.output_path(project, path).stat().st_size > 1000
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert not app.dirty
            assert core.load_project(path).tables["data"] == [["Jan", 5.0, 7.5]]

    run(go())


def test_invalid_number_is_reported_in_the_form(projects):
    path = projects / "p.json"
    project = CHART_TYPES["pie"].new("p")
    core.save_project(project, path)

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            ed = app.screen
            ed.query_one("TabbedContent").active = "tab-data"
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await type_text(pilot, "Rent")
            await pilot.press("tab")
            await type_text(pilot, "lots")
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, chart_app.FormScreen)  # still open
            assert "must be a number" in str(app.screen.query_one("#form-error").render())
            assert project.tables["data"] == []

    run(go())


def test_import_csv_into_this_chart_replaces_data_but_keeps_settings(projects, tmp_path):
    path = projects / "p.json"
    project = CHART_TYPES["pie"].new("Mine")
    project.settings["style"] = "donut"
    core.save_project(project, path)
    csv_path = tmp_path / "data.csv"
    shutil.copy(ROOT / "examples" / "pie.csv", csv_path)

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.import_here()
            await pilot.pause()
            await type_text(pilot, f'"{csv_path}"')  # quoted, as Windows' "Copy as path" gives it
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, TableEditor)
            assert len(project.tables["data"]) == 5
            assert project.settings["style"] == "donut" and project.title == "Mine"
            assert app.dirty
            assert app.screen.query_one("#data", DataTable).row_count == 5

    run(go())


def test_import_csv_errors_show_in_the_dialog_and_change_nothing(projects, tmp_path):
    path = projects / "p.json"
    project = CHART_TYPES["pie"].new("Mine")
    core.save_project(project, path)
    bad = tmp_path / "bad.csv"
    bad.write_text("label,value\nA,1\nB,twelve\n", encoding="utf-8")

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.import_here()
            await pilot.pause()
            await type_text(pilot, str(bad))
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, chart_app.FormScreen)
            assert 'row 3, column "Value"' in str(app.screen.query_one("#form-error").render())
            assert project.tables["data"] == [] and not app.dirty

    run(go())


def test_switching_charts_saves_unsaved_work_and_changes_editor(projects):
    a, b = projects / "a.json", projects / "b.json"
    pa = save_chart("pie", a)
    save_chart("gantt", b)

    async def go():
        app = chart_app.ChartApp(a, pa)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, TableEditor)
            pa.title = "changed"
            app.mark_dirty()
            app.open_project(b)
            await pilot.pause()
            assert isinstance(app.screen, GanttEditor)
            assert app.path == b and not app.dirty
            assert core.load_project(a).title == "changed"
            app.open_project(a)
            await pilot.pause()
            assert isinstance(app.screen, TableEditor) and app.project.type == "pie"

    run(go())


def test_new_chart_from_the_projects_menu(projects):
    a = projects / "a.json"
    pa = save_chart("pie", a)

    async def go():
        app = chart_app.ChartApp(a, pa)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.projects_chosen(("new", None))
            await pilot.pause()
            assert isinstance(app.screen, chart_app.PickerScreen)
            await pilot.press("enter")  # the first entry: Gantt
            await pilot.pause()
            await pilot.press("enter")  # accept the name
            await pilot.pause()
            assert isinstance(app.screen, GanttEditor)
            assert len(core.list_projects()) == 2

    run(go())


def test_settings_changes_are_stored(projects):
    path = projects / "b.json"
    project = CHART_TYPES["bar"].new("b")
    core.save_project(project, path)

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            box = app.screen.query_one("#set-title")
            box.value = "Sales"
            await pilot.pause()
            assert project.title == "Sales" and app.dirty

    run(go())


def test_cli_render_from_csv(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "sales.csv"
    shutil.copy(ROOT / "examples" / "bar.csv", csv_path)
    monkeypatch.setattr("sys.argv", ["chart_app.py", str(csv_path), "--type", "bar", "--render"])
    chart_app.main()
    assert (tmp_path / "sales.png").stat().st_size > 1000
    assert str(tmp_path / "sales.png") in capsys.readouterr().out


def test_cli_csv_without_type_is_an_error(tmp_path, monkeypatch, capsys):
    csv_path = tmp_path / "x.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["chart_app.py", str(csv_path), "--render"])
    try:
        chart_app.main()
    except SystemExit as e:
        assert e.code == 2
    assert "--type" in capsys.readouterr().err


def test_cli_bad_csv_prints_the_message(tmp_path, monkeypatch, capsys):
    csv_path = tmp_path / "x.csv"
    csv_path.write_text("label,value\nA,oops\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["chart_app.py", str(csv_path), "--type", "pie", "--render"])
    try:
        chart_app.main()
    except SystemExit as e:
        assert e.code == 2
    assert 'column "Value": must be a number' in capsys.readouterr().err


def test_cli_render_empty_chart_is_a_message_not_a_traceback(tmp_path, monkeypatch, capsys):
    path = tmp_path / "empty.json"
    core.save_project(CHART_TYPES["pie"].new("e"), path)
    monkeypatch.setattr("sys.argv", ["chart_app.py", str(path), "--render"])
    try:
        chart_app.main()
    except SystemExit as e:
        assert e.code == 1
    assert "Add at least 1 row" in capsys.readouterr().err


def test_new_task_defaults_to_the_last_tasks_category(projects):
    path = projects / "deer.json"
    shutil.copy(ROOT / "examples" / "deer_alarm.json", path)
    project = core.load_project(path)
    project.tasks[-1].category = project.categories[3].name  # not the first category

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.screen.open_form("tasks", None)
            await pilot.pause()
            assert app.screen.query_one("#f-category").value == project.categories[3].name

    run(go())


def test_dropdowns_work_from_the_keyboard(projects):
    path = projects / "deer.json"
    shutil.copy(ROOT / "examples" / "deer_alarm.json", path)
    project = core.load_project(path)
    names = [c.name for c in project.categories]

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.screen.open_form("tasks", None)
            await pilot.pause()
            form = app.screen
            select = form.query_one("#f-category")
            select.focus()
            await pilot.pause()
            # Down on a closed drop-down moves to the next box instead of opening it
            await pilot.press("down")
            assert app.focused is form.query_one("#f-start") and not select.expanded
            await pilot.press("up")
            assert app.focused is select
            # Enter opens it; the list starts on the current choice and stops at both ends
            await pilot.press("enter")
            await pilot.pause()
            assert select.expanded
            for _ in range(len(names) + 3):
                await pilot.press("down")
            assert select.query_one("SelectOverlay").highlighted == len(names) - 1
            for _ in range(len(names) + 3):
                await pilot.press("up")
            assert select.query_one("SelectOverlay").highlighted == 0
            await pilot.press("down", "enter")
            await pilot.pause()
            assert not select.expanded and select.value == names[1]

    run(go())


def test_f6_opens_the_png(projects, monkeypatch):
    path = projects / "p.json"
    project = save_chart("pie", path)
    opened = []
    monkeypatch.setattr(chart_app, "open_file", opened.append)

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("f6")  # nothing exported yet: a warning, not a crash
            await pilot.pause()
            assert opened == []
            await pilot.press("f5")
            await pilot.pause(0.7)
            await pilot.press("f6")
            await pilot.pause()
            assert opened == [core.output_path(project, path)]

    run(go())


def test_ctrl_l_opens_the_csv_import_dialog(projects):
    path = projects / "pie.json"
    project = charts.get("pie").new("pie")
    core.save_project(project, path)

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert isinstance(app.screen, ui.FormScreen)

    run(go())


def test_import_uses_the_file_dialog_when_there_is_one(projects, tmp_path, monkeypatch):
    path = projects / "p.json"
    project = CHART_TYPES["pie"].new("Mine")
    core.save_project(project, path)
    csv_path = tmp_path / "data.csv"
    shutil.copy(ROOT / "examples" / "pie.csv", csv_path)
    monkeypatch.setattr(filepicker, "pick_csv", lambda start=None: (True, csv_path))

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+l")
            await pilot.pause(0.3)
            assert isinstance(app.screen, TableEditor)  # no form: the chosen file was imported
            assert len(project.tables["data"]) == 5 and app.dirty

    run(go())


def test_cancelling_the_file_dialog_changes_nothing(projects, monkeypatch):
    path = projects / "p.json"
    project = CHART_TYPES["pie"].new("Mine")
    core.save_project(project, path)
    monkeypatch.setattr(filepicker, "pick_csv", lambda start=None: (True, None))

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+l")
            await pilot.pause(0.3)
            assert isinstance(app.screen, TableEditor) and not app.dirty

    run(go())


def test_new_chart_import_prefills_the_chosen_file(projects, tmp_path, monkeypatch):
    path = projects / "p.json"
    project = CHART_TYPES["pie"].new("Mine")
    core.save_project(project, path)
    csv_path = tmp_path / "data.csv"
    shutil.copy(ROOT / "examples" / "pie.csv", csv_path)
    monkeypatch.setattr(filepicker, "pick_csv", lambda start=None: (True, csv_path))

    async def go():
        app = chart_app.ChartApp(path, project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.import_new()
            await pilot.pause(0.3)
            assert isinstance(app.screen, chart_app.FormScreen)
            assert app.screen.query_one("#f-file").value == str(csv_path)

    run(go())


def test_picker_command_per_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(filepicker.sys, "platform", "linux")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setattr(filepicker.shutil, "which", lambda n: f"/usr/bin/{n}" if n == "zenity" else None)
    cmd = filepicker.picker_command(tmp_path)
    assert cmd[0] == "zenity" and any("*.csv" in a for a in cmd)
    monkeypatch.setattr(filepicker.shutil, "which", lambda n: f"/usr/bin/{n}" if n == "kdialog" else None)
    assert filepicker.picker_command(tmp_path)[0] == "kdialog"
    monkeypatch.setattr(filepicker.shutil, "which", lambda n: None)
    assert filepicker.picker_command(tmp_path) is None  # falls back to typing the path
    monkeypatch.delenv("WAYLAND_DISPLAY")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(filepicker.shutil, "which", lambda n: f"/usr/bin/{n}")
    assert filepicker.picker_command(tmp_path) is None  # no desktop session
    monkeypatch.setattr(filepicker.sys, "platform", "win32")
    cmd = filepicker.picker_command(tmp_path)
    assert "OpenFileDialog" in cmd[-1] and "*.csv" in cmd[-1]


def test_pick_csv_results(monkeypatch, tmp_path):
    class Done:
        def __init__(self, code, out=""):
            self.returncode, self.stdout, self.stderr = code, out, ""

    monkeypatch.setattr(filepicker, "picker_command", lambda start: ["x"])
    for done, expected in [(Done(0, "/a/b.csv\n"), (True, Path("/a/b.csv"))), (Done(1), (True, None)),
                           (Done(0), (True, None)), (Done(255), (False, None))]:
        monkeypatch.setattr(filepicker.subprocess, "run", lambda *a, _d=done, **k: _d)
        assert REAL_PICK_CSV(tmp_path) == expected
    monkeypatch.setattr(filepicker, "picker_command", lambda start: None)
    assert REAL_PICK_CSV(tmp_path) == (False, None)


def make_projects(projects, *names):
    for name in names:
        core.save_project(CHART_TYPES["pie"].new(name), projects / f"{name}.json")


def test_palette_lists_projects_first_and_in_a_fixed_order(projects):
    make_projects(projects, "a", "b")
    project = core.load_project(projects / "a.json")

    async def go():
        app = chart_app.ChartApp(projects / "a.json", project)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            names = [c.title for c in app.get_system_commands(app.screen) if c.discover]
            assert names[:3] == ["Projects", "New chart", "Save project as"]
            assert names.index("Save") < names.index("Import CSV into this chart") < names.index("Theme")
            assert names[-1] == "Quit"
            assert not any(n.startswith("Open project") for n in names)  # searchable only
            everything = [c.title for c in app.get_system_commands(app.screen)]
            assert "Open project: b" in everything

    run(go())


def test_projects_menu_arrows_reach_the_buttons_and_back(projects):
    make_projects(projects, "a", "b")

    async def go():
        app = chart_app.ChartApp(projects / "a.json", core.load_project(projects / "a.json"))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.action_projects()
            await pilot.pause()
            menu = app.screen
            listing = menu.query_one("#project-list")
            await pilot.press("up", "up", "up")
            assert listing.highlighted == 0  # stops at the top
            await pilot.press("down", "down", "down")
            await pilot.pause()
            assert app.focused.id == "open"  # off the end of the list, onto the buttons
            await pilot.press("right", "right", "right", "right")
            assert app.focused.id == "delete"  # stops at the last button
            await pilot.press("left")
            assert app.focused.id == "saveas"

    run(go())


def test_delete_another_project_from_the_menu(projects):
    make_projects(projects, "a", "b")

    async def go():
        app = chart_app.ChartApp(projects / "a.json", core.load_project(projects / "a.json"))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.action_projects()
            await pilot.pause()
            menu = app.screen
            menu.query_one("#project-list").highlighted = [e.stem for e in menu.entries].index("b")
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, chart_app.ConfirmScreen)
            assert app.focused.id == "no"  # Enter alone never deletes
            await pilot.press("y")
            await pilot.pause()
            assert app.screen is menu and not (projects / "b.json").exists()
            assert [e.stem for e in menu.entries] == ["a"]
            assert menu.query_one("#project-list").option_count == 1

    run(go())


def test_declining_the_delete_keeps_the_project(projects):
    make_projects(projects, "a", "b")

    async def go():
        app = chart_app.ChartApp(projects / "a.json", core.load_project(projects / "a.json"))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.action_projects()
            await pilot.pause()
            await pilot.press("d", "enter")  # focus starts on No
            await pilot.pause()
            assert (projects / "a.json").exists() and (projects / "b.json").exists()

    run(go())


def test_deleting_the_open_chart_opens_the_next_one(projects):
    make_projects(projects, "a", "b")

    async def go():
        app = chart_app.ChartApp(projects / "a.json", core.load_project(projects / "a.json"))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.dirty = True  # unsaved edits must not resurrect the deleted file
            app.action_projects()
            await pilot.pause()
            menu = app.screen
            menu.query_one("#project-list").highlighted = [e.stem for e in menu.entries].index("a")
            await pilot.press("d", "y")
            await pilot.pause(0.3)
            assert not (projects / "a.json").exists()
            assert app.path == projects / "b.json" and isinstance(app.screen, TableEditor)

    run(go())


def test_deleting_the_only_chart_starts_a_new_one(projects):
    make_projects(projects, "a")

    async def go():
        app = chart_app.ChartApp(projects / "a.json", core.load_project(projects / "a.json"))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.action_projects()
            await pilot.pause()
            await pilot.press("d", "y")
            await pilot.pause(0.3)
            assert not (projects / "a.json").exists()
            assert isinstance(app.screen, chart_app.PickerScreen)

    run(go())


def test_confirm_dialog_arrows_switch_between_yes_and_no(projects):
    async def go():
        app = chart_app.ChartApp(None, None)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.push_screen(chart_app.ConfirmScreen("Sure?"))
            await pilot.pause()
            assert app.focused.id == "yes"
            await pilot.press("right")
            assert app.focused.id == "no"
            await pilot.press("left")
            assert app.focused.id == "yes"

    run(go())


def screen_text(app) -> str:
    strips = app.screen._compositor.render_strips()
    return "\n".join("".join(seg.text for seg in strip) for strip in strips)


def test_nothing_is_cut_off_at_80_columns(projects):
    make_projects(projects, "a")

    async def go():
        app = chart_app.ChartApp(projects / "a.json", core.load_project(projects / "a.json"))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            footer = screen_text(app).splitlines()[-1]
            for shown in ("^s Save", "f5 Export", "f6 View", "^l Import", "^p Settings"):
                assert shown in footer, footer
            app.action_projects()
            await pilot.pause()
            form = app.screen.query_one("#form")
            for button in app.screen.query("Button"):
                assert button.region.right <= form.content_region.right, button.id
                assert button.region.width >= len(str(button.label)) + 2, button.id
            app.pop_screen()
            app.csv_help()
            await pilot.pause()
            info = app.screen.query_one(".info-text")
            assert info.region.width <= app.screen.query_one("#form").content_region.width

    run(go())


def test_dialogs_fit_a_narrow_terminal(projects):
    make_projects(projects, "a")

    async def go():
        app = chart_app.ChartApp(projects / "a.json", core.load_project(projects / "a.json"))
        async with app.run_test(size=(60, 24)) as pilot:
            await pilot.pause()
            app.action_projects()
            await pilot.pause()
            form = app.screen.query_one("#form")
            assert form.region.right <= 60
            for button in app.screen.query("Button"):
                assert button.region.right <= form.content_region.right, button.id

    run(go())
