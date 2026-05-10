"""Working memory — manages the context window with token counting and auto-compression."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import MemoryManager
from open_agent.config import MemoryConfig

logger = logging.getLogger("open_agent.memory.working")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, len(text) // 4)


@dataclass
class Message:
    """A single conversation turn."""

    role: str  # "user" | "assistant" | "system" | "summary"
    content: str
    timestamp: float = field(default_factory=time.time)

    @property
    def tokens(self) -> int:
        return _estimate_tokens(self.content)


class WorkingMemory(MemoryManager):
    """Context-window manager with automatic compression.

    Keeps recent turns intact while compressing older ones into summaries
    when the total token count approaches ``token_limit * compression_threshold``.
    """

    def __init__(self, config: MemoryConfig | None = None) -> None:
        super().__init__()
        self._config = config or MemoryConfig()
        self._messages: list[Message] = []
        self._summary_prefix: str = ""

    # ------------------------------------------------------------------
    # MemoryManager ABC
    # ------------------------------------------------------------------

    async def read(self, query: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        """Return the current context as a list of message dicts."""
        return await self.get_context()

    async def write(self, data: Any, **kwargs: Any) -> None:
        """Add a message. *data* should be a dict with 'role' and 'content'."""
        if isinstance(data, dict):
            await self.add_message(data.get("role", "user"), data.get("content", ""))
        elif isinstance(data, Message):
            self._messages.append(data)
            await self._maybe_compress()
        else:
            await self.add_message("user", str(data))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add_message(self, role: str, content: str) -> None:
        """Append a message and trigger compression if needed."""
        msg = Message(role=role, content=content)
        self._messages.append(msg)
        logger.debug(
            "WorkingMemory add_message role=%s tokens=%d total=%d",
            role,
            msg.tokens,
            self._total_tokens(),
        )
        await self._maybe_compress()

    async def get_context(self) -> list[dict[str, Any]]:
        """Return all messages (including summary prefix) as dicts."""
        result: list[dict[str, Any]] = []
        if self._summary_prefix:
            result.append({"role": "system", "content": self._summary_prefix})
        for msg in self._messages:
            result.append({"role": msg.role, "content": msg.content})
        return result

    async def compress_context(self) -> None:
        """Force compression of early turns into a summary.

        Keeps the last *keep_recent_turns* intact and summarizes everything
        before them.
        """
        keep = self._config.keep_recent_turns
        if len(self._messages) <= keep:
            return

        to_compress = self._messages[:-keep]
        self._messages = self._messages[-keep:]

        # Build a simple concatenation summary of early turns
        parts: list[str] = []
        if self._summary_prefix:
            parts.append(self._summary_prefix)
        for msg in to_compress:
            parts.append(f"[{msg.role}] {msg.content}")

        new_summary = " ".join(parts)
        # If the summary itself is very long, truncate it
        max_summary_tokens = int(self._config.working_memory_token_limit * 0.3)
        if _estimate_tokens(new_summary) > max_summary_tokens:
            char_limit = max_summary_tokens * 4
            new_summary = new_summary[:char_limit] + "..."
        self._summary_prefix = f"[Earlier conversation summary]: {new_summary}"

        logger.info(
            "WorkingMemory compressed %d turns into summary (%d tokens)",
            len(to_compress),
            _estimate_tokens(self._summary_prefix),
        )

    async def clear(self) -> None:
        """Remove all messages and summaries."""
        self._messages.clear()
        self._summary_prefix = ""

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _total_tokens(self) -> int:
        total = _estimate_tokens(self._summary_prefix) if self._summary_prefix else 0
        for msg in self._messages:
            total += msg.tokens
        return total

    async def _maybe_compress(self) -> None:
        threshold = int(
            self._config.working_memory_token_limit * self._config.compression_threshold
        )
        if self._total_tokens() >= threshold:
            await self.compress_context()
