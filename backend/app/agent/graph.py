"""
Agent orchestration with LangGraph.

Pipeline:
    [PLAN]  ->  [EXECUTE (tool-calling loop)]  ->  [CRITIQUE]  -> done

Key behaviors:
  - The Planner returns a STRUCTURED multi-step plan (JSON). Each step has an
    intent, suggested tool, and expected output. The Executor follows it.
  - The Executor uses OpenAI function calling. When a `run_sql` call fails, an
    LLM-driven SQL repair pass (`run_sql_with_repair`) auto-fixes obvious bugs
    transparently, recording each repair attempt in the trace.
  - SESSION MEMORY (last SQL / result / chart) is injected into the executor
    prompt so follow-ups like "now show only top 3" are grounded in concrete
    prior context.
  - The Critic optionally rewrites the answer if it judges it incorrect.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from openai import OpenAI

from app.agent.prompts import CRITIC_SYSTEM, EXECUTOR_SYSTEM, PLANNER_SYSTEM
from app.agent.python_tool import run_python
from app.agent.sql_repair import RepairOutcome, run_sql_with_repair
from app.agent.sql_tool import run_sql
from app.agent.tool_specs import TOOL_SPECS
from app.agent.viz_tool import generate_plot
from app.config import settings
from app.utils.logger import logger


# ---------------- shared state ----------------


@dataclass
class AgentState:
    question: str
    schema_text: str
    table_name: str
    history_text: str = "(none)"
    memory_text: str = "(none)"
    plan: str = ""
    plan_steps: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    table: Optional[List[Dict[str, Any]]] = None
    chart: Optional[Dict[str, Any]] = None
    last_sql: Optional[str] = None
    last_python: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    critic_verdict: Optional[Dict[str, Any]] = None
    repair_count: int = 0


# ---------------- LLM helpers ----------------


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Configure backend/.env before calling the agent."
        )
    return OpenAI(api_key=settings.openai_api_key)


def _chat(messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
          temperature: float = 0.0) -> Any:
    client = _client()
    kwargs: Dict[str, Any] = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client.chat.completions.create(**kwargs)


def _parse_json_loose(text: str) -> Optional[dict]:
    """Best-effort JSON parse: strips ``` fences and 'json' prefix."""
    if not text:
        return None
    s = text.strip().strip("`").strip()
    if s.lower().startswith("json"):
        s = s[4:].strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", s)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


# ---------------- planner ----------------


def _format_plan_for_prompt(plan_obj: dict) -> str:
    """Render a structured plan back into a numbered text block for downstream prompts."""
    lines: List[str] = []
    summary = plan_obj.get("summary") or ""
    if summary:
        lines.append(f"Summary: {summary}")
    assumptions = plan_obj.get("assumptions") or ""
    if assumptions:
        lines.append(f"Assumptions: {assumptions}")
    lines.append("Steps:")
    for s in plan_obj.get("steps", []):
        sid = s.get("id", "?")
        intent = s.get("intent", "")
        tool = s.get("tool", "")
        expected = s.get("expected", "")
        line = f"  {sid}. [{tool}] {intent}"
        if expected:
            line += f"  ->  expected: {expected}"
        lines.append(line)
    return "\n".join(lines)


def planner_node(state: AgentState) -> AgentState:
    """Produce a STRUCTURED multi-step plan (JSON) the executor will follow."""
    user_prompt = (
        f"User question: {state.question}\n\n"
        f"Conversation so far:\n{state.history_text}\n\n"
        f"Session memory (carry-over from previous turns):\n{state.memory_text}\n\n"
        f"Active dataset (use these exact column / table names):\n{state.schema_text}\n\n"
        f"Reply with the JSON plan now."
    )
    resp = _chat(
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    raw = (resp.choices[0].message.content or "").strip()

    plan_obj = _parse_json_loose(raw) or {}
    steps_raw = plan_obj.get("steps") or []
    plan_steps: List[Dict[str, Any]] = []
    for i, s in enumerate(steps_raw, start=1):
        plan_steps.append({
            "id": int(s.get("id", i)),
            "intent": str(s.get("intent", "")).strip(),
            "tool": (s.get("tool") or None),
            "expected": (s.get("expected") or None),
            "status": "pending",
        })

    if plan_steps:
        plan_text = _format_plan_for_prompt({**plan_obj, "steps": plan_steps})
    else:
        # Planner didn't comply with JSON; keep raw text as a fallback plan.
        plan_text = raw
        logger.warning("Planner returned non-JSON plan; using raw text fallback.")

    state.plan = plan_text
    state.plan_steps = plan_steps
    state.steps.append({
        "step": len(state.steps) + 1,
        "role": "planner",
        "output": {
            "summary": plan_obj.get("summary"),
            "assumptions": plan_obj.get("assumptions"),
            "steps": plan_steps,
            "raw": raw if not plan_steps else None,
        },
    })
    logger.info("PLAN:\n{}", plan_text)
    return state


# ---------------- tools ----------------


def _record_repair_steps(state: AgentState, outcome: RepairOutcome) -> None:
    """Append a 'repair' step for each LLM-driven SQL fix attempt."""
    for a in outcome.attempts:
        state.steps.append({
            "step": len(state.steps) + 1,
            "role": "repair",
            "tool": "sql_repair",
            "input": {
                "attempt": a.attempt,
                "failed_sql": a.failed_sql,
                "error": a.error,
            },
            "output": {
                "repaired_sql": a.repaired_sql,
                "explanation": a.explanation,
                "succeeded": a.succeeded,
            },
            "error": None if a.succeeded else (a.error or "repair failed"),
        })
    state.repair_count += outcome.repair_count


def _dispatch_tool(state: AgentState, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single tool call and return a JSON-safe dict result."""
    if name == "run_sql":
        outcome = run_sql_with_repair(
            sql=args.get("query", ""),
            schema_text=state.schema_text,
        )
        _record_repair_steps(state, outcome)
        r = outcome.final_result
        if r.success:
            state.last_sql = r.sql
        return {
            "success": r.success,
            "sql": r.sql,
            "row_count": r.row_count,
            "columns": r.columns,
            "rows": r.rows,
            "truncated": r.truncated,
            "error": r.error,
            "repair_attempts": outcome.repair_count,
        }
    if name == "run_python":
        r = run_python(args.get("code", ""), table_name=state.table_name)
        if r.success:
            state.last_python = args.get("code", "")
        return {
            "success": r.success,
            "result_type": r.result_type,
            "result_preview": r.result_preview,
            "stdout": r.stdout,
            "error": r.error,
        }
    if name == "generate_plot":
        r = generate_plot(
            data=args.get("data", []),
            chart_type=args.get("chart_type", "auto"),
            x=args.get("x"),
            y=args.get("y"),
            title=args.get("title"),
        )
        return {
            "success": r.success,
            "chart_type": r.chart_type,
            "title": r.title,
            "x": r.x,
            "y": r.y,
            "data": r.data,
            "error": r.error,
        }
    return {"success": False, "error": f"Unknown tool: {name}"}


def _record_tool_step(state: AgentState, tool_name: str, args: Dict[str, Any],
                      output: Dict[str, Any]) -> None:
    state.steps.append({
        "step": len(state.steps) + 1,
        "role": "tool",
        "tool": tool_name,
        "input": args,
        "output": _trim_for_log(output),
        "error": output.get("error"),
    })


def _trim_for_log(output: Dict[str, Any]) -> Dict[str, Any]:
    """Trim large fields so the trace stays small in the response."""
    out = dict(output)
    rows = out.get("rows")
    if isinstance(rows, list) and len(rows) > 20:
        out["rows"] = rows[:20]
    data = out.get("data")
    if isinstance(data, list) and len(data) > 50:
        out["data"] = data[:50]
    return out


def _mark_step_done(state: AgentState, tool_name: str) -> None:
    """Mark the first matching pending plan step as done (best-effort)."""
    for ps in state.plan_steps:
        if ps.get("status") == "pending" and ps.get("tool") == tool_name:
            ps["status"] = "done"
            return
    for ps in state.plan_steps:
        if ps.get("status") == "pending":
            ps["status"] = "done"
            return


def _mark_step_failed(state: AgentState, tool_name: str) -> None:
    for ps in state.plan_steps:
        if ps.get("status") == "pending" and ps.get("tool") == tool_name:
            ps["status"] = "failed"
            return


# ---------------- executor ----------------


def executor_node(state: AgentState) -> AgentState:
    """Tool-calling loop. Bounded by settings.agent_max_iterations."""
    state.messages = [
        {"role": "system", "content": EXECUTOR_SYSTEM},
        {
            "role": "user",
            "content": (
                f"User question: {state.question}\n\n"
                f"Plan:\n{state.plan}\n\n"
                f"Session memory (use for follow-ups):\n{state.memory_text}\n\n"
                f"Active dataset schema:\n{state.schema_text}\n\n"
                f"The active table name (for run_python) is: {state.table_name}\n\n"
                "Begin. Call tools as needed, then write the final answer."
            ),
        },
    ]

    last_table_rows: Optional[List[Dict[str, Any]]] = None
    last_chart: Optional[Dict[str, Any]] = None
    consecutive_failures = 0

    for _ in range(settings.agent_max_iterations):
        try:
            resp = _chat(messages=state.messages, tools=TOOL_SPECS)
        except Exception as e:  # noqa: BLE001
            state.error = f"LLM call failed: {e}"
            state.success = False
            return state

        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        msg_dict: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]
        state.messages.append(msg_dict)

        if not tool_calls:
            state.final_answer = (msg.content or "").strip()
            state.steps.append({
                "step": len(state.steps) + 1,
                "role": "executor",
                "output": state.final_answer,
            })
            state.table = last_table_rows
            state.chart = last_chart
            return state

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as e:
                args = {}
                logger.warning("Bad JSON args for {}: {}", name, e)

            output = _dispatch_tool(state, name, args)
            _record_tool_step(state, name, args, output)

            if not output.get("success"):
                consecutive_failures += 1
                _mark_step_failed(state, name)
            else:
                consecutive_failures = 0
                _mark_step_done(state, name)
                if name == "run_sql" and output.get("rows"):
                    last_table_rows = output["rows"]
                elif name == "run_python":
                    rp = output.get("result_preview")
                    if isinstance(rp, dict) and isinstance(rp.get("rows"), list):
                        last_table_rows = rp["rows"]
                elif name == "generate_plot":
                    last_chart = {
                        "chart_type": output.get("chart_type"),
                        "title": output.get("title"),
                        "x": output.get("x"),
                        "y": output.get("y"),
                        "data": output.get("data") or [],
                    }

            state.messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": json.dumps(_trim_for_log(output))[:8000],
            })

            if consecutive_failures > settings.agent_max_fix_attempts:
                state.error = (
                    f"Aborted after {consecutive_failures} consecutive tool failures."
                )
                state.success = False
                state.final_answer = (
                    "I attempted to answer but my tools kept failing. "
                    "Please refine the question or check the dataset schema."
                )
                state.table = last_table_rows
                state.chart = last_chart
                return state

    state.final_answer = (
        "I reached the maximum number of reasoning steps without producing a final "
        "answer. Try simplifying the question or breaking it into parts."
    )
    state.success = False
    state.error = "max_iterations_reached"
    state.table = last_table_rows
    state.chart = last_chart
    return state


# ---------------- critic ----------------


def critic_node(state: AgentState) -> AgentState:
    """Optional QA pass. Approves or rewrites the answer."""
    if not state.success or not state.final_answer:
        return state

    trace_summary = json.dumps([
        {k: v for k, v in s.items() if k != "input"} for s in state.steps[-6:]
    ], default=str)[:6000]

    user_prompt = (
        f"User question: {state.question}\n\n"
        f"Recent tool trace (truncated):\n{trace_summary}\n\n"
        f"Proposed final answer:\n{state.final_answer}\n\n"
        "Reply with the JSON verdict object now."
    )

    try:
        resp = _chat(
            messages=[
                {"role": "system", "content": CRITIC_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        verdict = _parse_json_loose(resp.choices[0].message.content or "") or {}
    except Exception as e:  # noqa: BLE001
        logger.warning("Critic failed (non-fatal): {}", e)
        return state

    if not verdict:
        return state

    state.critic_verdict = verdict
    state.steps.append({
        "step": len(state.steps) + 1,
        "role": "critic",
        "output": verdict,
    })
    if not verdict.get("approved", True) and verdict.get("improved_answer"):
        logger.info("Critic rewrote answer")
        state.final_answer = str(verdict["improved_answer"])
    return state


# ---------------- graph wiring ----------------


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("plan", planner_node)
    g.add_node("execute", executor_node)
    g.add_node("critique", critic_node)
    g.set_entry_point("plan")
    g.add_edge("plan", "execute")
    g.add_edge("execute", "critique")
    g.add_edge("critique", END)
    return g.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
