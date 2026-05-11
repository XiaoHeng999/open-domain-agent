"""Data models shared across memory layers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A single conversation turn with token tracking."""

    role: str  # "user" | "assistant" | "system" | "summary"
    content: str
    timestamp: float = field(default_factory=time.time)
    tokens: int = 0

    def __post_init__(self) -> None:
        if self.tokens == 0:
            from open_agent.memory.token_utils import estimate_tokens

            self.tokens = estimate_tokens(self.content)


@dataclass
class TaskState:
    """Execution state for the current ReAct loop."""

    current_step: int = 0
    finished: bool = False
    termination_flags: list[str] = field(default_factory=list)
    rounds_since_todo_update: int = 0

    def increment_step(self) -> None:
        self.current_step += 1
        self.rounds_since_todo_update += 1

    def mark_finished(self, flag: str = "") -> None:
        self.finished = True
        if flag:
            self.termination_flags.append(flag)

    def reset_todo_counter(self) -> None:
        self.rounds_since_todo_update = 0
