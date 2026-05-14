"""HookManager — register and fire hooks with priority ordering."""

from __future__ import annotations

import logging
from typing import Any

from .types import HookCallback, HookEvent, HookResult

logger = logging.getLogger("open_agent.hooks")


class _HookEntry:
    """Internal bookkeeping for a registered hook."""

    __slots__ = ("callback", "priority", "registration_order")

    def __init__(
        self,
        callback: HookCallback,
        priority: int,
        registration_order: int,
    ) -> None:
        self.callback = callback
        self.priority = priority
        self.registration_order = registration_order


class HookManager:
    """Central registry for lifecycle hooks.

    Usage::

        mgr = HookManager()
        mgr.register(HookEvent.TOOL_BEFORE, my_check, priority=10)
        results = await mgr.fire(HookEvent.TOOL_BEFORE, {"tool_name": "exec"})
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._hooks: dict[HookEvent, list[_HookEntry]] = {
            event: [] for event in HookEvent
        }
        self._registration_counter = 0

    def register(
        self,
        event: HookEvent,
        callback: HookCallback,
        *,
        priority: int = 100,
    ) -> None:
        """Register *callback* for *event* with the given *priority*.

        Lower priority values execute first.  Same-priority callbacks
        execute in registration order.
        """
        entry = _HookEntry(callback, priority, self._registration_counter)
        self._registration_counter += 1
        self._hooks[event].append(entry)
        self._hooks[event].sort(key=lambda e: (e.priority, e.registration_order))

    async def fire(
        self,
        event: HookEvent,
        context: dict[str, Any],
    ) -> list[HookResult]:
        """Fire all hooks registered for *event* and collect results.

        For ``TOOL_BEFORE`` and ``TOOL_AFTER``, the chain is interrupted immediately when
        any hook returns ``blocked=True`` — subsequent hooks are skipped.
        """
        if not self.enabled:
            return []

        results: list[HookResult] = []
        for entry in self._hooks[event]:
            result = entry.callback(context)
            # Support both sync and async callbacks.
            if isinstance(result, HookResult):
                results.append(result)
            else:
                # Await coroutines from async callbacks.
                result = await result  # type: ignore[misc]
                results.append(result)

            if result.blocked and event in (HookEvent.TOOL_BEFORE, HookEvent.TOOL_AFTER):
                logger.info("Hook chain interrupted: %s blocked execution", event)
                break

        return results
