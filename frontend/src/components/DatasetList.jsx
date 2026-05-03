import React from "react";

export default function DatasetList({ datasets, activeId, onSelect }) {
  if (!datasets?.length) {
    return (
      <div className="card p-5">
        <h3 className="font-semibold mb-2">Datasets</h3>
        <p className="text-sm text-slate-400">No datasets yet. Upload a CSV to begin.</p>
      </div>
    );
  }
  return (
    <div className="card p-5">
      <h3 className="font-semibold mb-3">Datasets</h3>
      <ul className="space-y-1.5">
        {datasets.map((d) => {
          const active = activeId === d.id;
          return (
            <li key={d.id}>
              <button
                onClick={() => onSelect?.(d)}
                className={`w-full text-left rounded-xl px-3 py-2 border transition ${
                  active
                    ? "border-accent-500/60 bg-accent-500/10"
                    : "border-white/5 bg-white/0 hover:bg-white/5"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium truncate">{d.name}</span>
                  <span className="pill">{d.row_count} rows</span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5 font-mono truncate">
                  {d.table_name}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
