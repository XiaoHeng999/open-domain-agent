"""Semantic knowledge-base interface — ABC and in-memory stub."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SemanticKB(ABC):
    """Abstract interface for a semantic knowledge base.

    Concrete implementations may use vector databases, graph stores, etc.
    """

    @abstractmethod
    async def write(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        """Write a document / fact to the knowledge base."""
        ...

    @abstractmethod
    async def query(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Query the knowledge base and return the top-K matching entries."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete an entry by key. Returns True if the entry existed."""
        ...


class InMemorySemanticKB(SemanticKB):
    """Stub in-memory semantic KB that returns empty results for queries.

    Useful for testing and as a placeholder until a real vector backend
    is wired in.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def write(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        self._store[key] = {
            "key": key,
            "value": value,
            "metadata": metadata or {},
        }

    async def query(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        # Stub: no semantic matching, return empty list
        return []

    async def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False
