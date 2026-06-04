"""Archive memory — JSONL cold storage for debug/eval/replay."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from open_agent.base import MemoryManager
from open_agent.config import MemoryConfig
from open_agent.trace import SpanKind

logger = logging.getLogger("open_agent.memory.archive")


class ArchiveMemory(MemoryManager):
    """Append-only JSONL log, one file per session.

    Does NOT participate in prompt assembly (no injection).
    """

    def __init__(
        self,
        config: MemoryConfig | None = None,
        session_id: str = "",
    ) -> None:
        super().__init__()
        self._config = config or MemoryConfig()
        self._archive_dir = Path(self._config.archive_dir)
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = session_id or time.strftime("%Y%m%d_%H%M%S")
        self._path = self._archive_dir / f"{self._session_id}.jsonl"

    # ------------------------------------------------------------------
    # MemoryManager ABC
    # ------------------------------------------------------------------

    async def read(self, query: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        session_id = kwargs.get("session_id", self._session_id)
        return self.query(session_id, type=kwargs.get("type"), limit=kwargs.get("limit"))

    async def write(self, data: Any, **kwargs: Any) -> None:
        if isinstance(data, dict):
            self.write_record(data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_record(self, record: dict[str, Any]) -> None:
        """Append a record to the session JSONL file.

        Adds timestamp automatically if not present.
        """
        span = _start_archive_span(self, "archive_write")
        record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ"))
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        _finish_span(span)

    def query(
        self,
        session_id: str,
        type: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Read records from a session's JSONL file with optional filtering."""
        path = self._archive_dir / f"{session_id}.jsonl"
        if not path.exists():
            return []

        results: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if type and record.get("type") != type:
                    continue
                results.append(record)
                if limit and len(results) >= limit:
                    break
        return results

    def replay(self, session_id: str) -> list[dict[str, Any]]:
        """Return all records for a session, ordered by timestamp."""
        return self.query(session_id)

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def archive_path(self) -> Path:
        return self._path


def _start_archive_span(obj, operation: str, **attrs):
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


def _finish_span(span):
    if span is not None:
        span.finish()
