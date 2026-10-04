"""
Editor screen for every table-driven chart. The tabs, boxes and forms are all built from
the chart type's declarations (`Setting`, `TableSpec`, `Column`), so adding a chart type
needs no new screen.
"""
from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import DataTable, Footer, Header, Input, Label, Select, Static, TabbedContent, TabPane

from charts.table import Column, Setting, TableChart, format_cell, parse_cell, parse_setting
from editor_base import EditorScreen
from ui import Field, FormScreen, ItemTable, Panel


class TableEditor(EditorScreen):
    @property
    def chart(self) -> TableChart:
        return self.app.chart  # type: ignore[attr-defined, no-any-return]

    def table_kinds(self) -> list[str]:
        return [t.key for t in self.chart.tables]

    def tab_ids(self) -> list[str]:
        return ["tab-settings", *(f"tab-{k}" for k in self.table_kinds()), "tab-preview"]

    # ---- layout
    def setting_value(self, key: str) -> str:
        p = self.project
        return p.title if key == "title" else p.output if key == "output" else str(p.settings[key])

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="tabs"):
            with TabPane("Settings", id="tab-settings"), Panel(id="settings"):
                yield Label("↑/↓ move between boxes. ↑ from the first box goes back to the tab bar, "
                            "where ←/→ switch tabs.", classes="hint")
                yield Label("Chart title", classes="field-label")
                yield Input(value=self.setting_value("title"), id="set-title")
                for s in self.chart.settings:
                    yield Label(s.label + (f" - {s.help}" if s.help else ""), classes="field-label")
                    if s.kind == "choice":
                        yield Select([(c, c) for c in s.choices], value=self.setting_value(s.key),
                                     allow_blank=False, id=f"set-{s.key}")
                    else:
                        yield Input(value=self.setting_value(s.key), id=f"set-{s.key}")
                yield Label("PNG file name (blank = same name as the project file)", classes="field-label")
                yield Input(value=self.setting_value("output"), id="set-output")
            for spec in self.chart.tables:
                with TabPane(spec.label, id=f"tab-{spec.key}"):
                    yield Label(f"{spec.hint}  a add · enter edit · d delete · [ ] reorder · ←/→ switch tab",
                                classes="hint")
                    yield ItemTable(id=spec.key, cursor_type="row", zebra_stripes=True)
            with TabPane("Preview", id="tab-preview"), ScrollableContainer():
                yield Static(id="preview")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_all()

    def reload(self) -> None:
        for s in [Setting("title", ""), *self.chart.settings, Setting("output", "")]:
            widget = self.query_one(f"#set-{s.key}")
            value = self.setting_value(s.key)
            if isinstance(widget, (Input, Select)) and widget.value != value:
                widget.value = value
            widget.remove_class("-invalid")
        for kind in self.table_kinds():
            self.refresh_table(kind, cursor=0)
        self.app.refresh_title()  # type: ignore[attr-defined]

    # ---- tables
    def columns(self, kind: str) -> list[Column]:
        return self.chart.columns(self.project, kind)

    def rows(self, kind: str) -> list[tuple[Any, ...]]:
        cols = self.columns(kind)
        out = []
        for row in self.project.tables[kind]:
            cells: list[Any] = []
            for col, value in zip(cols, row):
                if col.kind == "color" and value:
                    cells.append(Text(f"██ {value}", style=value))
                else:
                    cells.append(format_cell(value))
            out.append(tuple(cells))
        return out

    def refresh_table(self, kind: str, cursor: int | None = None) -> None:
        table = self.query_one(f"#{kind}", DataTable)
        row = table.cursor_row if cursor is None else cursor
        table.clear(columns=True)  # the Data columns of wide charts follow the Series tab
        table.add_columns(*(c.label for c in self.columns(kind)))
        for cells in self.rows(kind):
            table.add_row(*cells)
        if table.row_count:
            table.move_cursor(row=max(0, min(row, table.row_count - 1)))

    def items(self, kind: str) -> list[Any]:
        return self.project.tables[kind]  # type: ignore[no-any-return]

    def removed(self, kind: str, index: int) -> None:
        self.chart.row_removed(self.project, kind, index)

    def swapped(self, kind: str, i: int, j: int) -> None:
        self.chart.rows_swapped(self.project, kind, i, j)

    # ---- settings
    def on_input_changed(self, event: Input.Changed) -> None:
        self.apply_setting((event.input.id or ""), event.value, event.input)

    def on_select_changed(self, event: Select.Changed) -> None:
        self.apply_setting((event.select.id or ""), str(event.value), event.select)

    def apply_setting(self, widget_id: str, raw: str, widget: Input | Select[str]) -> None:
        if not widget_id.startswith("set-"):
            return
        key, p = widget_id[4:], self.project
        try:
            if key in ("title", "output"):
                value: Any = raw
            else:
                setting = next(s for s in self.chart.settings if s.key == key)
                value = parse_setting(setting, raw)
        except ValueError:
            widget.add_class("-invalid")
            return
        widget.remove_class("-invalid")
        current = getattr(p, key) if key in ("title", "output") else p.settings[key]
        if current != value:
            if key in ("title", "output"):
                setattr(p, key, value)
            else:
                p.settings[key] = value
            self.mark_dirty()

    # ---- forms
    def open_form(self, kind: str, index: int | None) -> None:
        p, chart = self.project, self.chart
        spec = chart.table(kind)
        cols = self.columns(kind)
        rows = p.tables[kind]
        old = rows[index] if index is not None else None
        verb = "Add" if old is None else "Edit"

        fields = []
        for i, col in enumerate(cols):
            value = format_cell(old[i]) if old is not None else col.default
            label = col.label + (f" - {col.help}" if col.help else "") + ("" if col.required else " (optional)")
            if col.kind == "choice":
                fields.append(Field(col.key, label, value or col.choices[0], choices=list(col.choices)))
            else:
                fields.append(Field(col.key, label, value, picker=col.kind == "color"))

        def validate(raw: dict[str, str]) -> list[Any]:
            row = []
            for col in cols:
                try:
                    row.append(parse_cell(col, raw[col.key]))
                except ValueError as e:
                    raise ValueError(f"{col.label} {e}.") from None
            if spec.unique:
                u = next(i for i, c in enumerate(cols) if c.key == spec.unique)
                if any(r[u] == row[u] for r in rows if r is not old):
                    raise ValueError(f'"{row[u]}" is already used - {cols[u].label} must be unique.')
            return chart.fill_row(p, kind, row)

        def done(result: list[Any] | None) -> None:
            if result is None:
                return
            if index is None:
                rows.append(result)
                index_after = len(rows) - 1
                chart.row_added(p, kind, index_after)
            else:
                rows[index] = result
                index_after = index
            self.mark_dirty()
            self.refresh_all()
            self.query_one(f"#{kind}", DataTable).move_cursor(row=index_after)

        self.app.push_screen(FormScreen(f"{verb} row - {spec.label}", fields, validate), done)
