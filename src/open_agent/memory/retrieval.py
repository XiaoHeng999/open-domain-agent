"""Retrieval memory — vector-backed episodic + semantic long-term memory."""

from __future__ import annotations

import json
import logging
import time as _time
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from open_agent.base import MemoryManager
from open_agent.config import MemoryConfig
from open_agent.memory.token_utils import estimate_tokens
from open_agent.trace import SpanKind

logger = logging.getLogger("open_agent.memory.retrieval")


class VectorStore:
    """Numpy-based vector store with cosine similarity search."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim
        self._ids: list[str] = []
        self._vectors: np.ndarray = np.empty((0, dim), dtype=np.float32)
        self._texts: list[str] = []
        self._metadatas: list[dict[str, Any]] = []

    def write(self, id: str, embedding: np.ndarray, text: str, metadata: dict[str, Any]) -> None:
        """Add or update a vector record."""
        vec = embedding.astype(np.float32).reshape(1, -1)
        if id in self._ids:
            idx = self._ids.index(id)
            self._vectors[idx] = vec[0]
            self._texts[idx] = text
            self._metadatas[idx] = metadata
        else:
            self._ids.append(id)
            self._vectors = np.vstack([self._vectors, vec]) if self._vectors.size else vec
            self._texts.append(text)
            self._metadatas.append(metadata)

    def query(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[str, str, dict[str, Any], float]]:
        """Return top_k results as (id, text, metadata, score) tuples."""
        if len(self._ids) == 0:
            return []

        q = query_embedding.astype(np.float32).reshape(1, -1)
        # Normalize for cosine similarity
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normed = self._vectors / norms
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm
        scores = (normed @ q.T).flatten()

        # Apply metadata filter
        candidates = list(range(len(self._ids)))
        if metadata_filter:
            candidates = [
                i for i in candidates
                if all(self._metadatas[i].get(k) == v for k, v in metadata_filter.items())
            ]

        scored = [(i, scores[i]) for i in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        return [
            (self._ids[i], self._texts[i], self._metadatas[i], float(scores[i]))
            for i, _ in top
        ]

    def delete(self, id: str) -> bool:
        """Delete a record by id."""
        if id not in self._ids:
            return False
        idx = self._ids.index(id)
        self._ids.pop(idx)
        self._texts.pop(idx)
        self._metadatas.pop(idx)
        self._vectors = np.delete(self._vectors, idx, axis=0)
        return True

    def save_to_disk(self, directory: Path) -> None:
        """Persist vectors and metadata to disk."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        if self._vectors.size:
            np.savez_compressed(directory / "vectors.npz", vectors=self._vectors, ids=self._ids)
        with open(directory / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(self._metadatas, f, ensure_ascii=False, indent=2)
        with open(directory / "texts.json", "w", encoding="utf-8") as f:
            json.dump(self._texts, f, ensure_ascii=False, indent=2)

    def load_from_disk(self, directory: Path) -> None:
        """Load vectors and metadata from disk."""
        directory = Path(directory)
        npz_path = directory / "vectors.npz"
        if npz_path.exists():
            data = np.load(npz_path, allow_pickle=False)
            self._vectors = data["vectors"]
            self._ids = list(data["ids"])
            self._dim = self._vectors.shape[1] if self._vectors.size else self._dim
        meta_path = directory / "metadata.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                self._metadatas = json.load(f)
        texts_path = directory / "texts.json"
        if texts_path.exists():
            with open(texts_path, encoding="utf-8") as f:
                self._texts = json.load(f)


class EmbeddingService:
    """Generate embeddings — sentence-transformers with TF-IDF fallback."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model = None
        self._tfidf = None
        self._dim = 384
        self._model_name = model_name
        self._try_load_transformer(model_name)

    def _try_load_transformer(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
            logger.info("Loaded embedding model: %s (dim=%d)", model_name, self._dim)
        except ImportError:
            logger.info("sentence-transformers not available, using TF-IDF fallback")
            self._model = None
            self._dim = 256

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        if self._model is not None:
            return self._model.encode(text, normalize_embeddings=True)
        # TF-IDF fallback: simple character n-gram hashing
        return self._tfidf_embed(text)

    def _tfidf_embed(self, text: str) -> np.ndarray:
        """Fallback embedding using character n-gram hashing."""
        vec = np.zeros(self._dim, dtype=np.float32)
        words = text.lower().split()
        for word in words:
            for i in range(min(len(word), 4)):
                idx = hash(word[:i+1]) % self._dim
                vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    @property
    def dim(self) -> int:
        return self._dim


class RetrievalMemory(MemoryManager):
    """Long-term memory with vector retrieval.

    Two sub-layers:
    - Episodic: task experiences (intent, steps, result, success)
    - Semantic: abstract knowledge, rules, patterns
    """

    def __init__(self, config: MemoryConfig | None = None) -> None:
        super().__init__()
        self._config = config or MemoryConfig()
        self._embedding = EmbeddingService(self._config.retrieval_embedding_model)
        self._store = VectorStore(dim=self._embedding.dim)
        self._store_dir = Path(self._config.retrieval_store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._load_if_exists()

    def _load_if_exists(self) -> None:
        if (self._store_dir / "vectors.npz").exists():
            self._store.load_from_disk(self._store_dir)

    # ------------------------------------------------------------------
    # MemoryManager ABC
    # ------------------------------------------------------------------

    async def read(self, query: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        top_k = kwargs.get("top_k", self._config.retrieval_top_k)
        layer = kwargs.get("layer")
        return await self.query(query, top_k=top_k, layer=layer)

    async def write(self, data: Any, **kwargs: Any) -> None:
        if isinstance(data, dict):
            layer = data.get("layer", "episodic")
            if layer == "episodic":
                await self.write_episodic(**data)
            elif layer == "semantic":
                await self.write_semantic(**data)

    # ------------------------------------------------------------------
    # Episodic sub-layer
    # ------------------------------------------------------------------

    async def write_episodic(
        self,
        intent: str = "",
        steps_summary: str = "",
        result: str = "",
        success: bool = True,
        task_type: str = "",
        **kwargs: Any,
    ) -> None:
        """Write an episodic record."""
        span = _start_retrieval_span(self, "episodic_write")
        text = f"Intent: {intent}. Steps: {steps_summary}. Result: {result}"
        metadata = {
            "layer": "episodic",
            "task_type": task_type,
            "success": success,
            "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        embedding = self._embedding.embed(text)
        record_id = uuid.uuid4().hex[:12]
        self._store.write(record_id, embedding, text, metadata)
        self._store.save_to_disk(self._store_dir)
        _finish_span(span)

    # ------------------------------------------------------------------
    # Semantic sub-layer
    # ------------------------------------------------------------------

    async def write_semantic(
        self,
        text: str = "",
        category: str = "general",
        confidence: float = 0.5,
        **kwargs: Any,
    ) -> None:
        """Write a semantic knowledge record."""
        metadata = {
            "layer": "semantic",
            "category": category,
            "confidence": confidence,
        }
        embedding = self._embedding.embed(text)
        record_id = uuid.uuid4().hex[:12]
        self._store.write(record_id, embedding, text, metadata)
        self._store.save_to_disk(self._store_dir)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(
        self,
        query_text: str,
        top_k: int = 5,
        layer: str | None = None,
        max_inject_tokens: int = 0,
    ) -> list[dict[str, Any]]:
        """Query retrieval memory with embedding search.

        Returns results above score threshold, truncated to max_inject_tokens.
        """
        if not query_text:
            return []

        span = _start_retrieval_span(self, "retrieval_query", top_k=top_k)
        top_k = min(top_k, self._config.retrieval_top_k)
        if max_inject_tokens <= 0:
            max_inject_tokens = self._config.retrieval_max_inject_tokens

        q_embedding = self._embedding.embed(query_text)
        metadata_filter = {"layer": layer} if layer else None
        results = self._store.query(q_embedding, top_k=top_k, metadata_filter=metadata_filter)

        threshold = self._config.retrieval_score_threshold
        filtered = []
        total_tokens = 0
        for id_, text, meta, score in results:
            if score <= threshold:
                continue
            tokens = estimate_tokens(text)
            if total_tokens + tokens > max_inject_tokens:
                break
            filtered.append({
                "id": id_,
                "text": text,
                "metadata": meta,
                "score": score,
            })
            total_tokens += tokens

        if span:
            span.set_attribute("results_count", len(filtered))
        _finish_span(span)
        return filtered


def _start_retrieval_span(obj, operation: str, **attrs):
    tm = getattr(obj, "_trace_manager", None)
    tid = getattr(obj, "_current_trace_id", None)
    if tm is None or tid is None:
        return None
    trace = tm.get_trace(tid)
    if trace is None:
        return None
    span = trace.create_span(operation, kind=SpanKind.MEMORY_OP)
    span.set_attribute("operation", operation)
    for k, v in attrs.items():
        span.set_attribute(k, v)
    return span


def _finish_span(span):
    if span is not None:
        span.finish()
