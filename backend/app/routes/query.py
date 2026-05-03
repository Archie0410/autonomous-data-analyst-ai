"""Natural-language query endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.agent import run_agent
from app.models.schemas import QueryRequest, QueryResponse
from app.services.database import get_session
from app.utils.logger import logger

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
def post_query(req: QueryRequest, db: Session = Depends(get_session)) -> QueryResponse:
    if not req.question.strip():
        raise HTTPException(400, "Question cannot be empty.")
    logger.info("[/query] session={} dataset={} q={!r}", req.session_id, req.dataset_id, req.question)
    return run_agent(db, req)
