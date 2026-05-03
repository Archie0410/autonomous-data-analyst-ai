import React from "react";

function formatCell(v) {
  if (v === null || v === undefined) return <span className="text-slate-500">—</span>;
  if (typeof v === "number") {
    if (Number.isInteger(v)) return v.toLocaleString();
    return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v);
}

export default function DataTable({ rows, maxHeight = 360 }) {
  if (!rows?.length) {
    return (
      <div className="text-sm text-slate-400 italic">No rows to display.</div>
    );
  }
  const cols = Object.keys(rows[0]);
  return (
    <div
      className="rounded-xl border border-white/5 overflow-auto"
      style={{ maxHeight }}
    >
      <table className="w-full text-xs">
        <thead className="bg-ink-700/70 sticky top-0">
          <tr>
            {cols.map((c) => (
              <th
                key={c}
                className="text-left font-semibold uppercase tracking-wide text-[10px] text-slate-400 px-3 py-2 border-b border-white/5"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className={i % 2 ? "bg-white/0" : "bg-white/[0.02]"}
            >
              {cols.map((c) => (
                <td
                  key={c}
                  className="px-3 py-1.5 border-b border-white/5 align-top"
                >
                  {formatCell(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
