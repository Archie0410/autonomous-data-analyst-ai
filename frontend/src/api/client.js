import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE || "/api";

export const api = axios.create({
  baseURL,
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

export async function uploadDataset(file, name) {
  const fd = new FormData();
  fd.append("file", file);
  if (name) fd.append("name", name);
  const { data } = await api.post("/datasets/upload", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function listDatasets() {
  const { data } = await api.get("/datasets");
  return data;
}

export async function getDataset(id) {
  const { data } = await api.get(`/datasets/${id}`);
  return data;
}

export async function askQuery({ question, dataset_id, session_id }) {
  const { data } = await api.post("/query", {
    question,
    dataset_id,
    session_id,
  });
  return data;
}

export async function listHistory(session_id) {
  const params = session_id ? { session_id } : {};
  const { data } = await api.get("/history", { params });
  return data;
}
