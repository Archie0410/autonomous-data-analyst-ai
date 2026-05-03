"""
LLM-driven SQL repair.

When `run_sql` fails, the executor's tool dispatcher invokes this module to
synthesize a corrected query from the error message + schema. The repair is
*transparent* — the executor sees the final (successful) SQL result, but the
trace records every repair attempt so the user can audit what happened.

Bounded by `settings.agent_max_fix_attempts`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional

from openai import OpenAI

from app.agent.prompts import SQL_REPAIR_SYSTEM
from app.agent.sql_tool import SQLResult, run_sql
from app.config import settings
from app.utils.logger import logger


@dataclass
class RepairAttempt:
    attempt: int
    failed_sql: str
    error: str
    repaired_sql: Optional[str] = None
    explanation: Optional[str] = None
    succeeded: bool = False


@dataclass
class RepairOutcome:
    final_result: SQLResult
    attempts: List[RepairAttempt] = field(default_factory=list)

    @property
    def repair_count(self) -> int:
        return len(self.attempts)


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _ask_for_fix(failed_sql: str, error: str, schema_text: str) -> Optional[dict]:
    """Single LLM call returning {sql, explanation} or None on failure."""
    if not settings.openai_api_key:
        return None
    user = (
        f"Schema:\n{schema_text}\n\n"
        f"Failed SQL:\n{failed_sql}\n\n"
        f"Error:\n{error}\n\n"
        "Reply with the JSON repair object now."
    )
    try:
        resp = _client().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SQL_REPAIR_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )
        text = (resp.choices[0].message.content or "").strip()
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
        obj = json.loads(text)
        sql = (obj.get("sql") or "").strip().rstrip(";").strip()
        if not sql:
            return None
        return {"sql": sql, "explanation": obj.get("explanation") or ""}
    except Exception as e:  # noqa: BLE001
        logger.warning("SQL repair LLM call failed: {}", e)
        return None


def run_sql_with_repair(
    sql: str,
    schema_text: str,
    max_attempts: Optional[int] = None,
) -> RepairOutcome:
    """
    Execute SQL. On failure, ask the LLM for a corrected query and retry.

    Returns the final SQLResult plus the full list of repair attempts (empty if
    the first execution succeeded). Bounded by `agent_max_fix_attempts` so a
    truly broken query can't loop forever.
    """
    cap = settings.agent_max_fix_attempts if max_attempts is None else max_attempts

    result = run_sql(sql)
    if result.success:
        return RepairOutcome(final_result=result)

    attempts: List[RepairAttempt] = []
    current_sql = sql
    last_error = result.error or "Unknown SQL error"

    for i in range(1, cap + 1):
        logger.info("SQL repair attempt {}/{}", i, cap)
        attempt = RepairAttempt(
            attempt=i, failed_sql=current_sql, error=last_error
        )
        fix = _ask_for_fix(current_sql, last_error, schema_text)
        if not fix:
            attempts.append(attempt)
            return RepairOutcome(final_result=result, attempts=attempts)

        attempt.repaired_sql = fix["sql"]
        attempt.explanation = fix["explanation"]

        new_result = run_sql(fix["sql"])
        attempt.succeeded = new_result.success
        attempts.append(attempt)

        if new_result.success:
            logger.info("SQL repair OK on attempt {}", i)
            return RepairOutcome(final_result=new_result, attempts=attempts)

        # Set up next iteration with the latest failed query/error.
        current_sql = fix["sql"]
        last_error = new_result.error or "Unknown SQL error"
        result = new_result

    logger.warning("SQL repair exhausted after {} attempts", cap)
    return RepairOutcome(final_result=result, attempts=attempts)
