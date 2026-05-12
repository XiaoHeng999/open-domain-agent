"""Subagent data types — preset definitions and result containers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubagentPreset:
    """Configuration template for a sub-agent type."""

    name: str
    system_prompt: str
    allowed_tools: list[str]
    max_turns: int = 10
    description: str = ""


@dataclass
class SubagentResult:
    """Result from a completed sub-agent execution."""

    agent_id: str
    answer: str
    success: bool
    duration_ms: float = 0.0
