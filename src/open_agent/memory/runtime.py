"""Runtime memory — session-scoped context window with rolling summary compression."""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import MemoryManager
from open_agent.config import MemoryConfig
from open_agent.memory.models import Message, TaskState
from open_agent.memory.token_utils import estimate_tokens

logger = logging.getLogger("open_agent.memory.runtime")

# Compression levels
_COMPRESS_NORMAL = "normal"
_COMPRESS_COMPRESSING = "compressing"
_COMPRESS_AGGRESSIVE = "aggressive"


class RuntimeMemory(MemoryManager):
    """Session-scoped context window with token budget management.

    Manages four core data structures:
    - messages: raw conversation buffer
    - rolling_summary: compressed earlier conversation
    - task_state: ReAct execution state (never compressed)
    - tool_result_cache: LRU cache keyed by (tool_name, args_hash)
    """

    def __init__(self, config: MemoryConfig | None = None) -> None:
        super().__init__()
        self._config = config or MemoryConfig()
        self._messages: list[Message] = []
        self._rolling_summary: str = ""
        self._summary_turn_start: int = 0
        self._task_state: TaskState = TaskState()
        self._tool_cache: OrderedDict[str, str] = OrderedDict()

    # ------------------------------------------------------------------
    # MemoryManager ABC
    # ------------------------------------------------------------------

    async def read(self, query: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        return await self.get_context()

    async def write(self, data: Any, **kwargs: Any) -> None:
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
        """Append a message and trigger compression check."""
        msg = Message(role=role, content=content)
        self._messages.append(msg)
        logger.debug(
            "RuntimeMemory add_message role=%s tokens=%d total=%d",
            role, msg.tokens, self._total_tokens(),
        )
        await self._maybe_compress()

    async def get_context(self) -> list[dict[str, Any]]:
        """Return rolling_summary + raw messages formatted for LLM consumption."""
        result: list[dict[str, Any]] = []
        if self._rolling_summary:
            result.append({
                "role": "system",
                "content": f"[Earlier conversation summary]: {self._rolling_summary}",
            })
        for msg in self._messages:
            result.append({"role": msg.role, "content": msg.content})
        return result

    @property
    def task_state(self) -> TaskState:
        return self._task_state

    def reset_task_state(self) -> None:
        """Reset task state for a new run."""
        self._task_state = TaskState()

    @property
    def rolling_summary(self) -> str:
        return self._rolling_summary

    @property
    def compression_level(self) -> str:
        """Return current compression level based on token usage."""
        ratio = self._total_tokens() / self._config.runtime_token_budget
        if ratio >= self._config.aggressive_threshold:
            return _COMPRESS_AGGRESSIVE
        if ratio >= self._config.compression_threshold:
            return _COMPRESS_COMPRESSING
        return _COMPRESS_NORMAL

    # ------------------------------------------------------------------
    # Tool result cache
    # ------------------------------------------------------------------

    def cache_get(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """Look up cached tool result. Returns None on miss."""
        key = self._cache_key(tool_name, args)
        if key in self._tool_cache:
            self._tool_cache.move_to_end(key)
            return self._tool_cache[key]
        return None

    def cache_put(self, tool_name: str, args: dict[str, Any], result: str) -> None:
        """Store a tool result in cache. Evicts LRU entry when full."""
        key = self._cache_key(tool_name, args)
        if key in self._tool_cache:
            self._tool_cache.move_to_end(key)
        self._tool_cache[key] = result
        while len(self._tool_cache) > self._config.tool_cache_max_entries:
            self._tool_cache.popitem(last=False)

    async def clear(self) -> None:
        """Remove all messages, summary, and cache."""
        self._messages.clear()
        self._rolling_summary = ""
        self._tool_cache.clear()
        self._task_state = TaskState()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _total_tokens(self) -> int:
        total = estimate_tokens(self._rolling_summary) if self._rolling_summary else 0
        for msg in self._messages:
            total += msg.tokens
        return total

    async def _maybe_compress(self) -> None:
        level = self.compression_level
        if level == _COMPRESS_NORMAL:
            return
        if level in (_COMPRESS_COMPRESSING, _COMPRESS_AGGRESSIVE):
            await self._compress_rolling_summary()
        if level == _COMPRESS_AGGRESSIVE:
            self._truncate_tool_cache()

    async def _compress_rolling_summary(self) -> None:
        """Compress the earliest 2 turns of raw messages into rolling summary."""
        keep = self._config.keep_recent_turns * 2  # user+assistant pairs
        if len(self._messages) <= keep:
            return

        to_compress = self._messages[:-keep]
        self._messages = self._messages[-keep:]

        parts: list[str] = []
        for msg in to_compress:
            parts.append(f"[{msg.role}] {msg.content}")

        new_summary_part = " ".join(parts)
        turn_start = self._summary_turn_start
        turn_end = turn_start + len(to_compress) // 2

        if self._rolling_summary:
            self._rolling_summary += f" | [Turns {turn_start+1}-{turn_end}]: {new_summary_part}"
        else:
            self._rolling_summary = f"[Turns {turn_start+1}-{turn_end}]: {new_summary_part}"

        self._summary_turn_start = turn_end

        # Secondary compression: if summary exceeds 30% of budget, re-compress
        max_summary_tokens = int(self._config.runtime_token_budget * 0.3)
        if estimate_tokens(self._rolling_summary) > max_summary_tokens:
            char_limit = max_summary_tokens * 4
            self._rolling_summary = self._rolling_summary[:char_limit] + "..."

        logger.info(
            "RuntimeMemory compressed %d messages into summary (%d tokens)",
            len(to_compress), estimate_tokens(self._rolling_summary),
        )

    def _truncate_tool_cache(self) -> None:
        """In aggressive mode, truncate tool cache entries."""
        max_tokens = self._config.max_tool_result_tokens
        total = sum(estimate_tokens(v) for v in self._tool_cache.values())
        while total > max_tokens and self._tool_cache:
            _, oldest = self._tool_cache.popitem(last=False)
            total -= estimate_tokens(oldest)

    @staticmethod
    def _cache_key(tool_name: str, args: dict[str, Any]) -> str:
        raw = f"{tool_name}:{sorted(args.items())}"
        return hashlib.md5(raw.encode()).hexdigest()
