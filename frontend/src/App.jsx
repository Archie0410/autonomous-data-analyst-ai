import React, { useEffect, useMemo, useState } from "react";
import Header from "./components/Header";
import DatasetUpload from "./components/DatasetUpload";
import DatasetList from "./components/DatasetList";
import DatasetPreview from "./components/DatasetPreview";
import Chat from "./components/Chat";
import { useSession } from "./hooks/useSession";
import {
  askQuery,
  getDataset,
  listDatasets,
} from "./api/client";

export default function App() {
  const { sessionId, reset: resetSession } = useSession();
  const [datasets, setDatasets] = useState([]);
  const [activeDatasetId, setActiveDatasetId] = useState(null);
  const [activeDataset, setActiveDataset] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [bootError, setBootError] = useState(null);

  useEffect(() => {
    refreshDatasets();
  }, []);

  useEffect(() => {
    if (!activeDatasetId) {
      setActiveDataset(null);
      return;
    }
    getDataset(activeDatasetId)
      .then(setActiveDataset)
      .catch((e) => setBootError(e.message));
  }, [activeDatasetId]);

  async function refreshDatasets() {
    try {
      const list = await listDatasets();
      setDatasets(list);
      if (list.length && !activeDatasetId) setActiveDatasetId(list[0].id);
    } catch (e) {
      setBootError(
        "Could not reach backend. Is the FastAPI server running on port 8000?"
      );
    }
  }

  function handleUploaded(detail) {
    setDatasets((prev) => {
      const without = prev.filter((d) => d.id !== detail.id);
      return [
        {
          id: detail.id,
          name: detail.name,
          table_name: detail.table_name,
          original_filename: detail.original_filename,
          row_count: detail.row_count,
          column_count: detail.column_count,
          created_at: detail.created_at,
        },
        ...without,
      ];
    });
    setActiveDatasetId(detail.id);
    setActiveDataset(detail);
  }

  async function handleAsk(question) {
    setMessages((m) => [...m, { role: "user", content: question }]);
    setIsLoading(true);
    try {
      const res = await askQuery({
        question,
        dataset_id: activeDatasetId,
        session_id: sessionId,
      });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.answer || "(no answer)",
          plan: res.plan,
          plan_steps: res.plan_steps,
          steps: res.steps,
          table: res.table,
          chart: res.chart,
          repairs: res.repairs || 0,
          memory: res.memory,
          error: res.error && !res.success ? res.error : null,
        },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Sorry, the request failed.",
          error: e?.response?.data?.detail || e.message,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleResetSession() {
    resetSession();
    setMessages([]);
  }

  const sortedDatasets = useMemo(
    () => [...datasets].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
    [datasets]
  );

  return (
    <div className="min-h-screen flex flex-col">
      <Header sessionId={sessionId} onResetSession={handleResetSession} />

      <main className="max-w-[1400px] w-full mx-auto px-6 py-6 flex-1 grid grid-cols-12 gap-6 min-h-0">
        <aside className="col-span-12 lg:col-span-4 xl:col-span-3 space-y-5 min-h-0 overflow-y-auto">
          <DatasetUpload onUploaded={handleUploaded} />
          <DatasetList
            datasets={sortedDatasets}
            activeId={activeDatasetId}
            onSelect={(d) => setActiveDatasetId(d.id)}
          />
          {activeDataset && <DatasetPreview dataset={activeDataset} />}

          {bootError && (
            <div className="card p-4 text-xs text-amber-200 bg-amber-500/10 border-amber-500/30">
              {bootError}
            </div>
          )}
        </aside>

        <section className="col-span-12 lg:col-span-8 xl:col-span-9 min-h-[70vh]">
          <Chat
            activeDataset={activeDataset}
            messages={messages}
            onAsk={handleAsk}
            isLoading={isLoading}
          />
        </section>
      </main>

      <footer className="text-center text-[11px] text-slate-500 py-4">
        Built with FastAPI · LangGraph · OpenAI · React · Tailwind · Plotly
      </footer>
    </div>
  );
}
