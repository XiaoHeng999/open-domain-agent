"""Hook type definitions — events, results, and callback signatures."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class HookEvent(str, Enum):
    """Lifecycle events that hooks can subscribe to."""

    SESSION_START = "session_start"
    TOOL_BEFORE = "tool_before"
    TOOL_AFTER = "tool_after"


# Callback receives a context dict and returns a HookResult.
HookCallback = Callable[[dict[str, Any]], "HookResult"]


@dataclass
class HookResult:
    """Result returned by a hook callback.

    Attributes
    ----------
    content:
        Optional text injected into the LLM message stream.
    blocked:
        When True (only meaningful for TOOL_BEFORE), stops tool execution.
    metadata:
        Arbitrary dict for non-injected data (audit metrics, etc.).
    """

    content: str | None = None
    blocked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
