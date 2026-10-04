"""Charts with a label column and one numeric column per series: bar, line, area, radar."""
from __future__ import annotations

import math
from typing import Any

from chart_core import fmt_num

from .table import (YES_NO, Setting, TableProject, WideChart, finish, is_on, new_figure,
                    rotate_if_crowded, tidy)

NAN = float("nan")
AXIS_LABELS = (Setting("x_label", "X-axis label (optional)", help="Text under the horizontal axis"),
               Setting("y_label", "Y-axis label (optional)", help="Text beside the vertical axis"))


def _zeros(values: list[float | None]) -> list[float]:
    return [0.0 if v is None else float(v) for v in values]


def _gaps(values: list[float | None]) -> list[float]:
    return [NAN if v is None else float(v) for v in values]


class BarChart(WideChart):
    id = "bar"
    csv_notes = "Rows are drawn in file order."
    label = "Bar / column chart"
    description = "Compare values across categories. Grouped, stacked, vertical or horizontal."
    settings = (
        Setting("orientation", "Direction", "choice", "vertical", ("vertical", "horizontal")),
        Setting("mode", "Several series", "choice", "grouped", ("grouped", "stacked"),
                help="Side by side, or stacked on top of each other"),
        Setting("values", "Print the value on each bar", "choice", "no", YES_NO),
        *AXIS_LABELS,
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        s = p.settings
        labels, series = self.labels(p), self.series(p)
        n, k = len(labels), len(series)
        horizontal, stacked = s["orientation"] == "horizontal", s["mode"] == "stacked" and k > 1
        slots = n * (1 if stacked else k)
        size = (8.0, max(4.0, 0.42 * slots + 2.2)) if horizontal else (max(7.0, 0.5 * slots + 3.0), 5.5)
        fig, ax = new_figure(plt, p.title, size)

        width = 0.8 if stacked or k == 1 else 0.8 / k
        pos_base, neg_base = [0.0] * n, [0.0] * n
        for j, (name, color, raw) in enumerate(series):
            vals = _zeros(raw)
            offset = 0.0 if stacked else -0.4 + width * (j + 0.5) if k > 1 else 0.0
            xs = [i + offset for i in range(n)]
            if stacked:
                base = [pos_base[i] if v >= 0 else neg_base[i] for i, v in enumerate(vals)]
                for i, v in enumerate(vals):
                    (pos_base if v >= 0 else neg_base)[i] += v
            else:
                base = [0.0] * n
            draw = ax.barh if horizontal else ax.bar
            kw = {"left": base} if horizontal else {"bottom": base}
            rects = draw(xs, vals, width, color=color, label=name, zorder=3, **kw)  # type: ignore[operator]
            if is_on(s["values"]):
                ax.bar_label(rects, labels=[fmt_num(v) if v or not stacked else "" for v in vals],
                             label_type="center" if stacked else "edge", fontsize=9,
                             color="white" if stacked else "#333333", padding=0 if stacked else 2)

        ticks = list(range(n))
        if horizontal:
            ax.set_yticks(ticks, labels)
            ax.invert_yaxis()
            tidy(ax, s["x_label"], s["y_label"], grid="x")
        else:
            ax.set_xticks(ticks, labels)
            rotate_if_crowded(ax, labels)
            tidy(ax, s["x_label"], s["y_label"], grid="y")
        if k > 1:
            ax.legend(frameon=False)
        return finish(fig)


class LineChart(WideChart):
    id = "line"
    csv_notes = "Rows are drawn in file order, left to right."
    label = "Line chart"
    description = "Show how one or more values change across an ordered set of points (time, steps)."
    settings = (
        Setting("markers", "Draw a dot at every point", "choice", "yes", YES_NO),
        *AXIS_LABELS,
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        s = p.settings
        labels, series = self.labels(p), self.series(p)
        fig, ax = new_figure(plt, p.title, (max(7.0, 0.55 * len(labels) + 3.0), 5.5))
        xs = list(range(len(labels)))
        for name, color, raw in series:
            ax.plot(xs, _gaps(raw), color=color, label=name, linewidth=2.2, zorder=3,
                    marker="o" if is_on(s["markers"]) or len(labels) == 1 else None, markersize=6)
        ax.set_xticks(xs, labels)
        rotate_if_crowded(ax, labels)
        tidy(ax, s["x_label"], s["y_label"], grid="y")
        if len(series) > 1:
            ax.legend(frameon=False)
        return finish(fig)


class AreaChart(WideChart):
    id = "area"
    csv_notes = "Rows are drawn in file order. Needs at least 2 rows."
    label = "Area chart"
    description = "Like a line chart with the area filled in. Stack series to show a total."
    min_rows = 2
    settings = (
        Setting("stacked", "Stack the series", "choice", "yes", YES_NO),
        *AXIS_LABELS,
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        s = p.settings
        labels, series = self.labels(p), self.series(p)
        fig, ax = new_figure(plt, p.title, (max(7.0, 0.55 * len(labels) + 3.0), 5.5))
        xs = list(range(len(labels)))
        if is_on(s["stacked"]):
            ax.stackplot(xs, [_zeros(v) for _n, _c, v in series], colors=[c for _n, c, _v in series],
                         labels=[n for n, _c, _v in series], alpha=0.9, zorder=3)
        else:
            for name, color, raw in series:
                ys = _zeros(raw)
                ax.fill_between(xs, ys, color=color, alpha=0.35, zorder=2)
                ax.plot(xs, ys, color=color, linewidth=2.2, label=name, zorder=3)
        ax.set_xticks(xs, labels)
        ax.set_xlim(0, len(labels) - 1)
        rotate_if_crowded(ax, labels)
        tidy(ax, s["x_label"], s["y_label"], grid="y")
        if len(series) > 1:
            ax.legend(frameon=False)
        return finish(fig)


class RadarChart(WideChart):
    id = "radar"
    csv_notes = "Each row becomes one spoke. Needs at least 3 rows."
    label = "Radar / spider chart"
    description = "Compare several measures at once on a web, e.g. skills or product ratings."
    min_rows = 3
    settings = (
        Setting("fill", "Fill the shapes", "choice", "yes", YES_NO),
    )

    def draw(self, p: TableProject, plt: Any) -> Any:
        labels, series = self.labels(p), self.series(p)
        n = len(labels)
        fig = plt.figure(figsize=(7.5, 6.5))
        ax = fig.add_subplot(111, polar=True)
        if p.title:
            fig.suptitle(p.title, fontsize=16, fontweight="bold")
        angles = [2 * math.pi * i / n for i in range(n)]
        closed = angles + angles[:1]
        ax.set_theta_offset(math.pi / 2)
        ax.set_theta_direction(-1)
        for name, color, raw in series:
            ys = _zeros(raw)
            ax.plot(closed, ys + ys[:1], color=color, linewidth=2.2, label=name, zorder=3)
            if is_on(p.settings["fill"]):
                ax.fill(closed, ys + ys[:1], color=color, alpha=0.22, zorder=2)
        ax.set_xticks(angles, labels, fontsize=11)
        ax.tick_params(axis="y", labelsize=8, colors="#777777")
        ax.grid(color="#DDDDDD")
        ax.spines["polar"].set_color("#CCCCCC")
        if len(series) > 1:
            ax.legend(loc="upper left", bbox_to_anchor=(1.05, 1.08), frameon=False)
        return finish(fig)
