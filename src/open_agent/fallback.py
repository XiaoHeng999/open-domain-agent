"""Fallback and degradation mechanism — FallbackChain + degradation strategies."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

logger = logging.getLogger("open_agent")

T = TypeVar("T")


@dataclass
class FallbackResult:
    """Result of a fallback chain execution."""

    success: bool
    value: Any = None
    error: Exception | None = None
    provider_used: str | None = None
    attempts: int = 0


class FallbackChain:
    """Execute a chain of callables with fallback — first success wins."""

    def __init__(self, providers: list[tuple[str, Callable[..., Any]]] | None = None) -> None:
        self._providers: list[tuple[str, Callable[..., Any]]] = providers or []
        self._failure_counts: dict[str, int] = {}
        self._max_consecutive_failures: int = 3

    def add(self, name: str, provider: Callable[..., Any]) -> "FallbackChain":
        self._providers.append((name, provider))
        return self

    async def execute(self, **kwargs: Any) -> FallbackResult:
        """Try each provider in order. First success wins."""
        last_error: Exception | None = None
        attempts = 0

        for name, provider in self._providers:
            if self._failure_counts.get(name, 0) >= self._max_consecutive_failures:
                logger.warning(f"Skipping degraded provider: {name}")
                continue

            attempts += 1
            try:
                result = provider(**kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                self._failure_counts[name] = 0
                return FallbackResult(
                    success=True,
                    value=result,
                    provider_used=name,
                    attempts=attempts,
                )
            except Exception as e:
                self._failure_counts[name] = self._failure_counts.get(name, 0) + 1
                last_error = e
                logger.warning(f"Provider {name} failed: {e}")

        return FallbackResult(
            success=False,
            error=last_error,
            attempts=attempts,
        )

    def reset(self, name: str | None = None) -> None:
        """Reset failure counts for a provider or all."""
        if name:
            self._failure_counts.pop(name, None)
        else:
            self._failure_counts.clear()

    @property
    def degraded(self) -> list[str]:
        """List of currently degraded (max-failures-hit) providers."""
        return [
            name
            for name, count in self._failure_counts.items()
            if count >= self._max_consecutive_failures
        ]
