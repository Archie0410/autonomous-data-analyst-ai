"""
Python execution sandbox for pandas analysis.

Design:
  - The LLM provides code that operates on a pre-loaded pandas DataFrame `df`.
  - Code runs with a restricted builtins namespace (no `open`, `eval`, `exec`,
    `__import__`, network, file I/O, subprocess, etc.).
  - The sandbox also exposes pandas as `pd` and numpy as `np`.
  - The contract is: assign your final answer to `result`. It can be a DataFrame,
    Series, dict, list, or scalar. We then JSON-serialize it safely.
  - Output is captured (stdout) and returned alongside the result for the agent's
    introspection.

This is *defense-in-depth*, not a true OS-level sandbox. For untrusted multi-tenant
production use, also run this process in a separate container with no network and
strict CPU/memory limits.
"""

from __future__ import annotations

import io
import signal
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import inspect

from app.services.database import get_engine
from app.utils.json_safe import df_preview, to_json_safe
from app.utils.logger import logger

EXEC_TIMEOUT_SEC = 15

# Block obviously dangerous names. RestrictedPython could be used for stronger
# guarantees; this list is the first line of defense.
_BANNED = {
    "open", "exec", "eval", "compile", "__import__", "input",
    "exit", "quit", "help", "globals", "vars", "locals",
    "memoryview", "bytearray",
}

# A minimal, safe builtins subset.
_SAFE_BUILTINS = {
    "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
    "range": range, "round": round, "sorted": sorted, "reversed": reversed,
    "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "any": any, "all": all, "list": list, "dict": dict, "set": set,
    "tuple": tuple, "str": str, "int": int, "float": float, "bool": bool,
    "print": print, "isinstance": isinstance, "type": type,
    "True": True, "False": False, "None": None,
}


@dataclass
class PythonResult:
    success: bool
    stdout: str
    result_type: str
    result_preview: Any
    error: Optional[str] = None


def _load_table(table_name: str) -> pd.DataFrame:
    engine = get_engine()
    insp = inspect(engine)
    if table_name not in insp.get_table_names():
        raise ValueError(f"Table not found: {table_name}")
    return pd.read_sql_table(table_name, engine)


def _has_banned_names(code: str) -> Optional[str]:
    for name in _BANNED:
        if f"{name}(" in code or f" {name} " in f" {code} ":
            return f"Use of '{name}' is not allowed in the sandbox."
    if "__" in code:
        return "Dunder access (e.g. __class__, __builtins__) is not allowed."
    return None


class _Timeout(Exception):
    pass


def _install_timeout(seconds: int):
    """Install a SIGALRM-based timeout on POSIX systems. No-op on Windows."""
    if sys.platform.startswith("win") or not hasattr(signal, "SIGALRM"):
        return None

    def _handler(signum, frame):  # noqa: ARG001
        raise _Timeout(f"Execution exceeded {seconds}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    return old


def _clear_timeout(old) -> None:
    if sys.platform.startswith("win") or not hasattr(signal, "SIGALRM"):
        return
    signal.alarm(0)
    if old is not None:
        signal.signal(signal.SIGALRM, old)


def run_python(code: str, table_name: str) -> PythonResult:
    """Execute pandas analysis code against the table loaded as `df`."""
    bad = _has_banned_names(code)
    if bad:
        return PythonResult(
            success=False,
            stdout="",
            result_type="error",
            result_preview=None,
            error=bad,
        )

    try:
        df = _load_table(table_name)
    except Exception as e:  # noqa: BLE001
        return PythonResult(
            success=False, stdout="", result_type="error", result_preview=None,
            error=f"Failed to load table {table_name!r}: {e}",
        )

    safe_globals: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "pd": pd,
        "np": np,
    }
    safe_locals: dict[str, Any] = {"df": df, "result": None}

    buf = io.StringIO()
    old = _install_timeout(EXEC_TIMEOUT_SEC)
    try:
        with redirect_stdout(buf):
            exec(compile(code, "<sandbox>", "exec"), safe_globals, safe_locals)  # noqa: S102
        result = safe_locals.get("result", None)
        rtype = type(result).__name__
        if isinstance(result, pd.DataFrame):
            preview = df_preview(result, n=20)
        elif isinstance(result, pd.Series):
            preview = df_preview(result.to_frame(), n=20)
        else:
            preview = to_json_safe(result)
        logger.info("Python OK type={} stdout_len={}", rtype, len(buf.getvalue()))
        return PythonResult(
            success=True,
            stdout=buf.getvalue()[-4000:],
            result_type=rtype,
            result_preview=preview,
        )
    except _Timeout as e:
        return PythonResult(
            success=False, stdout=buf.getvalue(), result_type="error",
            result_preview=None, error=str(e),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Python FAIL: {}", e)
        return PythonResult(
            success=False,
            stdout=buf.getvalue(),
            result_type="error",
            result_preview=None,
            error=f"{type(e).__name__}: {e}",
        )
    finally:
        _clear_timeout(old)
