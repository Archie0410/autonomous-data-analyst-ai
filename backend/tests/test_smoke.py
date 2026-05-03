"""Smoke tests that don't require an OpenAI key."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.database import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


CSV = b"""order_id,customer,amount,order_date
1,Alice,100,2024-01-15
2,Bob,250,2024-01-18
3,Alice,80,2024-02-02
4,Carol,420,2024-02-10
5,Bob,30,2024-02-12
"""


def test_health(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_and_list(client) -> None:
    r = client.post(
        "/api/datasets/upload",
        files={"file": ("orders.csv", io.BytesIO(CSV), "text/csv")},
        data={"name": "orders"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 5
    assert body["column_count"] == 4
    assert "preview" in body and len(body["preview"]) == 5

    r2 = client.get("/api/datasets")
    assert r2.status_code == 200
    assert any(d["id"] == body["id"] for d in r2.json())


def test_sql_tool_blocks_dml() -> None:
    from app.agent.sql_tool import run_sql

    r = run_sql("DROP TABLE orders")
    assert not r.success
    assert "allowed" in (r.error or "").lower()


def test_python_sandbox_blocks_imports() -> None:
    from app.agent.python_tool import run_python

    r = run_python("import os\nresult = os.listdir('.')", table_name="missing")
    assert not r.success


def test_sql_repair_skips_when_no_api_key(monkeypatch) -> None:
    """Without an API key the repair layer should be a no-op pass-through."""
    from app.agent import sql_repair as sr
    from app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "")

    # A clearly broken query against a real table.
    out = sr.run_sql_with_repair(
        sql="SELECT * FROM no_such_table_xyz",
        schema_text="Table: orders\nColumns: id, customer",
    )
    assert not out.final_result.success
    assert out.repair_count == 1  # one attempt logged, but LLM call was skipped
    assert out.attempts[0].repaired_sql is None


def test_agent_memory_upsert(client) -> None:
    """Agent memory should round-trip via the service layer."""
    from app.services.database import session_scope
    from app.services import memory as mem_svc

    with session_scope() as db:
        mem_svc.update_agent_memory(
            db,
            session_id="t-session",
            last_question="top 5 customers?",
            last_sql="SELECT customer, SUM(amount) FROM orders GROUP BY 1 ORDER BY 2 DESC LIMIT 5",
            last_result_json={"columns": ["customer", "total"], "rows": [{"customer": "Alice", "total": 180}]},
        )

    with session_scope() as db:
        m = mem_svc.get_agent_memory(db, "t-session")
        assert m is not None
        assert m.last_sql.startswith("SELECT customer")
        rendered = mem_svc.render_agent_memory(m)
        assert "Previous SQL" in rendered
        assert "Alice" in rendered
