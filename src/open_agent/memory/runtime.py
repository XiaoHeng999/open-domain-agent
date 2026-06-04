"""Runtime memory — session-scoped context window with rolling summary compression."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import sqlite3
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from open_agent.base import MemoryManager
from open_agent.config import MemoryConfig
from open_agent.memory.models import Message, TaskState
from open_agent.memory.token_utils import estimate_tokens
from open_agent.trace import SpanKind

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

    When persistence is enabled (MemoryConfig.persistence_enabled), messages
    are also written to SQLite for cross-session durability.
    """

    def __init__(self, config: MemoryConfig | None = None) -> None:
        super().__init__()
        self._config = config or MemoryConfig()
        self._messages: list[Message] = []
        self._rolling_summary: str = ""
        self._summary_turn_start: int = 0
        self._task_state: TaskState = TaskState()
        self._tool_cache: OrderedDict[str, str] = OrderedDict()
        self._tool_messages: list[dict[str, Any]] = []
        self._db_conn: sqlite3.Connection | None = None

        if self._config.persistence_enabled:
            self._init_db()
            self._cleanup_old_records()
            self._load_messages()

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
        span = _start_memory_span(self, "add_message")
        if span:
            span.set_attribute("operation", "write")
            span.set_attribute("role", role)
            span.set_attribute("content_length", len(content))
        msg = Message(role=role, content=content)
        self._messages.append(msg)
        logger.debug(
            "RuntimeMemory add_message role=%s tokens=%d total=%d",
            role, msg.tokens, self._total_tokens(),
        )
        if self._config.persistence_enabled and self._db_conn is not None:
            await asyncio.to_thread(self._persist_message, role, content)
        await self._maybe_compress()
        _finish_span(span)

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
        """Remove all messages, summary, cache, and tool messages."""
        self._messages.clear()
        self._rolling_summary = ""
        self._tool_cache.clear()
        self._task_state = TaskState()
        self._tool_messages.clear()
        if self._db_conn is not None:
            try:
                self._db_conn.execute("DELETE FROM messages")
                self._db_conn.commit()
            except sqlite3.Error:
                pass

    def close(self) -> None:
        """Close the SQLite connection if open."""
        if self._db_conn is not None:
            try:
                self._db_conn.close()
            except sqlite3.Error:
                pass
            self._db_conn = None

    # ------------------------------------------------------------------
    # Persistence internals
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the database and messages table."""
        db_path = Path(self._config.persistence_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db_conn.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "role TEXT NOT NULL, "
            "content TEXT NOT NULL, "
            "timestamp REAL NOT NULL)"
        )
        self._db_conn.commit()

    def _persist_message(self, role: str, content: str) -> None:
        """Write a single message to SQLite."""
        if self._db_conn is None:
            return
        try:
            self._db_conn.execute(
                "INSERT INTO messages (role, content, timestamp) VALUES (?, ?, ?)",
                (role, content, time.time()),
            )
            self._db_conn.commit()
        except sqlite3.Error:
            logger.warning("Failed to persist message to SQLite", exc_info=True)

    def _load_messages(self) -> None:
        """Load messages from SQLite into the in-memory buffer."""
        if self._db_conn is None:
            return
        try:
            cur = self._db_conn.execute(
                "SELECT role, content FROM messages ORDER BY id ASC"
            )
            for role, content in cur.fetchall():
                self._messages.append(Message(role=role, content=content))
        except sqlite3.Error:
            logger.warning("Failed to load messages from SQLite", exc_info=True)

    def _cleanup_old_records(self) -> None:
        """Delete records older than retention_days."""
        if self._db_conn is None:
            return
        cutoff = time.time() - self._config.persistence_retention_days * 86400
        try:
            self._db_conn.execute(
                "DELETE FROM messages WHERE timestamp < ?", (cutoff,)
            )
            self._db_conn.commit()
        except sqlite3.Error:
            logger.warning("Failed to cleanup old records", exc_info=True)

    # ------------------------------------------------------------------
    # Tool messages (tool_use/tool_result pairs for LLM context)
    # ------------------------------------------------------------------

    def add_tool_messages(self, messages: list[dict[str, Any]]) -> None:
        """Append tool messages and enforce token budget."""
        self._tool_messages.extend(messages)
        self._enforce_tool_message_budget()

    def get_tool_messages(self) -> list[dict[str, Any]]:
        """Return current tool messages."""
        return list(self._tool_messages)

    def clear_tool_messages(self) -> None:
        """Clear tool messages only."""
        self._tool_messages.clear()

    def _enforce_tool_message_budget(self) -> None:
        """Truncate oldest tool messages when they exceed the token budget."""
        max_tokens = self._config.max_tool_result_tokens
        total = sum(estimate_tokens(m.get("content", "")) for m in self._tool_messages)
        while total > max_tokens and self._tool_messages:
            removed = self._tool_messages.pop(0)
            total -= estimate_tokens(removed.get("content", ""))

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
        span = _start_memory_span(self, "compress")
        if span:
            span.set_attribute("operation", "compress")
        compressed_count = 0
        if level in (_COMPRESS_COMPRESSING, _COMPRESS_AGGRESSIVE):
            before = len(self._messages)
            await self._compress_rolling_summary()
            compressed_count = before - len(self._messages)
        if level == _COMPRESS_AGGRESSIVE:
            self._truncate_tool_cache()
        if span:
            span.set_attribute("messages_compressed", compressed_count)
        _finish_span(span)

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


def _start_memory_span(obj: Any, operation: str, **attrs: Any) -> Any:
    """Create a MEMORY_OP span if tracing is active, else return None."""
    tm = getattr(obj, "_trace_manager", None)
    tid = getattr(obj, "_current_trace_id", None)
    if tm is None or tid is None:
        return None
    trace = tm.get_trace(tid)
    if trace is None:
        return None
    span = trace.create_span(operation, kind=SpanKind.MEMORY_OP)
    span.set_attribute("operation", operation)
    for k, v in attrs.items():
        span.set_attribute(k, v)
    return span


def _finish_span(span: Any) -> None:
    if span is not None:
        span.finish()
