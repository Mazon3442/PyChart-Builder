"""
Behaviour every editor screen shares: tabs of row tables, keyboard navigation, and the
add / edit / delete / reorder actions. A chart's editor supplies the tables and the forms.
"""
from __future__ import annotations

from typing import Any, ClassVar

from textual.binding import Binding, BindingType
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Static, TabbedContent, Tabs


class EditorScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "add_item", "Add"),
        Binding("enter", "edit_item", "Edit", show=True),
        Binding("d,delete", "delete_item", "Delete"),
        Binding("[", "move(-1)", "Move", key_display="[ ]"),
        Binding("]", "move(1)", "Move down", show=False),
        Binding("up", "nav_focus(-1)", show=False),
        Binding("down", "nav_focus(1)", show=False),
    ]

    # ---- what the subclass provides
    def table_kinds(self) -> list[str]:
        raise NotImplementedError

    def tab_ids(self) -> list[str]:
        raise NotImplementedError

    def rows(self, kind: str) -> list[tuple[Any, ...]]:
        raise NotImplementedError

    def items(self, kind: str) -> list[Any]:
        raise NotImplementedError

    def open_form(self, kind: str, index: int | None) -> None:
        raise NotImplementedError

    def reload(self) -> None:
        """Show a different project (settings boxes and tables)."""
        raise NotImplementedError

    def delete_blocked(self, kind: str, index: int) -> str | None:
        """A reason this row can't be deleted, or None."""
        return None

    def removed(self, kind: str, index: int) -> None:
        """Called after a row is deleted."""

    def swapped(self, kind: str, i: int, j: int) -> None:
        """Called after rows i and j trade places."""

    # ---- shared
    @property
    def project(self) -> Any:
        return self.app.project  # type: ignore[attr-defined]

    def mark_dirty(self) -> None:
        self.app.mark_dirty()  # type: ignore[attr-defined]

    def refresh_table(self, kind: str, cursor: int | None = None) -> None:
        table = self.query_one(f"#{kind}", DataTable)
        row = table.cursor_row if cursor is None else cursor
        table.clear()
        for cells in self.rows(kind):
            table.add_row(*cells)
        if table.row_count:
            table.move_cursor(row=max(0, min(row, table.row_count - 1)))

    def refresh_all(self) -> None:
        for kind in self.table_kinds():
            self.refresh_table(kind)
        self.app.refresh_title()  # type: ignore[attr-defined]

    def current_table(self) -> DataTable[Any] | None:
        f = self.focused
        return f if isinstance(f, DataTable) else None

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("add_item", "edit_item", "delete_item", "move"):
            return self.current_table() is not None
        return True

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        tab = (event.pane.id or "").removeprefix("tab-")
        if tab in self.table_kinds():
            self.query_one(f"#{tab}", DataTable).focus()
        else:
            # Keep focus somewhere ←/→ still switch tabs (not inside a text box).
            self.query_one(TabbedContent).query_one(Tabs).focus()
            if tab == "preview":
                chart = self.app.chart  # type: ignore[attr-defined]
                self.query_one("#preview", Static).update(chart.preview(self.project))
        self.refresh_bindings()

    # ---- keyboard navigation
    def action_switch_tab(self, delta: int) -> None:
        tabs, order = self.query_one(TabbedContent), self.tab_ids()
        tabs.active = order[(order.index(tabs.active) + delta) % len(order)]  # wraps, like the tab bar

    def action_nav_focus(self, delta: int) -> None:
        """↑/↓ move between boxes (tables, lists and the colour picker use them for themselves)."""
        if isinstance(self.app.screen, ModalScreen):
            return
        self.focus_next() if delta > 0 else self.focus_previous()

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
        if reason := self.delete_blocked(kind, i):
            self.notify(reason, severity="warning")
            return
        del self.items(kind)[i]
        self.removed(kind, i)
        self.mark_dirty()
        self.refresh_all()

    def action_move(self, delta: int) -> None:
        if not (table := self.current_table()) or not table.row_count:
            return
        kind, i = table.id or "", table.cursor_row
        items, j = self.items(kind), i + delta
        if 0 <= j < len(items):
            items[i], items[j] = items[j], items[i]
            self.swapped(kind, i, j)
            self.mark_dirty()
            self.refresh_all()
            self.refresh_table(kind, cursor=j)
