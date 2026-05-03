"""
Conversation memory + per-session agent scratchpad.

Two layers:
  1. `ChatMessage` rows — raw user/assistant transcript for compact prompting.
  2. `AgentMemory` row — structured scratchpad updated after each successful
     run (last SQL, last result preview, last chart, derived facts). The
     planner and executor read this to handle follow-ups like
     "now show only top 3" or "plot that as a pie chart" without re-deriving
     everything from chat history.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.db_models import AgentMemory, ChatMessage


# ---------- chat transcript ----------


def append_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    dataset_id: int | None = None,
) -> None:
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        dataset_id=dataset_id,
    )
    db.add(msg)
    db.commit()


def get_recent_messages(db: Session, session_id: str, limit: int = 10) -> List[ChatMessage]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def transcript(db: Session, session_id: str, limit: int = 10) -> str:
    msgs = get_recent_messages(db, session_id, limit=limit)
    if not msgs:
        return "(no prior conversation)"
    lines = []
    for m in msgs:
        prefix = m.role.upper()
        body = m.content if len(m.content) < 600 else (m.content[:600] + "...")
        lines.append(f"{prefix}: {body}")
    return "\n".join(lines)


# ---------- agent scratchpad ----------


def get_agent_memory(db: Session, session_id: str) -> Optional[AgentMemory]:
    return db.get(AgentMemory, session_id)


def update_agent_memory(
    db: Session,
    session_id: str,
    *,
    dataset_id: Optional[int] = None,
    last_question: Optional[str] = None,
    last_sql: Optional[str] = None,
    last_python: Optional[str] = None,
    last_result_json: Optional[Dict[str, Any]] = None,
    last_chart_json: Optional[Dict[str, Any]] = None,
    facts: Optional[List[str]] = None,
) -> AgentMemory:
    """Upsert helper. Only fields explicitly passed are overwritten."""
    mem = db.get(AgentMemory, session_id)
    if mem is None:
        mem = AgentMemory(session_id=session_id)
        db.add(mem)

    if dataset_id is not None:
        mem.dataset_id = dataset_id
    if last_question is not None:
        mem.last_question = last_question
    if last_sql is not None:
        mem.last_sql = last_sql
    if last_python is not None:
        mem.last_python = last_python
    if last_result_json is not None:
        mem.last_result_json = last_result_json
    if last_chart_json is not None:
        mem.last_chart_json = last_chart_json
    if facts is not None:
        existing = list(mem.facts_json or [])
        for f in facts:
            if f and f not in existing:
                existing.append(f)
        mem.facts_json = existing[-12:]  # keep the most recent 12 facts

    db.commit()
    db.refresh(mem)
    return mem


def render_agent_memory(mem: Optional[AgentMemory]) -> str:
    """Compact, prompt-friendly rendering of the scratchpad."""
    if mem is None:
        return "(no prior agent memory)"
    parts: List[str] = []
    if mem.last_question:
        parts.append(f"Previous question: {mem.last_question}")
    if mem.last_sql:
        parts.append(f"Previous SQL:\n{mem.last_sql}")
    res = mem.last_result_json or {}
    cols = res.get("columns") or []
    rows = res.get("rows") or []
    if cols:
        parts.append(
            f"Previous result columns ({len(cols)}): {', '.join(map(str, cols))}"
        )
    if rows:
        sample = rows[: min(5, len(rows))]
        parts.append(f"Previous result rows (first {len(sample)}):\n{sample}")
    chart = mem.last_chart_json or {}
    if chart.get("chart_type"):
        parts.append(
            f"Previous chart: {chart.get('chart_type')} "
            f"(x={chart.get('x')}, y={chart.get('y')})"
        )
    facts = mem.facts_json or []
    if facts:
        parts.append("Known facts: " + " | ".join(facts[-6:]))
    return "\n\n".join(parts) if parts else "(no prior agent memory)"
