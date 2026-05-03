"""Pydantic request/response schemas for the public API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------- Datasets ----------


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    sample_values: List[Any] = []
    null_count: int = 0


class DatasetSummary(BaseModel):
    id: int
    name: str
    table_name: str
    original_filename: str
    row_count: int
    column_count: int
    created_at: datetime


class DatasetDetail(DatasetSummary):
    columns: List[ColumnInfo]
    preview: List[Dict[str, Any]]


# ---------- Query / Agent ----------


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    dataset_id: Optional[int] = None
    session_id: str = Field(default="default")


class PlanStep(BaseModel):
    """One unit of a multi-step plan produced by the Planner."""

    id: int
    intent: str
    tool: Optional[str] = None  # run_sql | run_python | generate_plot | reason
    expected: Optional[str] = None
    status: str = "pending"  # pending | done | failed | skipped


class AgentStep(BaseModel):
    step: int
    role: str  # planner | executor | critic | tool | repair
    tool: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    error: Optional[str] = None


class ChartSpec(BaseModel):
    """A minimal, framework-agnostic chart description rendered by the frontend."""

    chart_type: str  # bar | line | pie | scatter | histogram | table
    title: Optional[str] = None
    x: Optional[str] = None
    y: Optional[List[str]] = None
    data: List[Dict[str, Any]] = []


class MemorySnapshot(BaseModel):
    """Compact summary of the agent's session-level memory after this run."""

    last_sql: Optional[str] = None
    last_chart_type: Optional[str] = None
    last_result_columns: List[str] = []
    last_result_row_count: int = 0
    facts: List[str] = []


class QueryResponse(BaseModel):
    success: bool
    session_id: str
    question: str
    answer: str
    plan: Optional[str] = None
    plan_steps: List[PlanStep] = []
    steps: List[AgentStep] = []
    table: Optional[List[Dict[str, Any]]] = None
    chart: Optional[ChartSpec] = None
    memory: Optional[MemorySnapshot] = None
    repairs: int = 0
    error: Optional[str] = None


# ---------- History ----------


class HistoryItem(BaseModel):
    id: int
    session_id: str
    dataset_id: Optional[int]
    user_query: str
    final_answer: Optional[str]
    success: bool
    created_at: datetime
