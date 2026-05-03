"""
High-level agent entry point used by the FastAPI route layer.

Responsibilities:
  - Resolve the dataset (explicit dataset_id or vector-store retrieval).
  - Pull conversation memory + per-session agent scratchpad.
  - Run the LangGraph pipeline (Planner -> Executor -> Critic) which now also
    auto-repairs failed SQL.
  - Persist the chat turn, the full audit log, and an updated memory snapshot.
  - Return a `QueryResponse` ready for the frontend.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent.graph import AgentState, get_graph
from app.models.db_models import Dataset, QueryLog
from app.models.schemas import (
    AgentStep,
    ChartSpec,
    MemorySnapshot,
    PlanStep,
    QueryRequest,
    QueryResponse,
)
from app.services import memory
from app.services.ingestion import get_schema_summary
from app.services.vector_store import vector_store
from app.utils.logger import logger


def _resolve_dataset(db: Session, req: QueryRequest) -> Dataset | None:
    if req.dataset_id is not None:
        return db.get(Dataset, req.dataset_id)

    hits = vector_store.search(req.question, top_k=1)
    if hits:
        ds = db.get(Dataset, hits[0][0])
        if ds:
            return ds

    return db.query(Dataset).order_by(Dataset.created_at.desc()).first()


def _summarize_table_for_memory(rows: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    if not rows:
        return {}
    cols = list(rows[0].keys()) if isinstance(rows[0], dict) else []
    return {
        "columns": cols,
        "rows": rows[: min(5, len(rows))],
        "row_count": len(rows),
    }


def _summarize_chart_for_memory(chart: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not chart:
        return {}
    return {
        "chart_type": chart.get("chart_type"),
        "title": chart.get("title"),
        "x": chart.get("x"),
        "y": chart.get("y"),
    }


def run_agent(db: Session, req: QueryRequest) -> QueryResponse:
    ds = _resolve_dataset(db, req)
    if ds is None:
        return QueryResponse(
            success=False,
            session_id=req.session_id,
            question=req.question,
            answer="No dataset is available. Please upload a CSV first.",
            error="no_dataset",
        )

    schema_text = get_schema_summary(db, ds.id)
    history_text = memory.transcript(db, req.session_id, limit=8)
    mem = memory.get_agent_memory(db, req.session_id)
    memory_text = memory.render_agent_memory(mem)

    state = AgentState(
        question=req.question,
        schema_text=schema_text,
        table_name=ds.table_name,
        history_text=history_text,
        memory_text=memory_text,
    )

    memory.append_message(db, req.session_id, "user", req.question, dataset_id=ds.id)

    try:
        out = get_graph().invoke(state)
        state = out if isinstance(out, AgentState) else AgentState(**out)  # type: ignore[arg-type]
    except Exception as e:  # noqa: BLE001
        logger.exception("Agent crashed")
        _persist_log(
            db, req, ds.id, plan="", plan_steps=[], steps=[],
            answer=f"Internal error: {e}", success=False, error=str(e),
        )
        return QueryResponse(
            success=False,
            session_id=req.session_id,
            question=req.question,
            answer=f"Sorry, I hit an internal error: {e}",
            error=str(e),
        )

    chart_spec = None
    if state.chart and state.chart.get("data"):
        chart_spec = ChartSpec(**state.chart)

    memory.append_message(
        db, req.session_id, "assistant", state.final_answer, dataset_id=ds.id
    )

    if state.success:
        updated_mem = memory.update_agent_memory(
            db,
            req.session_id,
            dataset_id=ds.id,
            last_question=req.question,
            last_sql=state.last_sql,
            last_python=state.last_python,
            last_result_json=_summarize_table_for_memory(state.table) or None,
            last_chart_json=_summarize_chart_for_memory(state.chart) or None,
        )
    else:
        updated_mem = mem

    _persist_log(
        db, req, ds.id,
        plan=state.plan,
        plan_steps=state.plan_steps,
        steps=state.steps,
        answer=state.final_answer,
        success=state.success,
        error=state.error,
    )

    steps_typed = [AgentStep(**_coerce_step(s)) for s in state.steps]
    plan_steps_typed = [PlanStep(**_coerce_plan_step(s)) for s in state.plan_steps]

    return QueryResponse(
        success=state.success,
        session_id=req.session_id,
        question=req.question,
        answer=state.final_answer,
        plan=state.plan,
        plan_steps=plan_steps_typed,
        steps=steps_typed,
        table=state.table,
        chart=chart_spec,
        memory=_memory_snapshot(updated_mem),
        repairs=state.repair_count,
        error=state.error,
    )


def _coerce_step(s: dict) -> dict:
    return {
        "step": int(s.get("step", 0)),
        "role": str(s.get("role", "tool")),
        "tool": s.get("tool"),
        "input": s.get("input"),
        "output": s.get("output"),
        "error": s.get("error"),
    }


def _coerce_plan_step(s: dict) -> dict:
    return {
        "id": int(s.get("id", 0)),
        "intent": str(s.get("intent", "")),
        "tool": s.get("tool"),
        "expected": s.get("expected"),
        "status": str(s.get("status", "pending")),
    }


def _memory_snapshot(mem) -> Optional[MemorySnapshot]:
    if mem is None:
        return None
    res = mem.last_result_json or {}
    chart = mem.last_chart_json or {}
    return MemorySnapshot(
        last_sql=mem.last_sql,
        last_chart_type=chart.get("chart_type"),
        last_result_columns=list(res.get("columns") or []),
        last_result_row_count=int(res.get("row_count") or 0),
        facts=list(mem.facts_json or []),
    )


def _persist_log(
    db: Session,
    req: QueryRequest,
    dataset_id: int,
    plan: str,
    plan_steps: list,
    steps: list,
    answer: str,
    success: bool,
    error: str | None,
) -> None:
    log = QueryLog(
        session_id=req.session_id,
        dataset_id=dataset_id,
        user_query=req.question,
        plan=plan,
        plan_steps_json=[_coerce_plan_step(s) for s in plan_steps],
        steps_json=[_coerce_step(s) for s in steps],
        final_answer=answer,
        success=success,
        error=error,
    )
    db.add(log)
    db.commit()
