"""Built-in hooks shipped with the agent framework."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from .types import HookResult

logger = logging.getLogger("open_agent.hooks")


# ---------------------------------------------------------------------------
# Welcome hook — SESSION_START
# ---------------------------------------------------------------------------

_HELLO_LUCKY_ART = r"""
 _   _      _ _                            _   _
| | | | ___| | | ___   __      _____  _ __| | | | __ _
| |_| |/ _ \ | |/ _ \  \ \ /\ / / _ \| '__| |_| |/ _` |
|  _  |  __/ | | (_) |  \ V  V / (_) | |  |  _  | (_| |
|_| |_|\___|_|_|\___/    \_/\_/ \___/|_|  |_| |_|\__, |
                                                  |___/
"""

_WELCOME_TEXT = "HELLO! LUCKY! — Your agent session has started."


def welcome_hook(context: dict[str, Any]) -> HookResult:
    """Print ASCII banner on session start and return welcome text."""
    print(_HELLO_LUCKY_ART)
    return HookResult(content=_WELCOME_TEXT)


# ---------------------------------------------------------------------------
# Pre-check hook — TOOL_BEFORE
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\brm\s+-rf\s+/"),
    re.compile(r"\brm\s+-rf\s+~"),
    re.compile(r"\bdd\s+if=.*of=/dev/"),
    re.compile(r"\bmkfs\b"),
    re.compile(r">\s*/dev/sd"),
    re.compile(r"\bchmod\s+-R\s+777\s+/"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
]

_HIGH_RISK_TOOLS = {"exec"}


def pre_check_hook(context: dict[str, Any]) -> HookResult:
    """Block dangerous commands from high-risk tools like ExecTool."""
    tool_name = context.get("tool_name", "")
    if tool_name not in _HIGH_RISK_TOOLS:
        return HookResult(blocked=False)

    command = context.get("args", {}).get("command", "")
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            return HookResult(
                blocked=True,
                content="Blocked: dangerous command pattern detected",
            )

    return HookResult(blocked=False)


# ---------------------------------------------------------------------------
# Audit hook — TOOL_AFTER
# ---------------------------------------------------------------------------


def audit_hook(context: dict[str, Any]) -> HookResult:
    """Log tool execution details and return an audit summary."""
    tool_name = context.get("tool_name", "unknown")
    success = context.get("success", False)
    duration_ms = context.get("duration_ms", 0.0)

    logger.info(
        "[AUDIT] tool=%s success=%s duration=%.1fms",
        tool_name,
        success,
        duration_ms,
    )

    return HookResult(
        content=f"[AUDIT] tool={tool_name} success={success} duration={duration_ms:.1f}ms",
        metadata={"tool_name": tool_name, "success": success, "duration_ms": duration_ms},
    )
