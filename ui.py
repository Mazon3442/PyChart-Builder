"""
Widgets and dialogs shared by every editor screen: scrolling panel, row tables, the colour
picker, the add/edit form, and a yes/no confirmation.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from rich.text import Text
from textual import events
from textual.actions import SkipAction
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Input, Label, Select
from textual.widgets._select import SelectOverlay

import chart_core as core
from chart_core import fmt_num

# ------------------------------------------------------------------- widgets

class Panel(VerticalScroll, can_focus=False):
    """A scrolling box that never takes focus itself, so arrow keys land on the fields inside."""


class ItemTable(DataTable[Any]):
    """Table whose left/right arrows switch tabs (a row cursor has no use for them)."""

    def action_cursor_left(self) -> None:
        if hasattr(self.screen, "action_switch_tab"):
            self.screen.action_switch_tab(-1)

    def action_cursor_right(self) -> None:
        if hasattr(self.screen, "action_switch_tab"):
            self.screen.action_switch_tab(1)


class ClampedOverlay(SelectOverlay):
    """The drop-down list of a Select, but ↑/↓ stop at the first and last choice instead of wrapping."""

    def action_cursor_down(self) -> None:
        if self.highlighted is None or self.highlighted < self.option_count - 1:
            super().action_cursor_down()

    def action_cursor_up(self) -> None:
        if self.highlighted is None or self.highlighted > 0:
            super().action_cursor_up()


class NavSelect(Select[str]):
    """A drop-down you can drive from the keyboard like any other box.

    ↑/↓ move to the previous/next box (a stock Select opens its list on ↑/↓ instead, which traps you
    in it); Enter or Space opens the list; inside the list ↑/↓ choose without wrapping around.
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter,space", "show_overlay", "Show menu", show=False),
        Binding("up", "go(-1)", show=False),
        Binding("down", "go(1)", show=False),
    ]

    def compose(self) -> ComposeResult:
        for widget in super().compose():
            if isinstance(widget, SelectOverlay):
                yield ClampedOverlay(type_to_search=self._type_to_search).data_bind(compact=Select.compact)
            else:
                yield widget

    def action_go(self, delta: int) -> None:
        self.screen.focus_next() if delta > 0 else self.screen.focus_previous()


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


class FormScreen(ModalScreen[Any]):
    """Modal form. `validate(raw: dict[str, str])` returns a result or raises ValueError."""
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "cancel", "Cancel"),
        Binding("up", "nav_focus(-1)", show=False),
        Binding("down", "nav_focus(1)", show=False),
    ]
    AUTO_FOCUS = "Input, Select"

    def __init__(self, title: str, fields: list[Field], validate: Callable[[dict[str, str]], Any]):
        super().__init__()
        self.form_title, self.fields, self.validate = title, fields, validate

    def compose(self) -> ComposeResult:
        with Panel(id="form"):
            yield Label(self.form_title, id="form-title")
            for f in self.fields:
                yield Label(f.label, classes="field-label")
                if f.choices is not None:
                    yield NavSelect([(c, c) for c in f.choices], value=f.value,
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


def parse_color(raw: str, used: list[str]) -> str:
    """Hex colour as typed, or the next free swatch when left blank."""
    raw = raw.strip()
    if not raw:
        return core.auto_color(used)
    if re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raw = "#" + raw
    if not core.HEX_RE.match(raw):
        raise ValueError("That isn't a hex code like #377EB8. Pick a swatch or leave it blank for auto.")
    return raw


CSS = """
FormScreen, ConfirmScreen, ProjectsScreen, PickerScreen, InfoScreen { align: center middle; }
#form { width: 70; height: auto; max-height: 100%; border: thick $primary;
        background: $surface; padding: 0 2; }
#form-title { text-style: bold; margin: 1 0; }
.field-label { margin-top: 1; color: $text-muted; width: 100%; }
#form Input { border: none; height: 1; padding: 0 1; background: $boost; }
#form-error { color: $error; height: auto; margin-top: 1; }
#form-buttons { height: auto; margin: 1 0; align-horizontal: right; }
#form-buttons Button { margin-left: 2; }
#project-list, #chart-list { height: auto; max-height: 14; margin-top: 1; }
#chart-list { max-height: 20; }
Input.-invalid { background: $error 30%; }
#settings Input { border: none; height: 1; padding: 0 1; background: $boost; }
#settings Select { margin-top: 0; }
#settings .field-label { margin-top: 1; }
.hint { color: $text-muted; padding: 0 1; height: auto; width: 100%; }
DataTable { height: 1fr; }
#preview { width: auto; padding: 1; }
"""
