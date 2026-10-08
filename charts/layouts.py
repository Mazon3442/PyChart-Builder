"""Charts that need their own layout code: timeline, treemap and org chart."""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import chart_core as core
from chart_core import fmt_num

from .base import CsvError
from .table import Column, Setting, TableChart, TableProject, TableSpec, finish, new_figure


def _rows(p: TableProject) -> list[list[Any]]:
    return p.tables["data"]


# ------------------------------------------------------------------- timeline

class TimelineChart(TableChart):
    id = "timeline"
    csv_notes = "Row order doesn't matter - events are sorted by date."
    label = "Timeline / roadmap"
    description = "Events on a date line - project history, release plans, milestones."
    settings = ()
    tables = (TableSpec(
        "data", "Events", "One row per event. Rows may be in any order; they're sorted by date. "
        "Category (optional) colors the event.",
        (Column("date", "Date", "date", default=core.local_today().isoformat(), help="YYYY-MM-DD"),
         Column("label", "Label", aliases=("event", "name")),
         Column("category", "Category", required=False, aliases=("group",)))),)

    def draw(self, p: TableProject, plt: Any) -> Any:
        import matplotlib.dates as mdates

        events = sorted(((date.fromisoformat(r[0]), r[1], r[2] or "") for r in _rows(p)), key=lambda e: e[0])
        cats = list(dict.fromkeys(c for _d, _l, c in events if c))
        colors = dict(zip(cats, core.color_cycle(len(cats))))
        n = len(events)
        fig, ax = new_figure(plt, p.title, (max(9.0, 1.15 * n + 3.0), 5.0))
        levels = [1.0, -1.0, 2.0, -2.0, 3.0, -3.0]
        ax.axhline(0, color="#555555", linewidth=2.5, zorder=1)
        for i, (d, label, cat) in enumerate(events):
            h, color = levels[i % len(levels)], colors.get(cat, core.SWATCHES[0])
            ax.plot([d, d], [0, h * 0.85], color="#999999", linewidth=1, zorder=2)
            ax.plot(d, 0, marker="o", markersize=11, color=color, markeredgecolor="white", zorder=3)
            ax.text(d, h * 0.9, f"{label}\n{d:%b} {d.day}, {d.year}", ha="center",
                    va="bottom" if h > 0 else "top", fontsize=9.5, linespacing=1.3,
                    bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": color, "linewidth": 1.4})
        ax.set_ylim(-3.9 if n > 4 else -2.9, 3.9 if n > 4 else 2.9)
        span = (events[-1][0] - events[0][0]).days or 30
        pad = max(span * 0.06, 3)
        ax.set_xlim(events[0][0] - timedelta(days=pad * 1.5),
                    events[-1][0] + timedelta(days=pad * 1.5))
        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.yaxis.set_visible(False)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        if cats:
            from matplotlib.lines import Line2D
            ax.legend([Line2D([], [], marker="o", linestyle="", color=colors[c]) for c in cats], cats,
                      frameon=False, loc="upper left", bbox_to_anchor=(0, -0.08), ncol=min(len(cats), 4))
        return finish(fig)


# ------------------------------------------------------------------ tree data

def tree_problem(rows: list[list[Any]], id_i: int, parent_i: int, what: str) -> tuple[int, str] | None:
    """(row index, message) for the first problem in parent links, or None if it is a valid forest."""
    ids = [r[id_i] for r in rows]
    for i, r in enumerate(rows):
        if ids.index(r[id_i]) != i:
            return i, f'"{r[id_i]}" is used more than once; each {what} must be unique.'
    index = {v: i for i, v in enumerate(ids)}
    for i, r in enumerate(rows):
        parent = r[parent_i]
        if parent and parent not in index:
            return i, f'the parent "{parent}" is not the {what} of any row.'
    for i, r in enumerate(rows):
        seen, cur = {i}, r
        while cur[parent_i]:
            nxt = index[cur[parent_i]]
            if nxt in seen:
                return i, f'"{r[id_i]}" is its own ancestor (the parents form a loop).'
            seen.add(nxt)
            cur = rows[nxt]
    return None


@dataclass
class Node:
    name: str
    value: float = 0.0
    color: str = ""
    children: list[Node] = field(default_factory=list)


def build_forest(rows: list[list[Any]], id_i: int, parent_i: int, value_i: int | None = None) -> list[Node]:
    nodes = {r[id_i]: Node(r[id_i], r[value_i] if value_i is not None else 0.0) for r in rows}
    roots: list[Node] = []
    for r in rows:
        parent = r[parent_i]
        (nodes[parent].children if parent else roots).append(nodes[r[id_i]])
    return roots


# -------------------------------------------------------------------- treemap

def _worst(row: list[float], side: float) -> float:
    s = sum(row)
    return max(side * side * max(row) / (s * s), s * s / (side * side * min(row)))


def squarify(sizes: list[float], x: float, y: float, w: float, h: float) -> list[tuple[float, float, float, float]]:
    """Rectangles (x, y, w, h) filling the box, one per size (sizes sorted largest first, summing to w*h)."""
    rects: list[tuple[float, float, float, float]] = []
    sizes = list(sizes)
    while sizes:
        side = min(w, h)
        row = [sizes[0]]
        while len(row) < len(sizes) and _worst(row + [sizes[len(row)]], side) <= _worst(row, side):
            row.append(sizes[len(row)])
        total = sum(row)
        if w >= h:
            col_w, yy = total / h, y
            for s in row:
                rects.append((x, yy, col_w, s / col_w))
                yy += s / col_w
            x, w = x + col_w, w - col_w
        else:
            row_h, xx = total / w, x
            for s in row:
                rects.append((xx, y, s / row_h, row_h))
                xx += s / row_h
            y, h = y + row_h, h - row_h
        sizes = sizes[len(row):]
    return rects


class TreemapChart(TableChart):
    id = "treemap"
    csv_notes = "Leave value empty for a parent row - its size is the sum of its children. A parent must match another row's label exactly."
    label = "Treemap"
    description = "Rectangles sized by value, optionally grouped into parents (budgets, disk usage)."
    settings = ()
    tables = (TableSpec(
        "data", "Data",
        "One row per rectangle. Give a row a Parent (the Label of another row) to nest it inside that one; "
        "a parent's size is the sum of its children.",
        (Column("label", "Label"),
         Column("value", "Value", "number", required=False, minimum=0, strict=True,
                help="Size (more than 0). Leave blank for a parent: its size is the sum of its children."),
         Column("parent", "Parent", required=False, help="Label of the row this one sits inside; blank = top level")),
        unique="label"),)

    def _problem(self, rows: list[list[Any]]) -> tuple[int, str] | None:
        if bad := tree_problem(rows, 0, 2, "label"):
            return bad
        parents = {r[2] for r in rows if r[2]}
        for i, r in enumerate(rows):
            if r[0] not in parents and r[1] is None:
                return i, f'"{r[0]}" has no children, so it needs a value.'
        return None

    def check_ready(self, p: TableProject) -> None:
        super().check_ready(p)
        if bad := self._problem(_rows(p)):
            raise ValueError(f"Data row {bad[0] + 1}: {bad[1]}")

    def check_csv(self, p: TableProject, path: Any) -> None:
        if bad := self._problem(_rows(p)):
            raise CsvError(f'{path.name} row {bad[0] + 2}, column "Parent/Label": {bad[1]}')

    def draw(self, p: TableProject, plt: Any) -> Any:
        from matplotlib.patches import Rectangle

        roots = build_forest([[r[0], r[1] or 0.0, r[2]] for r in _rows(p)], 0, 2, 1)

        def total(n: Node) -> float:
            n.value = sum(total(c) for c in n.children) if n.children else n.value
            return n.value

        for r in roots:
            total(r)
        width, height = 10.0, 6.4
        fig, ax = new_figure(plt, p.title, (width + 0.6, height + 1.0))
        base = core.color_cycle(len(roots))

        def lighten(color: str, amount: float) -> tuple[float, float, float]:
            rr, gg, bb = (int(color[k:k + 2], 16) / 255 for k in (1, 3, 5))
            return (rr + (1 - rr) * amount, gg + (1 - gg) * amount, bb + (1 - bb) * amount)

        def lay(nodes: list[Node], x: float, y: float, w: float, h: float, depth: int, color: str) -> None:
            nodes = sorted(nodes, key=lambda n: -n.value)
            area, sum_v = w * h, sum(n.value for n in nodes)
            for i, (n, (rx, ry, rw, rh)) in enumerate(zip(nodes, squarify([n.value / sum_v * area for n in nodes],
                                                                       x, y, w, h))):
                c = color or base[roots.index(n)]
                if n.children:
                    ax.add_patch(Rectangle((rx, ry), rw, rh, facecolor=lighten(c, 0.55), edgecolor="white", linewidth=2))
                    head = min(0.4, rh * 0.25)
                    if rw > 0.9 and rh > 0.7:
                        ax.text(rx + 0.08, ry + head / 2, n.name, ha="left", va="center", fontsize=10,
                                fontweight="bold", color="#222222", clip_on=True)
                    lay(n.children, rx + 0.06, ry + head, rw - 0.12, rh - head - 0.06, depth + 1, c)
                else:
                    ax.add_patch(Rectangle((rx, ry), rw, rh, facecolor=lighten(c, 0.12 * depth), edgecolor="white",
                                           linewidth=2))
                    if rw > 0.7 and rh > 0.4:
                        size = max(7.0, min(13.0, rw * 4.5, rh * 14))
                        dark = depth == 0 and core.text_color_for(c) == "white"
                        ax.text(rx + rw / 2, ry + rh / 2, f"{textwrap.fill(n.name, max(6, int(rw * 7)))}\n{fmt_num(n.value)}",
                                ha="center", va="center", fontsize=size, color="white" if dark else "#222222")

        lay(roots, 0, 0, width, height, 0, "")
        ax.set_xlim(0, width)
        ax.set_ylim(height, 0)
        ax.axis("off")
        return finish(fig)


# -------------------------------------------------------------------- org chart

class OrgChart(TableChart):
    id = "orgchart"
    csv_notes = "A parent must match another row's id exactly; leave it empty for the top box. Several top boxes are allowed."
    label = "Org chart / hierarchy"
    description = "A tree of boxes - who reports to whom, or any parent/child structure."
    settings = (Setting("box_width", "Box width (characters)", "int", 16, minimum=8),)
    tables = (TableSpec(
        "data", "Boxes",
        "One row per box. Parent is the ID of the box above it; leave it blank for the top box.",
        (Column("id", "ID", help="A short unique name, e.g. ceo or A1"),
         Column("label", "Label", help="Text shown in the box", aliases=("name", "title")),
         Column("parent", "Parent", required=False, help="ID of the box above; blank = top", aliases=("reports to",))),
        unique="id"),)

    def _problem(self, rows: list[list[Any]]) -> tuple[int, str] | None:
        return tree_problem(rows, 0, 2, "ID")

    def check_ready(self, p: TableProject) -> None:
        super().check_ready(p)
        if bad := self._problem(_rows(p)):
            raise ValueError(f"Boxes row {bad[0] + 1}: {bad[1]}")

    def check_csv(self, p: TableProject, path: Any) -> None:
        if bad := self._problem(_rows(p)):
            raise CsvError(f'{path.name} row {bad[0] + 2}, column "Parent/ID": {bad[1]}')

    def draw(self, p: TableProject, plt: Any) -> Any:
        from matplotlib.patches import FancyBboxPatch

        rows = _rows(p)
        labels = {r[0]: r[1] for r in rows}
        roots = build_forest(rows, 0, 2)
        wrap = int(p.settings["box_width"])
        box_w, gap_x, gap_y = 0.28 + 0.085 * wrap, 0.3, 0.9
        box_h = 0.3 + 0.2 * max(len(textwrap.wrap(t, wrap)) or 1 for t in labels.values())

        pos: dict[str, tuple[float, int]] = {}
        slot = [0]

        def place(n: Node, depth: int) -> float:
            if n.children:
                xs = [place(c, depth + 1) for c in n.children]
                x = (xs[0] + xs[-1]) / 2
            else:
                x = slot[0] * (box_w + gap_x)
                slot[0] += 1
            pos[n.name] = (x, depth)
            return x

        for r in roots:
            place(r, 0)
        levels = max(d for _x, d in pos.values()) + 1
        width = (slot[0] - 1) * (box_w + gap_x) + box_w + 0.8
        height = levels * (box_h + gap_y) - gap_y + 0.8
        fig, ax = new_figure(plt, p.title, (max(width, 5.0), max(height, 2.5) + (0.7 if p.title else 0.0)))
        colors = core.color_cycle(levels)

        def draw_node(n: Node) -> None:
            x, d = pos[n.name]
            y = d * (box_h + gap_y)
            for c in n.children:
                cx, cd = pos[c.name]
                cy, mid = cd * (box_h + gap_y), y + box_h + gap_y / 2
                ax.plot([x, x, cx, cx], [y + box_h, mid, mid, cy], color="#888888", linewidth=1.4, zorder=1,
                        solid_joinstyle="round")
                draw_node(c)
            ax.add_patch(FancyBboxPatch((x - box_w / 2, y), box_w, box_h, boxstyle="round,pad=0,rounding_size=0.08",
                                        facecolor=colors[d], edgecolor="none", zorder=2))
            ax.text(x, y + box_h / 2, textwrap.fill(labels[n.name], wrap), ha="center", va="center", fontsize=10.5,
                    color=core.text_color_for(colors[d]), zorder=3, linespacing=1.2)

        for r in roots:
            draw_node(r)
        ax.set_xlim(-box_w / 2 - 0.4, width - box_w / 2 - 0.4)
        ax.set_ylim(height - 0.4, -0.4)
        ax.axis("off")
        return finish(fig)
