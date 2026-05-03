import React from "react";
import DataTable from "./DataTable";

export default function DatasetPreview({ dataset }) {
  if (!dataset) return null;
  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold">{dataset.name}</h3>
          <div className="text-xs text-slate-400 font-mono">
            {dataset.table_name}
          </div>
        </div>
        <div className="text-right text-xs text-slate-400">
          <div>{dataset.row_count.toLocaleString()} rows</div>
          <div>{dataset.column_count} columns</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {dataset.columns?.slice(0, 12).map((c) => (
          <span
            key={c.name}
            className="pill font-mono"
            title={`${c.name} (${c.dtype})`}
          >
            {c.name}
            <span className="text-slate-500"> · {c.dtype}</span>
          </span>
        ))}
        {dataset.columns?.length > 12 && (
          <span className="pill">+{dataset.columns.length - 12} more</span>
        )}
      </div>

      <DataTable rows={dataset.preview || []} maxHeight={220} />
    </div>
  );
}
