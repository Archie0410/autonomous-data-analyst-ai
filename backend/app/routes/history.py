"""History + chat-message browse endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.models.db_models import ChatMessage, QueryLog
from app.models.schemas import HistoryItem
from app.services.database import get_session

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history", response_model=List[HistoryItem])
def list_history(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_session),
) -> List[HistoryItem]:
    q = db.query(QueryLog).order_by(QueryLog.created_at.desc())
    if session_id:
        q = q.filter(QueryLog.session_id == session_id)
    rows = q.limit(limit).all()
    return [
        HistoryItem(
            id=r.id,
            session_id=r.session_id,
            dataset_id=r.dataset_id,
            user_query=r.user_query,
            final_answer=r.final_answer,
            success=r.success,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/sessions/{session_id}/messages")
def list_messages(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_session),
):
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
