"""Charts whose data is a single table: pie, funnel, waterfall, pareto, burndown,
histogram, box plot, scatter / bubble and heatmap."""
from __future__ import annotations

import math
from typing import Any

import chart_core as core
from chart_core import fmt_num

from .base import CsvError
from .table import (YES_NO, Column, Setting, TableChart, TableProject, TableSpec, finish,
                    is_on, new_figure, rotate_if_crowded, tidy)

X_LABEL = Setting("x_label", "X-axis label (optional)", help="Text under the horizontal axis")
Y_LABEL = Setting("y_label", "Y-axis label (optional)", help="Text beside the vertical axis")


def _rows(p: TableProject) -> list[list[Any]]:
    return p.tables["data"]


def _data(hint: str, *columns: Column, unique: str | None = None) -> tuple[TableSpec]:
    return (TableSpec("data", "Data", hint, columns, unique),)


class PieChart(TableChart):
    id = "pie"
    csv_notes = "Slices with a value of 0 are skipped. The color column is optional."
    label = "Pie / donut chart"
    description = "Show how a whole splits into parts."
    settings = (
        Setting("style", "Style", "choice", "pie", ("pie", "donut")),
        Setting("percent", "Print the percentage on each slice", "choice", "yes", YES_NO),
    )
    tables = _data(
        "One row per slice. Slice colors are picked for you.",
        Column("label", "Label", help="Name of the slice"),
        Column("value", "Value", "number", minimum=0, help="Size of the slice (0 or more)"),
        Column("color", "Color", "color", required=False, help="Hex code like #377EB8; blank = automatic",
               aliases=("colour",)),
    )

    def check_ready(self, p: TableProject) -> None:
        super().check_ready(p)
        if sum(r[1] for r in _rows(p)) <= 0:
            raise ValueError("The values add up to 0, so there's nothing to draw. Give at least one slice a value.")

    def draw(self, p: TableProject, plt: Any) -> Any:
        rows = [r for r in _rows(p) if r[1] > 0]
        cycle = core.color_cycle(len(_rows(p)))
        colors = [r[2] or cycle[i] for i, r in enumerate(_rows(p)) if r[1] > 0]
        fig, ax = new_figure(plt, p.title, (8.5, 6.0))
        donut = p.settings["style"] == "donut"
        wedges, _t, *autotexts = ax.pie(
            [r[1] for r in rows], colors=colors, startangle=90, counterclock=False,
            autopct=(lambda pct: f"{pct:.0f}%") if is_on(p.settings["percent"]) else None,
            pctdistance=0.78 if donut else 0.62,
            wedgeprops={"width": 0.42 if donut else 1, "edgecolor": "white", "linewidth": 1.5})
        for t, color in zip(autotexts[0] if autotexts else [], colors):
            t.set_color(core.text_color_for(color))
            t.set_fontsize(10)
            t.set_fontweight("bold")
        ax.legend(wedges, [r[0] for r in rows], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
        ax.set_aspect("equal")
        return finish(fig)


class FunnelChart(TableChart):
    id = "funnel"
    csv_notes = "List the stages from widest to narrowest."
    label = "Funnel chart"
    description = "Stages of a process where each stage is smaller than the last (sales, sign-ups)."
    settings = (Setting("percent", "Print the share of the first stage", "choice", "yes", YES_NO),)
    tables = _data(
        "One row per stage, from the widest (top) to the narrowest.",
        Column("stage", "Stage", aliases=("label", "name")),
        Column("value", "Value", "number", minimum=0, help="Count at this stage (0 or more)"),
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        rows = _rows(p)
        n, top = len(rows), max(r[1] for r in rows) or 1
        colors = core.color_cycle(n)
        fig, ax = new_figure(plt, p.title, (9.0, max(4.0, 0.8 * n + 1.8)))
        for i, (stage, value) in enumerate(r[:2] for r in rows):
            ax.barh(i, value, left=-value / 2, height=0.85, color=colors[i], zorder=3)
            text = f"{stage}\n{fmt_num(value)}"
            if is_on(p.settings["percent"]) and rows[0][1]:
                text += f" ({value / rows[0][1]:.0%})"
            ax.text(0, i, text, ha="center", va="center", fontsize=10, fontweight="bold",
                    color=core.text_color_for(colors[i]), zorder=4, linespacing=1.15)
        ax.set_xlim(-top / 2 * 1.02, top / 2 * 1.02)
        ax.set_ylim(n - 0.45, -0.55)
        ax.axis("off")
        return finish(fig)


class WaterfallChart(TableChart):
    id = "waterfall"
    csv_notes = "Use a negative number for a decrease. The first row is usually the starting value."
    label = "Waterfall chart"
    description = "How a starting value rises and falls to an end value (budgets, profit bridges)."
    settings = (
        Setting("total", "Add a total bar at the end", "choice", "yes", YES_NO),
        Setting("total_label", "Label for the total bar", default="Total"),
        X_LABEL, Y_LABEL,
    )
    tables = _data(
        "One row per step, in order. The first row is usually the starting value. Use a negative number for a decrease.",
        Column("label", "Label"),
        Column("change", "Change", "number", help="Amount added (positive) or taken away (negative)",
               aliases=("amount", "value")),
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        rows = _rows(p)
        n = len(rows) + (1 if is_on(p.settings["total"]) else 0)
        fig, ax = new_figure(plt, p.title, (max(7.5, 0.9 * n + 3.0), 5.5))
        up, down, total_color = "#3A9E4E", "#D62728", "#377EB8"
        running, labels, tops = 0.0, [], []
        span = max(abs(r[1]) for r in rows) or 1
        for i, (label, change) in enumerate(r[:2] for r in rows):
            start = running
            running += change
            ax.bar(i, change, bottom=start, color=up if change >= 0 else down, width=0.65, zorder=3)
            ax.text(i, max(start, running) + span * 0.02, f"{change:+g}", ha="center", va="bottom", fontsize=10)
            if i < len(rows) - 1:
                ax.plot([i + 0.33, i + 1 - 0.33], [running, running], color="#888888", linewidth=1, zorder=2)
            labels.append(label)
            tops.append(max(start, running))
        if is_on(p.settings["total"]):
            i = len(rows)
            ax.plot([i - 1 + 0.33, i - 0.33], [running, running], color="#888888", linewidth=1, zorder=2)
            ax.bar(i, running, color=total_color, width=0.65, zorder=3)
            ax.text(i, max(running, 0) + span * 0.02, fmt_num(running), ha="center", va="bottom",
                    fontsize=10, fontweight="bold")
            labels.append(p.settings["total_label"] or "Total")
        ax.axhline(0, color="#555555", linewidth=1, zorder=4)
        ax.set_xticks(range(n), labels)
        rotate_if_crowded(ax, labels)
        lows = [0.0, running] + [t - abs(r[1]) for t, r in zip(tops, rows)]
        ax.set_ylim(min(lows), max(tops + [running]) + span * 0.12)
        tidy(ax, p.settings["x_label"], p.settings["y_label"])
        return finish(fig)


class ParetoChart(TableChart):
    id = "pareto"
    csv_notes = "Rows are sorted largest first for you."
    label = "Pareto chart"
    description = "Bars sorted largest to smallest plus a running-total line - find the vital few causes."
    settings = (X_LABEL, Setting("y_label", "Y-axis label (optional)", default="Count"))
    tables = _data(
        "One row per cause or category. Rows are sorted for you, largest first.",
        Column("label", "Label", aliases=("category", "cause")),
        Column("value", "Value", "number", minimum=0, help="Count or amount (0 or more)", aliases=("count",)),
    )

    def check_ready(self, p: TableProject) -> None:
        super().check_ready(p)
        if sum(r[1] for r in _rows(p)) <= 0:
            raise ValueError("The values add up to 0, so there's nothing to draw.")

    def draw(self, p: TableProject, plt: Any) -> Any:
        rows = sorted(_rows(p), key=lambda r: -r[1])
        labels, values = [r[0] for r in rows], [r[1] for r in rows]
        total = sum(values)
        cumulative, run = [], 0.0
        for v in values:
            run += v
            cumulative.append(100 * run / total)
        fig, ax = new_figure(plt, p.title, (max(7.5, 0.7 * len(rows) + 3.5), 5.5))
        ax.bar(range(len(rows)), values, color=core.SWATCHES[0], width=0.7, zorder=3)
        ax.set_xticks(range(len(rows)), labels)
        rotate_if_crowded(ax, labels)
        tidy(ax, p.settings["x_label"], p.settings["y_label"])
        ax2 = ax.twinx()
        ax2.plot(range(len(rows)), cumulative, color=core.SWATCHES[1], marker="o", linewidth=2, zorder=5)
        ax2.axhline(80, color="#999999", linestyle="--", linewidth=1)
        ax2.set_ylim(0, 105)
        ax2.set_ylabel("Cumulative %", fontsize=12)
        ax2.spines["top"].set_visible(False)
        return finish(fig)


class BurndownChart(TableChart):
    id = "burndown"
    csv_notes = "Rows are plotted in file order. The ideal line is drawn for you."
    label = "Burndown chart"
    description = "Work remaining over time, against the ideal pace (sprints, projects)."
    min_rows = 2
    settings = (
        Setting("ideal", "Draw the ideal line (straight down to zero)", "choice", "yes", YES_NO),
        Setting("x_label", "X-axis label (optional)", default="Day"),
        Setting("y_label", "Y-axis label (optional)", default="Work remaining"),
    )
    tables = _data(
        "One row per day (or week), in order. Remaining = work still to do at the end of that day.",
        Column("label", "Day", aliases=("day", "period", "date", "label"), help="Name of the day, e.g. 1, Mon, Jan 6"),
        Column("remaining", "Remaining", "number", minimum=0, help="Work left (story points, hours, tasks)"),
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        rows = _rows(p)
        labels, remaining = [str(r[0]) for r in rows], [r[1] for r in rows]
        xs = list(range(len(rows)))
        fig, ax = new_figure(plt, p.title, (max(7.5, 0.6 * len(rows) + 3.5), 5.5))
        if is_on(p.settings["ideal"]):
            ax.plot([0, len(rows) - 1], [remaining[0], 0], color="#888888", linestyle="--",
                    linewidth=2, label="Ideal", zorder=2)
        ax.plot(xs, remaining, color=core.SWATCHES[1], marker="o", linewidth=2.4, label="Remaining", zorder=3)
        ax.set_xticks(xs, labels)
        ax.set_ylim(bottom=0)
        rotate_if_crowded(ax, labels)
        tidy(ax, p.settings["x_label"], p.settings["y_label"])
        ax.legend(frameon=False)
        return finish(fig)


class HistogramChart(TableChart):
    id = "histogram"
    csv_notes = "One measurement per row, not counts. The number of bars is set in the app."
    label = "Histogram"
    description = "How a set of numbers is spread out. Counts how many fall into each range."
    settings = (
        Setting("bins", "Number of bars (bins)", "int", 10, minimum=1),
        Setting("x_label", "X-axis label (optional)", default="Value"),
        Setting("y_label", "Y-axis label (optional)", default="Count"),
    )
    tables = _data(
        "One number per row - the raw measurements, not counts.",
        Column("value", "Value", "number", aliases=("values", "data", "number", "x")),
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        values = [r[0] for r in _rows(p)]
        fig, ax = new_figure(plt, p.title, (8.0, 5.5))
        ax.hist(values, bins=int(p.settings["bins"]), color=core.SWATCHES[0], edgecolor="white", zorder=3)
        tidy(ax, p.settings["x_label"], p.settings["y_label"])
        ax.yaxis.get_major_locator().set_params(integer=True)
        return finish(fig)


class BoxPlotChart(TableChart):
    id = "boxplot"
    csv_notes = "Rows with the same group name end up in the same box."
    label = "Box plot"
    description = "Compare how several groups of numbers are spread: median, quartiles and outliers."
    min_rows = 2
    settings = (
        Setting("points", "Show every data point too", "choice", "yes", YES_NO),
        X_LABEL, Y_LABEL,
    )
    tables = _data(
        "One row per measurement. Rows with the same group name are drawn in the same box.",
        Column("group", "Group", aliases=("label", "category")),
        Column("value", "Value", "number"),
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        groups: dict[str, list[float]] = {}
        for g, v in _rows(p):
            groups.setdefault(g, []).append(v)
        names = list(groups)
        colors = core.color_cycle(len(names))
        fig, ax = new_figure(plt, p.title, (max(6.5, 1.3 * len(names) + 3.0), 5.5))
        box = ax.boxplot([groups[n] for n in names], patch_artist=True, widths=0.55, zorder=3,
                         medianprops={"color": "#111111", "linewidth": 2},
                         flierprops={"marker": "o", "markersize": 5, "markerfacecolor": "#777777",
                                     "markeredgecolor": "none"})
        for patch, color in zip(box["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
        if is_on(p.settings["points"]):
            for i, n in enumerate(names, start=1):
                m = len(groups[n])
                jitter = [((j * 0.618) % 1 - 0.5) * 0.3 for j in range(m)]  # fixed, so exports repeat exactly
                ax.scatter([i + dx for dx in jitter], groups[n], s=16, color="#333333", alpha=0.55, zorder=4)
        ax.set_xticks(range(1, len(names) + 1), names)
        rotate_if_crowded(ax, names)
        tidy(ax, p.settings["x_label"], p.settings["y_label"])
        return finish(fig)


class ScatterChart(TableChart):
    id = "scatter"
    csv_notes = "Leave group empty if you have one set of points. Fill in size to get bubbles."
    label = "Scatter / bubble chart"
    description = "Plot pairs of numbers to see relationships. Add a size column to make it a bubble chart."
    settings = (
        Setting("trendline", "Draw a straight trend line", "choice", "no", YES_NO),
        X_LABEL, Y_LABEL,
    )
    tables = _data(
        "One row per point. Group (optional) colors points by group; Size (optional) makes bubbles.",
        Column("x", "X", "number"),
        Column("y", "Y", "number"),
        Column("group", "Group", required=False, aliases=("category", "series")),
        Column("size", "Size", "number", required=False, minimum=0, help="Bubble size (0 or more)"),
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        rows = _rows(p)
        groups: dict[str, list[list[Any]]] = {}
        for r in rows:
            groups.setdefault(r[2] or "", []).append(r)
        sizes = [r[3] for r in rows if r[3] is not None]
        lo, hi = (min(sizes), max(sizes)) if sizes else (0, 0)

        def area(v: float | None) -> float:
            if not sizes:
                return 46.0
            if v is None:
                v = lo
            return 60 + 700 * (v - lo) / (hi - lo) if hi > lo else 240.0

        colors = core.color_cycle(len(groups))
        fig, ax = new_figure(plt, p.title, (8.0, 5.8))
        for color, (name, pts) in zip(colors, groups.items()):
            ax.scatter([r[0] for r in pts], [r[1] for r in pts], s=[area(r[3]) for r in pts], color=color,
                       alpha=0.65 if sizes else 0.85, edgecolor="white", linewidth=0.8, zorder=3)
        if is_on(p.settings["trendline"]):
            xs = [r[0] for r in rows]
            if len(set(xs)) >= 2:
                import numpy as np
                slope, intercept = np.polyfit(xs, [r[1] for r in rows], 1)
                x0, x1 = min(xs), max(xs)
                ax.plot([x0, x1], [slope * x0 + intercept, slope * x1 + intercept], color="#555555",
                        linestyle="--", linewidth=1.6, zorder=4)
        tidy(ax, p.settings["x_label"], p.settings["y_label"], grid="both")
        if len(groups) > 1 or is_on(p.settings["trendline"]):
            from matplotlib.lines import Line2D
            handles = [Line2D([], [], marker="o", linestyle="", markersize=9, color=c, alpha=0.8)
                       for c, name in zip(colors, groups) if name]
            names = [name for name in groups if name]
            if is_on(p.settings["trendline"]):
                handles.append(Line2D([], [], color="#555555", linestyle="--"))
                names.append("Trend")
            ax.legend(handles, names, frameon=False, loc="best")
        return finish(fig)


class HeatmapChart(TableChart):
    id = "heatmap"
    csv_notes = "Each row/column pair may appear only once. Missing pairs are drawn grey."
    label = "Heatmap"
    description = "A grid of colored cells - darker means bigger. Good for comparing two categories."
    settings = (
        Setting("values", "Print the number in each cell", "choice", "yes", YES_NO),
        Setting("colormap", "Colors", "choice", "Blues",
                ("Blues", "Greens", "Reds", "YlOrRd", "viridis", "coolwarm")),
        X_LABEL, Y_LABEL,
    )
    tables = _data(
        "One row per cell. Row and Column say where it goes; each pair may appear once.",
        Column("row", "Row", aliases=("y",)),
        Column("column", "Column", aliases=("col", "x")),
        Column("value", "Value", "number"),
    )

    @staticmethod
    def _duplicate(rows: list[list[Any]]) -> tuple[int, str, str] | None:
        seen: set[tuple[str, str]] = set()
        for i, (r, c, _v) in enumerate(rows):
            if (r, c) in seen:
                return i, r, c
            seen.add((r, c))
        return None

    def check_ready(self, p: TableProject) -> None:
        super().check_ready(p)
        if dup := self._duplicate(_rows(p)):
            raise ValueError(f'Row "{dup[1]}" / column "{dup[2]}" appears more than once on the Data tab.')

    def check_csv(self, p: TableProject, path: Any) -> None:
        if dup := self._duplicate(_rows(p)):
            raise CsvError(f'{path.name} row {dup[0] + 2}: row "{dup[1]}" / column "{dup[2]}" '
                           "appears more than once; each pair may appear only once.")

    def draw(self, p: TableProject, plt: Any) -> Any:
        rows = _rows(p)
        row_names = list(dict.fromkeys(r[0] for r in rows))
        col_names = list(dict.fromkeys(r[1] for r in rows))
        grid = [[math.nan] * len(col_names) for _ in row_names]
        for r, c, v in rows:
            grid[row_names.index(r)][col_names.index(c)] = v
        fig, ax = new_figure(plt, p.title, (max(6.5, 0.9 * len(col_names) + 3.5), max(4.0, 0.6 * len(row_names) + 2.5)))
        cmap = plt.get_cmap(p.settings["colormap"]).copy()
        cmap.set_bad("#F2F2F2")
        im = ax.imshow(grid, cmap=cmap, aspect="auto")
        ax.set_xticks(range(len(col_names)), col_names)
        ax.set_yticks(range(len(row_names)), row_names)
        rotate_if_crowded(ax, col_names)
        if is_on(p.settings["values"]):
            for i, r in enumerate(grid):
                for j, v in enumerate(r):
                    if v == v:
                        red, green, blue, _a = im.cmap(im.norm(v))
                        dark = 0.299 * red + 0.587 * green + 0.114 * blue < 0.5
                        ax.text(j, i, fmt_num(v) if abs(v) < 1e6 else f"{v:.3g}", ha="center", va="center",
                                fontsize=10, color="white" if dark else "#222222")
        tidy(ax, p.settings["x_label"], p.settings["y_label"], grid="")
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.tick_params(length=0)
        fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03)
        return finish(fig)
