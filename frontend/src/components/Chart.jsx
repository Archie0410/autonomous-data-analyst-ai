import React, { useMemo } from "react";
import Plot from "react-plotly.js";

const LAYOUT_BASE = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: "#cbd5e1", family: "Inter, sans-serif", size: 12 },
  margin: { l: 50, r: 20, t: 40, b: 50 },
  xaxis: { gridcolor: "rgba(255,255,255,0.08)", zerolinecolor: "rgba(255,255,255,0.08)" },
  yaxis: { gridcolor: "rgba(255,255,255,0.08)", zerolinecolor: "rgba(255,255,255,0.08)" },
  legend: { orientation: "h", y: -0.2 },
  colorway: ["#7c5cff", "#22d3ee", "#f472b6", "#facc15", "#34d399", "#f97316"],
};

const CONFIG = { displaylogo: false, responsive: true };

export default function Chart({ spec }) {
  const { traces, layout } = useMemo(() => buildPlot(spec), [spec]);
  if (!spec || !spec.data?.length) return null;

  return (
    <div className="rounded-xl border border-white/5 bg-ink-700/30 p-3">
      <Plot
        data={traces}
        layout={layout}
        config={CONFIG}
        style={{ width: "100%", height: "360px" }}
        useResizeHandler
      />
    </div>
  );
}

function buildPlot(spec) {
  if (!spec) return { traces: [], layout: LAYOUT_BASE };
  const rows = spec.data || [];
  const x = spec.x;
  const yCols = (spec.y && spec.y.length ? spec.y : inferYCols(rows, x)).filter(Boolean);
  const title = spec.title || "";

  const xs = rows.map((r) => r[x]);

  let traces = [];
  switch (spec.chart_type) {
    case "pie": {
      const valueCol = yCols[0];
      traces = [
        {
          type: "pie",
          labels: xs,
          values: rows.map((r) => Number(r[valueCol])),
          hole: 0.45,
          textinfo: "label+percent",
        },
      ];
      break;
    }
    case "scatter": {
      traces = yCols.map((yc) => ({
        type: "scatter",
        mode: "markers",
        name: yc,
        x: xs,
        y: rows.map((r) => Number(r[yc])),
        marker: { size: 9, opacity: 0.85 },
      }));
      break;
    }
    case "histogram": {
      const col = x || yCols[0];
      traces = [
        {
          type: "histogram",
          x: rows.map((r) => Number(r[col])),
          marker: { color: "#7c5cff" },
        },
      ];
      break;
    }
    case "line": {
      traces = yCols.map((yc) => ({
        type: "scatter",
        mode: "lines+markers",
        name: yc,
        x: xs,
        y: rows.map((r) => Number(r[yc])),
        line: { width: 2 },
      }));
      break;
    }
    case "table": {
      // Plotly tables are bulky; fall back to first numeric bar.
      traces = yCols.map((yc) => ({
        type: "bar",
        name: yc,
        x: xs,
        y: rows.map((r) => Number(r[yc])),
      }));
      break;
    }
    case "bar":
    default: {
      traces = yCols.map((yc) => ({
        type: "bar",
        name: yc,
        x: xs,
        y: rows.map((r) => Number(r[yc])),
      }));
    }
  }

  const layout = {
    ...LAYOUT_BASE,
    title: title ? { text: title, font: { size: 14 } } : undefined,
    barmode: traces.length > 1 ? "group" : undefined,
  };

  return { traces, layout };
}

function inferYCols(rows, x) {
  if (!rows.length) return [];
  const sample = rows[0];
  return Object.keys(sample).filter(
    (k) => k !== x && typeof sample[k] === "number"
  );
}
