"""Cancellation token for graceful task cancellation."""
from __future__ import annotations

import asyncio


class CancellationToken:
    """Wraps an asyncio.Event for cooperative cancellation.

    Checked at iteration boundaries in the ReAct loop.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()
