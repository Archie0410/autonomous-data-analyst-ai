import React, { useRef, useState } from "react";
import { uploadDataset } from "../api/client";

export default function DatasetUpload({ onUploaded }) {
  const inputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [drag, setDrag] = useState(false);

  async function handleFile(file) {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    try {
      const detail = await uploadDataset(file, file.name.replace(/\.[^.]+$/, ""));
      onUploaded?.(detail);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div
      className={`card p-5 transition ${
        drag ? "ring-2 ring-accent-500/60" : ""
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        handleFile(e.dataTransfer.files?.[0]);
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">Upload dataset</h3>
        <span className="pill">CSV / TSV</span>
      </div>

      <label
        className="block border border-dashed border-white/10 rounded-xl px-4 py-8 text-center cursor-pointer hover:bg-white/5 transition"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.tsv,.txt"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        <div className="text-sm text-slate-300">
          {isUploading ? (
            <span className="inline-flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-accent-500 animate-pulse" />
              Uploading & ingesting...
            </span>
          ) : (
            <>
              <span className="text-accent-300 font-medium">Click to upload</span> or
              drop a CSV here
            </>
          )}
        </div>
        <div className="text-xs text-slate-500 mt-1">
          Stored in SQLite with auto-detected schema
        </div>
      </label>

      {error && (
        <div className="mt-3 text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
          {String(error)}
        </div>
      )}
    </div>
  );
}
