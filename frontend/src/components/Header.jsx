import React from "react";

export default function Header({ sessionId, onResetSession }) {
  return (
    <header className="sticky top-0 z-20 bg-ink-900/70 backdrop-blur border-b border-white/5">
      <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-accent-500 to-indigo-500 grid place-items-center shadow-glow">
            <span className="font-bold">A</span>
          </div>
          <div>
            <div className="font-semibold tracking-tight">Autonomous AI Data Analyst</div>
            <div className="text-xs text-slate-400">
              Plan → Execute → Critique
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="pill font-mono">session: {sessionId.slice(0, 8)}</span>
          <button className="btn-ghost !py-1.5 !px-3" onClick={onResetSession}>
            New session
          </button>
        </div>
      </div>
    </header>
  );
}
