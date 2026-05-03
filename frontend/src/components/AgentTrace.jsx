import React, { useState } from "react";

function StepBadge({ role, tool }) {
  const colors = {
    planner: "bg-amber-500/20 text-amber-200 border-amber-500/30",
    executor: "bg-emerald-500/20 text-emerald-200 border-emerald-500/30",
    critic: "bg-pink-500/20 text-pink-200 border-pink-500/30",
    tool: "bg-sky-500/20 text-sky-200 border-sky-500/30",
    repair: "bg-orange-500/20 text-orange-200 border-orange-500/30",
  };
  return (
    <span
      className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-md border ${
        colors[role] || colors.tool
      }`}
    >
      {tool ? `${role} · ${tool}` : role}
    </span>
  );
}

function StatusDot({ status }) {
  const map = {
    pending: "bg-slate-500/40",
    done: "bg-emerald-400",
    failed: "bg-red-400",
    skipped: "bg-amber-400",
  };
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${map[status] || map.pending}`}
      title={status}
    />
  );
}

function pretty(val) {
  if (val === null || val === undefined) return "";
  if (typeof val === "string") return val;
  try {
    return JSON.stringify(val, null, 2);
  } catch {
    return String(val);
  }
}

function StructuredPlan({ planSteps, plan }) {
  // Prefer the structured representation if available; fall back to raw text.
  if (!planSteps || planSteps.length === 0) {
    if (!plan) return null;
    return (
      <pre className="text-xs whitespace-pre-wrap font-mono text-slate-200">
        {plan}
      </pre>
    );
  }
  return (
    <ol className="space-y-1.5">
      {planSteps.map((s) => (
        <li key={s.id} className="flex items-start gap-2 text-xs">
          <span className="mt-1.5">
            <StatusDot status={s.status} />
          </span>
          <div>
            <div className="text-slate-200">
              <span className="text-slate-500 font-mono mr-1.5">{s.id}.</span>
              {s.intent}
              {s.tool && (
                <span className="ml-2 pill text-[10px] !py-0">{s.tool}</span>
              )}
            </div>
            {s.expected && (
              <div className="text-[11px] text-slate-500 mt-0.5">
                expected: {s.expected}
              </div>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

function RepairCard({ s }) {
  const inp = s.input || {};
  const out = s.output || {};
  return (
    <div className="rounded-xl bg-orange-500/5 border border-orange-500/20 p-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <StepBadge role="repair" tool={`attempt ${inp.attempt}`} />
          <span className="text-xs text-slate-500">step {s.step}</span>
        </div>
        <span
          className={`text-[10px] px-2 py-0.5 rounded border ${
            out.succeeded
              ? "text-emerald-200 bg-emerald-500/10 border-emerald-500/30"
              : "text-red-200 bg-red-500/10 border-red-500/30"
          }`}
        >
          {out.succeeded ? "fixed" : "still failing"}
        </span>
      </div>
      <div className="text-[11px] text-slate-400 mb-1">SQL error</div>
      <pre className="text-[11px] whitespace-pre-wrap font-mono text-red-200/90 mb-2">
        {inp.error}
      </pre>
      <details>
        <summary className="text-[11px] text-slate-400 cursor-pointer">
          failed query → repaired query
        </summary>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
          <pre className="text-[11px] font-mono whitespace-pre-wrap text-slate-300 bg-ink-700/40 rounded p-2">
            {inp.failed_sql}
          </pre>
          <pre className="text-[11px] font-mono whitespace-pre-wrap text-emerald-200 bg-ink-700/40 rounded p-2">
            {out.repaired_sql || "(no fix returned)"}
          </pre>
        </div>
        {out.explanation && (
          <div className="text-[11px] text-slate-400 mt-2 italic">
            {out.explanation}
          </div>
        )}
      </details>
    </div>
  );
}

function GenericStepCard({ s }) {
  return (
    <div className="rounded-xl bg-ink-700/40 border border-white/5 p-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <StepBadge role={s.role} tool={s.tool} />
          <span className="text-xs text-slate-500">step {s.step}</span>
        </div>
        {s.error && (
          <span className="text-[10px] text-red-300 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20">
            error
          </span>
        )}
      </div>

      {s.input !== undefined && s.input !== null && (
        <details className="mb-1">
          <summary className="text-[11px] text-slate-400 cursor-pointer">input</summary>
          <pre className="text-[11px] mt-1 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-slate-300">
            {pretty(s.input)}
          </pre>
        </details>
      )}

      {s.output !== undefined && s.output !== null && (
        <details>
          <summary className="text-[11px] text-slate-400 cursor-pointer">output</summary>
          <pre className="text-[11px] mt-1 max-h-56 overflow-auto whitespace-pre-wrap font-mono text-slate-300">
            {pretty(s.output)}
          </pre>
        </details>
      )}

      {s.error && (
        <pre className="text-[11px] mt-2 text-red-300 whitespace-pre-wrap font-mono">
          {s.error}
        </pre>
      )}
    </div>
  );
}

export default function AgentTrace({ plan, planSteps, steps, repairs }) {
  const [expanded, setExpanded] = useState(false);
  if (!plan && (!steps || steps.length === 0)) return null;

  const tail = expanded ? steps : steps?.slice(-4) || [];

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <span>Agent reasoning</span>
          {repairs > 0 && (
            <span className="pill text-[10px] !py-0 bg-orange-500/15 border-orange-500/30 text-orange-200">
              {repairs} SQL repair{repairs > 1 ? "s" : ""}
            </span>
          )}
        </div>
        {steps?.length > 4 && (
          <button
            className="text-xs text-accent-300 hover:text-accent-400"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Show last 4" : `Show all ${steps.length} steps`}
          </button>
        )}
      </div>

      {(plan || planSteps?.length) && (
        <div className="rounded-xl bg-ink-700/40 border border-white/5 p-3">
          <div className="flex items-center gap-2 mb-2">
            <StepBadge role="planner" />
            <span className="text-xs text-slate-400">multi-step plan</span>
          </div>
          <StructuredPlan planSteps={planSteps} plan={plan} />
        </div>
      )}

      {tail
        .filter((s) => s.role !== "planner")
        .map((s) =>
          s.role === "repair" ? (
            <RepairCard key={s.step} s={s} />
          ) : (
            <GenericStepCard key={s.step} s={s} />
          )
        )}
    </div>
  );
}
