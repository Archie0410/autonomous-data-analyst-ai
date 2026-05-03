"""
FAISS-backed vector store for dataset schema retrieval.

When a user asks a question, we embed the question and retrieve the most relevant
dataset schemas. This lets the planner pick the right table when several datasets
have been uploaded.

Falls back gracefully (no-op) if no OpenAI key is configured, so tests can run.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.config import settings
from app.utils.logger import logger

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover
    faiss = None  # FAISS becomes optional


class _SchemaVectorStore:
    """Thin wrapper over FAISS that maps dataset_id -> embedded schema text."""

    def __init__(self, persist_dir: str) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.persist_dir / "schemas.faiss"
        self.meta_path = self.persist_dir / "schemas_meta.json"
        self._lock = threading.Lock()
        self._dim: Optional[int] = None
        self._index = None
        self._meta: List[Dict] = []  # parallel to vectors: {dataset_id, text}
        self._load()

    # ---------- persistence ----------

    def _load(self) -> None:
        if not faiss:
            logger.warning("FAISS not available - vector store disabled")
            return
        if self.index_path.exists() and self.meta_path.exists():
            try:
                self._index = faiss.read_index(str(self.index_path))
                self._dim = self._index.d
                self._meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
                logger.info("Loaded vector store: {} entries", len(self._meta))
            except Exception as e:  # noqa: BLE001
                logger.warning("Vector store load failed, starting fresh: {}", e)
                self._index = None
                self._meta = []

    def _save(self) -> None:
        if not self._index:
            return
        faiss.write_index(self._index, str(self.index_path))
        self.meta_path.write_text(json.dumps(self._meta), encoding="utf-8")

    # ---------- embeddings ----------

    def _embed(self, texts: List[str]) -> Optional[np.ndarray]:
        if not settings.openai_api_key:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.embeddings.create(
                model=settings.openai_embedding_model, input=texts
            )
            arr = np.array([d.embedding for d in resp.data], dtype="float32")
            return arr
        except Exception as e:  # noqa: BLE001
            logger.warning("Embedding failed (non-fatal): {}", e)
            return None

    # ---------- public API ----------

    def add_dataset_schema(self, dataset_id: int, schema_text: str) -> None:
        if not faiss:
            return
        with self._lock:
            embeds = self._embed([schema_text])
            if embeds is None:
                return
            if self._index is None:
                self._dim = embeds.shape[1]
                self._index = faiss.IndexFlatIP(self._dim)
            faiss.normalize_L2(embeds)
            self._index.add(embeds)
            self._meta.append({"dataset_id": dataset_id, "text": schema_text})
            self._save()
            logger.info("Indexed schema for dataset_id={}", dataset_id)

    def search(self, query: str, top_k: int = 3) -> List[Tuple[int, str, float]]:
        """Return [(dataset_id, schema_text, score), ...]."""
        if not faiss or self._index is None or not self._meta:
            return []
        embeds = self._embed([query])
        if embeds is None:
            return []
        faiss.normalize_L2(embeds)
        scores, idx = self._index.search(embeds, min(top_k, len(self._meta)))
        out: List[Tuple[int, str, float]] = []
        for i, s in zip(idx[0], scores[0]):
            if i < 0 or i >= len(self._meta):
                continue
            m = self._meta[int(i)]
            out.append((int(m["dataset_id"]), str(m["text"]), float(s)))
        return out


vector_store = _SchemaVectorStore(settings.vector_store_dir)
