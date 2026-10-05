"""Every chart type: example CSV loads, JSON round-trips, PNG renders, bad input gives clear errors."""
import json
from pathlib import Path

import pytest

import chart_core as core
from charts import CHART_TYPES, CsvError
from charts.layouts import squarify, tree_problem
from charts.table import WideChart

ROOT = Path(__file__).resolve().parent.parent
IDS = list(CHART_TYPES)


def example(cid):
    return ROOT / "examples" / f"{cid}.csv"


@pytest.mark.parametrize("cid", IDS)
def test_example_csv_loads_and_renders(cid, tmp_path):
    chart = CHART_TYPES[cid]
    project = chart.from_csv(example(cid), "Example")
    out = chart.render(project, tmp_path / f"{cid}.png")
    assert out.stat().st_size > 5_000
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("cid", IDS)
def test_json_round_trip(cid, tmp_path):
    chart = CHART_TYPES[cid]
    project = chart.from_csv(example(cid), "Example")
    path = tmp_path / "p.json"
    core.save_project(project, path)
    assert json.loads(path.read_text(encoding="utf-8"))["type"] == cid
    again = core.load_project(path)
    assert again.to_dict() == project.to_dict()


@pytest.mark.parametrize("cid", IDS)
def test_new_chart_saves_loads_and_refuses_to_render_empty(cid, tmp_path):
    chart = CHART_TYPES[cid]
    project = chart.new("Blank")
    path = tmp_path / "blank.json"
    core.save_project(project, path)
    assert core.load_project(path).to_dict() == project.to_dict()
    with pytest.raises(ValueError):
        chart.render(project, tmp_path / "blank.png")


@pytest.mark.parametrize("cid", IDS)
def test_csv_help_mentions_something(cid):
    assert len(CHART_TYPES[cid].csv_help) > 30


def test_old_gantt_files_without_a_type_still_load():
    project = core.load_project(ROOT / "deer_alarm.json")
    assert project.type == "gantt" and len(project.tasks) > 5


def test_unknown_type_is_a_readable_error(tmp_path):
    path = tmp_path / "x.json"
    path.write_text('{"type": "hologram"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown chart type"):
        core.load_project(path)


def test_non_object_json_is_a_readable_error(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        core.load_project(path)


def test_hand_edited_row_with_wrong_length_is_refused():
    bar = CHART_TYPES["bar"]
    d = bar.new("t").to_dict()
    d["tables"]["data"] = [["A", 1.0, 2.0, 3.0]]
    with pytest.raises(ValueError, match="expected 2"):
        bar.from_dict(d)


# ------------------------------------------------------------------- CSV errors

def write(tmp_path, text, name="data.csv", encoding="utf-8"):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return path


def test_csv_empty_file(tmp_path):
    with pytest.raises(CsvError, match="empty"):
        CHART_TYPES["pie"].from_csv(write(tmp_path, ""), "t")


def test_csv_header_only(tmp_path):
    with pytest.raises(CsvError, match="no data rows"):
        CHART_TYPES["pie"].from_csv(write(tmp_path, "label,value\n"), "t")


def test_csv_missing_column_names_what_was_found(tmp_path):
    with pytest.raises(CsvError, match=r"missing the column\(s\): Value.*Found: label, amount"):
        CHART_TYPES["pie"].from_csv(write(tmp_path, "label,amount\nA,1\n"), "t")


def test_csv_bad_number_names_row_and_column(tmp_path):
    with pytest.raises(CsvError) as e:
        CHART_TYPES["pie"].from_csv(write(tmp_path, "label,value\nA,1\nB,12k\n"), "t")
    assert str(e.value) == 'data.csv row 3, column "Value": must be a number (got "12k").'


def test_csv_negative_pie_value(tmp_path):
    with pytest.raises(CsvError, match="at least 0"):
        CHART_TYPES["pie"].from_csv(write(tmp_path, "label,value\nA,-1\n"), "t")


def test_csv_nan_is_rejected(tmp_path):
    with pytest.raises(CsvError, match="must be a number"):
        CHART_TYPES["pie"].from_csv(write(tmp_path, "label,value\nA,nan\n"), "t")


def test_csv_bad_date(tmp_path):
    with pytest.raises(CsvError, match=r'row 2, column "Date": must be a date'):
        CHART_TYPES["timeline"].from_csv(write(tmp_path, "date,label\n24/08/2026,Start\n"), "t")


def test_csv_empty_required_cell(tmp_path):
    with pytest.raises(CsvError, match=r"row 3, column \"Label\": can't be empty"):
        CHART_TYPES["pie"].from_csv(write(tmp_path, "label,value\nA,1\n,2\n"), "t")


def test_csv_utf8_bom_and_semicolons_and_case(tmp_path):
    text = "﻿LABEL;Value\nA;1\nB;2\n"
    project = CHART_TYPES["pie"].from_csv(write(tmp_path, text), "t")
    assert project.tables["data"] == [["A", 1.0, None], ["B", 2.0, None]]


def test_csv_not_utf8(tmp_path):
    with pytest.raises(CsvError, match="UTF-8"):
        CHART_TYPES["pie"].from_csv(write(tmp_path, "label,value\nCafé,1\n", encoding="cp1252"), "t")


def test_csv_missing_file(tmp_path):
    with pytest.raises(CsvError, match="Couldn't read"):
        CHART_TYPES["pie"].from_csv(tmp_path / "nope.csv", "t")


def test_csv_header_aliases(tmp_path):
    project = CHART_TYPES["funnel"].from_csv(write(tmp_path, "Label,Value\nA,3\nB,2\n"), "t")
    assert project.tables["data"][0] == ["A", 3.0]


def test_wide_csv_series_and_gaps(tmp_path):
    project = CHART_TYPES["line"].from_csv(write(tmp_path, "x,One,Two\na,1,\nb,2,3\n"), "t")
    assert [s[0] for s in project.tables["series"]] == ["One", "Two"]
    assert project.tables["data"] == [["a", 1.0, None], ["b", 2.0, 3.0]]


def test_wide_csv_needs_a_series(tmp_path):
    with pytest.raises(CsvError, match="at least one column of numbers"):
        CHART_TYPES["bar"].from_csv(write(tmp_path, "label\nA\n"), "t")


def test_wide_csv_duplicate_and_empty_headers(tmp_path):
    with pytest.raises(CsvError, match="appears twice"):
        CHART_TYPES["bar"].from_csv(write(tmp_path, "l,A,a\nx,1,2\n"), "t")
    with pytest.raises(CsvError, match="header is empty"):
        CHART_TYPES["bar"].from_csv(write(tmp_path, "l,A,\nx,1,2\n"), "t")


def test_wide_csv_bad_number(tmp_path):
    with pytest.raises(CsvError, match=r'row 3, column "B": must be a number \(got "x"\)'):
        CHART_TYPES["bar"].from_csv(write(tmp_path, "l,A,B\nx,1,2\ny,3,x\n"), "t")


def test_radar_needs_three_rows(tmp_path):
    with pytest.raises(CsvError, match="at least 3"):
        CHART_TYPES["radar"].from_csv(write(tmp_path, "l,A\nx,1\ny,2\n"), "t")


def test_heatmap_duplicate_pair(tmp_path):
    with pytest.raises(CsvError, match="more than once"):
        CHART_TYPES["heatmap"].from_csv(write(tmp_path, "row,column,value\na,b,1\na,b,2\n"), "t")


def test_orgchart_problems(tmp_path):
    org = CHART_TYPES["orgchart"]
    with pytest.raises(CsvError, match="not the ID of any row"):
        org.from_csv(write(tmp_path, "id,label,parent\na,A,zzz\n"), "t")
    with pytest.raises(CsvError, match="loop"):
        org.from_csv(write(tmp_path, "id,label,parent\na,A,b\nb,B,a\n"), "t")
    with pytest.raises(CsvError, match="already used"):
        org.from_csv(write(tmp_path, "id,label,parent\na,A,\na,B,\n"), "t")


def test_treemap_leaf_needs_value(tmp_path):
    with pytest.raises(CsvError, match="needs a value"):
        CHART_TYPES["treemap"].from_csv(write(tmp_path, "label,value,parent\nA,,\n"), "t")


def test_gantt_csv(tmp_path):
    csv_text = "task,start,duration,category,color\nA,1,2,Plan,#112233\nB,3,1.5,Plan,\nC,2,1,,\n"
    project = CHART_TYPES["gantt"].from_csv(write(tmp_path, csv_text), "G")
    assert [c.name for c in project.categories] == ["Plan", "Tasks"]
    assert project.categories[0].color == "#112233"
    assert [t.end for t in project.tasks] == [2, 3.5, 2]
    with pytest.raises(CsvError, match='column "duration": must be more than 0'):
        CHART_TYPES["gantt"].from_csv(write(tmp_path, "task,start,duration\nA,1,0\n"), "G")
    with pytest.raises(CsvError, match='column "start": must be 1 or more'):
        CHART_TYPES["gantt"].from_csv(write(tmp_path, "task,start,duration\nA,0,1\n"), "G")


# ------------------------------------------------------------- series linkage

def test_wide_series_edits_keep_data_columns_aligned():
    bar = CHART_TYPES["bar"]
    assert isinstance(bar, WideChart)
    p = bar.new("t")
    p.tables["data"] = [["A", 1.0], ["B", 2.0]]
    p.tables["series"].append(["Two", "#E4572E"])
    bar.row_added(p, "series", 1)
    assert p.tables["data"] == [["A", 1.0, None], ["B", 2.0, None]]
    p.tables["data"][0][2] = 9.0
    p.tables["series"][0], p.tables["series"][1] = p.tables["series"][1], p.tables["series"][0]
    bar.rows_swapped(p, "series", 0, 1)
    assert p.tables["data"][0] == ["A", 9.0, 1.0]
    del p.tables["series"][0]
    bar.row_removed(p, "series", 0)
    assert p.tables["data"][0] == ["A", 1.0]
    assert [c.label for c in bar.columns(p, "data")] == ["Label", "Series 1"]


def test_wide_chart_without_series_explains_itself(tmp_path):
    bar = CHART_TYPES["bar"]
    p = bar.new("t")
    p.tables["series"].clear()
    p.tables["data"] = [["A"]]
    with pytest.raises(ValueError, match="Series tab"):
        bar.render(p, tmp_path / "x.png")


# --------------------------------------------------------------------- helpers

def test_squarify_fills_the_box():
    sizes = sorted([6.0, 6.0, 4.0, 3.0, 2.0, 2.0, 1.0], reverse=True)
    w, h = 6.0, 4.0
    scale = w * h / sum(sizes)
    rects = squarify([s * scale for s in sizes], 0, 0, w, h)
    assert len(rects) == len(sizes)
    assert sum(rw * rh for _x, _y, rw, rh in rects) == pytest.approx(w * h)
    assert all(0 <= x and x + rw <= w + 1e-9 and 0 <= y and y + rh <= h + 1e-9 for x, y, rw, rh in rects)


def test_tree_problem_accepts_forests():
    assert tree_problem([["a", "", ""], ["b", "", "a"], ["c", "", ""]], 0, 2, "ID") is None


def test_filenames():
    assert core.project_filename("a/b:c") == "a-b-c.json"
    assert core.project_filename("CON") == "CON_.json"
    with pytest.raises(ValueError):
        core.project_filename("  ..  ")


def test_output_path_is_relative_to_the_project_file():
    p = CHART_TYPES["pie"].new("t")
    assert core.output_path(p, Path("sub") / "x.json") == Path("sub") / "x.png"
    p.output = "out.png"
    assert core.output_path(p, Path("sub") / "x.json") == Path("sub") / "out.png"


def test_hostile_labels_render(tmp_path):
    """Markup-like and very long text must not break drawing."""
    bar = CHART_TYPES["bar"]
    p = bar.new("$x^2$ \\ {bad} <b>")
    p.tables["data"] = [["a" * 80, 1.0], ["$$", 2.0], ["", 3.0]]
    bar.render(p, tmp_path / "x.png")


def test_dollar_signs_in_text_are_drawn_as_typed(tmp_path):
    for cid in ("gantt", "pie"):
        chart = CHART_TYPES[cid]
        project = chart.from_csv(example(cid), "$a$ and $b")
        if cid == "pie":
            project.tables["data"][0][0] = "$$ broken $"
        else:
            project.tasks[0].name = "$x^ budget $"
        chart.render(project, tmp_path / f"{cid}.png")


def test_milestone_tiers_never_overlap_and_always_finish():
    from charts.gantt import assign_tiers
    # five crowded labels (the layout that used to overprint) and one pathological pile-up
    for centers, widths in (([6.6, 7.8, 8.4, 9.0, 9.6], [0.9, 0.9, 0.9, 0.9, 1.2]), ([1.0] * 6, [2.0] * 6)):
        tiers = assign_tiers(centers, widths)
        for i in range(len(centers)):
            for j in range(i):
                if tiers[i] == tiers[j]:
                    assert abs(centers[i] - centers[j]) >= (widths[i] + widths[j]) / 2


def test_gantt_with_crowded_milestones_renders(tmp_path):
    import datetime
    from charts.gantt import Milestone
    project = core.load_project(ROOT / "deer_alarm.json")
    project.semester_start = datetime.date(2026, 9, 21)
    project.milestones = [Milestone(w, f"Milestone number {w}\nwith two lines") for w in (11, 12, 13, 14, 15, 16)]
    CHART_TYPES["gantt"].render(project, tmp_path / "g.png")
    assert (tmp_path / "g.png").stat().st_size > 5_000


def test_output_name_without_png_extension_gets_one(tmp_path):
    """The name typed in Settings may omit .png; export and 'view' must agree on the real file."""
    chart = CHART_TYPES["pie"]
    p = chart.from_csv(example("pie"), "t")
    project_file = tmp_path / "proj.json"
    for typed, expected in (("DeerAlarm(SD403_Fa26_09)", "DeerAlarm(SD403_Fa26_09).png"),
                            ("v1.2", "v1.2.png"), ("shout.PNG", "shout.PNG"), ("sub/x", "sub/x.png")):
        p.output = typed
        out = core.output_path(p, project_file)
        assert out == tmp_path / expected
        chart.render(p, out)
        assert out.exists()
