"""
SQLAlchemy ORM models for system metadata.

The user's uploaded data is stored in dynamically named tables (one per dataset).
These models only describe the *system* tables: dataset registry, chat history,
and query/execution logs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    """Registry of all uploaded datasets."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_count: Mapped[int] = mapped_column(Integer, default=0)
    schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    """Conversation memory for follow-up questions."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    dataset_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("datasets.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user|assistant|system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QueryLog(Base):
    """Full audit trail of agent runs (plan, tool calls, errors, final answer)."""

    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    dataset_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("datasets.id"), nullable=True
    )
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_steps_json: Mapped[list] = mapped_column(JSON, default=list)
    steps_json: Mapped[list] = mapped_column(JSON, default=list)
    final_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(default=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentMemory(Base):
    """
    Per-session scratchpad updated after every successful agent run.

    Stores enough context for follow-ups like "now show only top 3" or
    "plot that as a pie chart" to be answered without re-deriving everything
    from chat history alone.
    """

    __tablename__ = "agent_memory"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("datasets.id"), nullable=True
    )
    last_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_sql: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_python: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_chart_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    facts_json: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
