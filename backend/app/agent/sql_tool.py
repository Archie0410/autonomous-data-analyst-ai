"""
SQL tool: safely execute SELECT-style queries against the active dataset.

Hard rules:
  - Only one statement per call.
  - Only read-only statements (SELECT, WITH ... SELECT, EXPLAIN, PRAGMA table_info).
  - Hard row limit injected automatically.
  - Returns dataframe + JSON-safe preview.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sqlalchemy import text

from app.services.database import get_engine
from app.utils.json_safe import df_preview
from app.utils.logger import logger

MAX_ROWS = 1000

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|attach|detach|replace|"
    r"vacuum|reindex|grant|revoke)\b",
    re.IGNORECASE,
)
_ALLOWED_START = re.compile(r"^\s*(select|with|explain|pragma)\b", re.IGNORECASE)


@dataclass
class SQLResult:
    success: bool
    sql: str
    rows: list
    columns: list
    row_count: int
    truncated: bool
    error: Optional[str] = None
    preview: Optional[dict] = None


def _validate(sql: str) -> Optional[str]:
    s = sql.strip().rstrip(";").strip()
    if not s:
        return "Empty SQL."
    if ";" in s:
        return "Only a single statement is allowed (no `;`)."
    if not _ALLOWED_START.match(s):
        return "Only SELECT / WITH / EXPLAIN / PRAGMA queries are allowed."
    if _FORBIDDEN.search(s):
        return "DML/DDL statements are not allowed."
    return None


def _inject_limit(sql: str, limit: int) -> str:
    s = sql.strip().rstrip(";").strip()
    if re.search(r"\blimit\s+\d+\b", s, re.IGNORECASE):
        return s
    return f"{s} LIMIT {limit}"


def run_sql(sql: str, limit: int = MAX_ROWS) -> SQLResult:
    """Execute a read-only SQL query against the active SQLite database."""
    err = _validate(sql)
    if err:
        return SQLResult(
            success=False,
            sql=sql,
            rows=[],
            columns=[],
            row_count=0,
            truncated=False,
            error=err,
        )

    safe_sql = _inject_limit(sql, limit + 1)
    try:
        engine = get_engine()
        with engine.connect() as conn:
            df = pd.read_sql_query(text(safe_sql), conn)
        truncated = len(df) > limit
        if truncated:
            df = df.head(limit)
        prev = df_preview(df, n=min(20, len(df)))
        logger.info("SQL OK rows={} cols={}", len(df), df.shape[1])
        return SQLResult(
            success=True,
            sql=safe_sql,
            rows=prev["rows"],
            columns=prev["columns"],
            row_count=int(len(df)),
            truncated=truncated,
            preview=prev,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("SQL FAIL: {} | sql={}", e, safe_sql)
        return SQLResult(
            success=False,
            sql=safe_sql,
            rows=[],
            columns=[],
            row_count=0,
            truncated=False,
            error=str(e),
        )


def list_tables() -> list[str]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ).fetchall()
    return [r[0] for r in rows if not r[0].startswith("sqlite_")]
