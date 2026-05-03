"""
Visualization tool: produce a chart spec from a list of records.

We don't render server-side. Instead we emit a small JSON spec that the React
frontend renders with Plotly. The agent can either:
  - explicitly call `generate_plot(...)` with a chart_type, x, and y fields, OR
  - pass `chart_type="auto"` to let us infer the best chart from the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from app.utils.json_safe import to_json_safe
from app.utils.logger import logger

ALLOWED_TYPES = {"bar", "line", "pie", "scatter", "histogram", "table", "auto"}


@dataclass
class VizResult:
    success: bool
    chart_type: str
    title: Optional[str]
    x: Optional[str]
    y: Optional[List[str]]
    data: List[Dict[str, Any]]
    error: Optional[str] = None


def _is_numeric(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series)


def _is_temporal(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    try:
        pd.to_datetime(series.dropna().head(20), errors="raise")
        return True
    except Exception:  # noqa: BLE001
        return False


def _auto_select(df: pd.DataFrame) -> tuple[str, Optional[str], Optional[List[str]]]:
    """Choose the most appropriate chart type from a small dataframe."""
    if df.shape[1] == 0 or df.shape[0] == 0:
        return "table", None, None

    cols = list(df.columns)
    numeric_cols = [c for c in cols if _is_numeric(df[c])]
    non_numeric_cols = [c for c in cols if c not in numeric_cols]

    if df.shape[1] == 1 and numeric_cols:
        return "histogram", numeric_cols[0], None

    if len(non_numeric_cols) >= 1 and len(numeric_cols) >= 1:
        x = non_numeric_cols[0]
        y = numeric_cols[: min(3, len(numeric_cols))]
        if _is_temporal(df[x]):
            return "line", x, y
        if df[x].nunique() <= 8 and len(y) == 1:
            return "pie", x, y
        return "bar", x, y

    if len(numeric_cols) >= 2:
        return "scatter", numeric_cols[0], [numeric_cols[1]]

    return "table", None, None


def generate_plot(
    data: List[Dict[str, Any]],
    chart_type: str = "auto",
    x: Optional[str] = None,
    y: Optional[List[str]] = None,
    title: Optional[str] = None,
) -> VizResult:
    """Create a chart spec. Returns a JSON-safe payload the frontend can render."""
    if chart_type not in ALLOWED_TYPES:
        return VizResult(
            success=False, chart_type=chart_type, title=title, x=x, y=y, data=[],
            error=f"Unknown chart_type {chart_type!r}. Allowed: {sorted(ALLOWED_TYPES)}",
        )

    if not data:
        return VizResult(
            success=False, chart_type=chart_type, title=title, x=x, y=y, data=[],
            error="No data provided to plot.",
        )

    try:
        df = pd.DataFrame(data)
    except Exception as e:  # noqa: BLE001
        return VizResult(
            success=False, chart_type=chart_type, title=title, x=x, y=y, data=[],
            error=f"Could not build dataframe: {e}",
        )

    if chart_type == "auto":
        ctype, ax, ay = _auto_select(df)
        chart_type = ctype
        x = x or ax
        y = y or ay

    if y and not isinstance(y, list):
        y = [y]

    data_safe = to_json_safe(df.head(200))
    logger.info("Viz {} x={} y={} rows={}", chart_type, x, y, len(data_safe))
    return VizResult(
        success=True,
        chart_type=chart_type,
        title=title,
        x=x,
        y=y,
        data=data_safe,
    )
