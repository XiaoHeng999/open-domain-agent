"""Episodic memory — stores task-level summaries for future retrieval."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import MemoryManager
from open_agent.config import MemoryConfig


@dataclass
class EpisodicSummary:
    """Summary of a completed task / episode."""

    intent: str
    steps_summary: str
    result: str
    user_feedback: str = ""
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


class EpisodicStore(MemoryManager):
    """In-memory dict-backed store for episodic summaries.

    Write triggers modelled as distinct methods:
      * ``write_after_task`` — called after a task finishes
      * ``write_after_reflection`` — called after a self-reflection step
      * ``write_after_checkpoint`` — called at checkpoint boundaries
    """

    def __init__(self, config: MemoryConfig | None = None) -> None:
        super().__init__()
        self._config = config or MemoryConfig()
        self._store: dict[str, EpisodicSummary] = {}

    # ------------------------------------------------------------------
    # MemoryManager ABC
    # ------------------------------------------------------------------

    async def read(self, query: str = "", **kwargs: Any) -> list[EpisodicSummary]:
        """Retrieve episodic summaries matching *query*."""
        top_k: int = kwargs.get("top_k", 5)
        return await self.retrieve_episodic(query, top_k=top_k)

    async def write(self, data: Any, **kwargs: Any) -> None:
        """Write an episodic summary. *data* may be an EpisodicSummary or dict."""
        if isinstance(data, EpisodicSummary):
            await self.write_episodic_summary(data)
        elif isinstance(data, dict):
            summary = EpisodicSummary(
                intent=data.get("intent", ""),
                steps_summary=data.get("steps_summary", ""),
                result=data.get("result", ""),
                user_feedback=data.get("user_feedback", ""),
            )
            await self.write_episodic_summary(summary)
        else:
            raise TypeError(f"Cannot write episodic data of type {type(data)}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def write_episodic_summary(self, summary: EpisodicSummary) -> None:
        """Store a summary."""
        self._store[summary.id] = summary

    async def retrieve_episodic(
        self, query: str, top_k: int = 5
    ) -> list[EpisodicSummary]:
        """Simple keyword-based retrieval. Returns the *top_k* best matches."""
        if not query:
            # Return most recent
            all_summaries = sorted(
                self._store.values(), key=lambda s: s.timestamp, reverse=True
            )
            return all_summaries[:top_k]

        query_lower = query.lower()
        scored: list[tuple[float, EpisodicSummary]] = []
        for summary in self._store.values():
            score = self._relevance_score(query_lower, summary)
            scored.append((score, summary))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [s for _, s in scored[:top_k]]

    # ------------------------------------------------------------------
    # Write trigger helpers
    # ------------------------------------------------------------------

    async def write_after_task(
        self,
        intent: str,
        steps_summary: str,
        result: str,
        user_feedback: str = "",
    ) -> EpisodicSummary:
        """Record a summary after a task completes."""
        summary = EpisodicSummary(
            intent=intent,
            steps_summary=steps_summary,
            result=result,
            user_feedback=user_feedback,
        )
        await self.write_episodic_summary(summary)
        return summary

    async def write_after_reflection(
        self,
        intent: str,
        steps_summary: str,
        result: str,
        user_feedback: str = "",
    ) -> EpisodicSummary:
        """Record a summary after a self-reflection step."""
        return await self.write_after_task(
            intent, steps_summary, result, user_feedback
        )

    async def write_after_checkpoint(
        self,
        intent: str,
        steps_summary: str,
        result: str,
        user_feedback: str = "",
    ) -> EpisodicSummary:
        """Record a summary at a checkpoint boundary."""
        return await self.write_after_task(
            intent, steps_summary, result, user_feedback
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _relevance_score(query: str, summary: EpisodicSummary) -> float:
        """Very simple keyword-overlap relevance."""
        text = f"{summary.intent} {summary.steps_summary} {summary.result}".lower()
        words = query.split()
        hits = sum(1 for w in words if w in text)
        return hits / max(len(words), 1)
