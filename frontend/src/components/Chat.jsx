import React, { useEffect, useRef, useState } from "react";
import DataTable from "./DataTable";
import Chart from "./Chart";
import AgentTrace from "./AgentTrace";

function Bubble({ role, children }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-md border ${
          isUser
            ? "bg-accent-500 text-white border-accent-400/40"
            : "bg-ink-700/60 text-slate-100 border-white/5"
        }`}
      >
        {children}
      </div>
    </div>
  );
}

export default function Chat({
  activeDataset,
  messages,
  onAsk,
  isLoading,
}) {
  const [input, setInput] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  function submit(e) {
    e.preventDefault();
    const v = input.trim();
    if (!v || isLoading) return;
    onAsk(v);
    setInput("");
  }

  const placeholder = activeDataset
    ? `Ask about ${activeDataset.name}... e.g. "Top 5 customers by revenue last month"`
    : "Upload a dataset to start asking questions";

  return (
    <div className="card flex flex-col h-full min-h-0">
      <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between">
        <div>
          <div className="font-semibold text-sm">Conversation</div>
          <div className="text-xs text-slate-400">
            {activeDataset
              ? `Active: ${activeDataset.name} (${activeDataset.row_count.toLocaleString()} rows × ${activeDataset.column_count} cols)`
              : "No dataset selected"}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.length === 0 && !isLoading && (
          <div className="text-center text-sm text-slate-400 py-12">
            <div className="text-4xl mb-2">🪄</div>
            Ask anything about your data. The agent will plan, run SQL or
            pandas, validate the result, and explain the insight.
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className="space-y-3">
            <Bubble role={m.role}>
              {m.role === "assistant" && m.error ? (
                <div className="text-red-300 text-xs">
                  <strong>Error:</strong> {m.error}
                </div>
              ) : null}
              <div className="whitespace-pre-wrap">{m.content}</div>
            </Bubble>

            {m.role === "assistant" && (m.table?.length || m.chart) && (
              <div className="space-y-3">
                {m.chart && <Chart spec={m.chart} />}
                {m.table?.length ? <DataTable rows={m.table} /> : null}
              </div>
            )}

            {m.role === "assistant" && (m.plan || m.steps?.length) && (
              <AgentTrace
                plan={m.plan}
                planSteps={m.plan_steps}
                steps={m.steps}
                repairs={m.repairs || 0}
              />
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-3 text-xs text-slate-400">
            <div className="flex gap-1">
              <span className="h-2 w-2 rounded-full bg-accent-500 animate-bounce [animation-delay:-0.2s]" />
              <span className="h-2 w-2 rounded-full bg-accent-500 animate-bounce [animation-delay:-0.1s]" />
              <span className="h-2 w-2 rounded-full bg-accent-500 animate-bounce" />
            </div>
            <span>Planning, running tools, and validating...</span>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <form
        onSubmit={submit}
        className="border-t border-white/5 p-4 flex items-end gap-2"
      >
        <textarea
          rows={2}
          className="input resize-none"
          placeholder={placeholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit(e);
            }
          }}
          disabled={isLoading}
        />
        <button
          type="submit"
          className="btn-primary h-[60px] px-5"
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? "Thinking..." : "Ask"}
        </button>
      </form>
    </div>
  );
}
