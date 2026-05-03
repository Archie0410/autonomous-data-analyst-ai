"""
Helpers to serialize pandas / numpy objects safely to JSON.

LLM tool calls and HTTP responses must never crash on NaN, datetime, or numpy types.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def _scalar(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, datetime, date)):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:
            return str(v)
    return v


def to_json_safe(obj: Any) -> Any:
    """Recursively convert pandas/numpy objects into JSON-safe Python primitives."""
    if isinstance(obj, pd.DataFrame):
        records = obj.where(pd.notna(obj), None).to_dict(orient="records")
        return [to_json_safe(r) for r in records]
    if isinstance(obj, pd.Series):
        return to_json_safe(obj.where(pd.notna(obj), None).to_dict())
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_json_safe(v) for v in obj]
    return _scalar(obj)


def df_preview(df: pd.DataFrame, n: int = 10) -> dict:
    """Compact JSON-safe preview of a dataframe (head + shape + dtypes)."""
    head = df.head(n)
    return {
        "columns": list(map(str, df.columns)),
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "shape": [int(df.shape[0]), int(df.shape[1])],
        "rows": to_json_safe(head),
    }
