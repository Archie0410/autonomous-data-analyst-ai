"""OpenAI function-calling JSON schemas for the agent's tools."""

from __future__ import annotations

from typing import Any, Dict, List

TOOL_SPECS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "Execute a single read-only SQLite SELECT/WITH/EXPLAIN/PRAGMA query "
                "against the active dataset table. Returns rows + columns + row_count."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A single SQL statement, no trailing semicolon.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": (
                "Execute pandas analysis code. The current dataset is preloaded as "
                "`df` (pandas.DataFrame). Pandas is `pd`, numpy is `np`. Assign your "
                "final answer to a variable named `result` (DataFrame, dict, list, or scalar)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code that uses `df`, `pd`, `np` and assigns to `result`.",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_plot",
            "description": (
                "Build a chart spec from tabular data (a list of row dicts produced by "
                "a previous tool call). Use chart_type='auto' to infer the best chart."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of row objects to chart.",
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line", "pie", "scatter", "histogram", "table", "auto"],
                        "default": "auto",
                    },
                    "x": {"type": "string", "description": "Column name for X axis (optional)."},
                    "y": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Column name(s) for Y axis (optional).",
                    },
                    "title": {"type": "string"},
                },
                "required": ["data"],
            },
        },
    },
]
