"""
Chart types. Each one is registered here; the app reads this list for the picker and
asks the chart type to load, import, draw and describe itself.
"""
from __future__ import annotations

from .base import ChartType, CsvError
from .gantt import GanttChart
from .layouts import OrgChart, TimelineChart, TreemapChart
from .simple import (BoxPlotChart, BurndownChart, FunnelChart, HeatmapChart, HistogramChart,
                     ParetoChart, PieChart, ScatterChart, WaterfallChart)
from .wide import AreaChart, BarChart, LineChart, RadarChart

# Picker order: the common ones first.
CHART_TYPES: dict[str, ChartType] = {c.id: c for c in (
    GanttChart(), BarChart(), LineChart(), PieChart(), AreaChart(), ScatterChart(), HistogramChart(),
    BoxPlotChart(), HeatmapChart(), TimelineChart(), BurndownChart(), WaterfallChart(), FunnelChart(),
    ParetoChart(), RadarChart(), TreemapChart(), OrgChart(),
)}

__all__ = ["CHART_TYPES", "ChartType", "CsvError", "get"]


def get(type_id: str) -> ChartType:
    try:
        return CHART_TYPES[type_id]
    except KeyError:
        known = ", ".join(CHART_TYPES)
        raise ValueError(f'Unknown chart type "{type_id}". This version knows: {known}.') from None
