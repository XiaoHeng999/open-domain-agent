"""OTel-like Trace Data Model — Trace + Span + structured JSON logging."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class SpanKind(str, Enum):
    ROUTING = "routing"
    TOOL_CALL = "tool_call"
    MEMORY_OP = "memory_op"
    AGENT_LOOP = "agent_loop"
    CHECKPOINT = "checkpoint"
    RECOVERY = "recovery"
    EVAL = "eval"
    SUBAGENT = "subagent"
    INTERNAL = "internal"


@dataclass
class Span:
    """A single operation within a trace."""

    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_id: str | None = None
    operation: str = ""
    kind: SpanKind = SpanKind.INTERNAL
    attributes: dict[str, Any] = field(default_factory=dict)
    status: SpanStatus = SpanStatus.OK
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    error_message: str | None = None

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def finish(self, status: SpanStatus = SpanStatus.OK, error: str | None = None) -> None:
        self.end_time = time.time()
        self.status = status
        if error:
            self.error_message = error

    def set_attribute(self, key: str, value: Any) -> "Span":
        self.attributes[key] = value
        return self

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "span_id": self.span_id,
            "operation": self.operation,
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time,
            "attributes": self.attributes,
        }
        if self.parent_id:
            d["parent_id"] = self.parent_id
        if self.end_time:
            d["end_time"] = self.end_time
            d["duration_ms"] = self.duration_ms
        if self.error_message:
            d["error_message"] = self.error_message
        return d


@dataclass
class Trace:
    """A collection of spans representing a complete operation."""

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    spans: list[Span] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def create_span(
        self,
        operation: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_id: str | None = None,
    ) -> Span:
        span = Span(
            parent_id=parent_id,
            operation=operation,
            kind=kind,
            attributes={"trace_id": self.trace_id},
        )
        self.spans.append(span)
        return span

    def get_span(self, span_id: str) -> Span | None:
        for s in self.spans:
            if s.span_id == span_id:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "metadata": self.metadata,
            "spans": [s.to_dict() for s in self.spans],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


def _enforce_trace_retention(path: Path, max_retention: int) -> None:
    """Keep only the last *max_retention* lines in a trace JSONL file."""
    if not path.exists():
        return
    lines = path.read_text().splitlines()
    if len(lines) <= max_retention:
        return
    kept = lines[-max_retention:]
    path.write_text("\n".join(kept) + "\n")


class TraceManager:
    """Central trace manager — stores traces by trace_id."""

    def __init__(self, trace_dir: str = ".open_agent/traces") -> None:
        self._traces: dict[str, Trace] = {}
        self._trace_dir = trace_dir

    def create_trace(self, metadata: dict[str, Any] | None = None) -> Trace:
        trace = Trace(metadata=metadata or {})
        self._traces[trace.trace_id] = trace
        return trace

    def get_trace(self, trace_id: str) -> Trace | None:
        return self._traces.get(trace_id)

    def list_traces(self) -> list[str]:
        return list(self._traces.keys())

    async def persist_trace(self, trace_id: str) -> None:
        """Persist a single trace to disk, appending to traces.jsonl."""
        trace = self._traces.get(trace_id)
        if trace is None:
            return
        try:
            path = Path(self._trace_dir)
            path.mkdir(parents=True, exist_ok=True)
            jsonl_path = path / "traces.jsonl"
            line = json.dumps(trace.to_dict(), ensure_ascii=False)
            with open(jsonl_path, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass

    async def persist_all_traces(self) -> None:
        """Persist all in-memory traces to disk."""
        for trace_id in list(self._traces.keys()):
            await self.persist_trace(trace_id)
        # Enforce retention after bulk persist
        try:
            from open_agent.config import load_config
            cfg = load_config()
            retention = cfg.trace.trace_retention
            if isinstance(retention, int):
                _enforce_trace_retention(Path(self._trace_dir) / "traces.jsonl", retention)
        except Exception:
            pass

    @staticmethod
    def _parse_trace_dict(data: dict[str, Any]) -> Trace:
        """Parse a trace dict into a Trace object."""
        trace = Trace(
            trace_id=data["trace_id"],
            metadata=data.get("metadata", {}),
        )
        for span_data in data.get("spans", []):
            span = Span(
                span_id=span_data["span_id"],
                parent_id=span_data.get("parent_id"),
                operation=span_data["operation"],
                kind=SpanKind(span_data["kind"]),
                status=SpanStatus(span_data["status"]),
                start_time=span_data["start_time"],
                end_time=span_data.get("end_time"),
                error_message=span_data.get("error_message"),
                attributes=span_data.get("attributes", {}),
            )
            trace.spans.append(span)
        return trace

    def load_trace(self, trace_id: str) -> Trace | None:
        """Load a trace from disk by trace_id.

        Prefers traces.jsonl, falls back to legacy {trace_id}.json.
        """
        trace_dir = Path(self._trace_dir)

        # Try JSONL first
        jsonl_path = trace_dir / "traces.jsonl"
        if jsonl_path.exists():
            try:
                for line in jsonl_path.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("trace_id") == trace_id:
                        return self._parse_trace_dict(data)
            except Exception:
                pass

        # Fallback: legacy per-file format
        legacy_path = trace_dir / f"{trace_id}.json"
        if legacy_path.exists():
            try:
                data = json.loads(legacy_path.read_text())
                return self._parse_trace_dict(data)
            except Exception:
                pass

        return None

    def list_persisted_traces(self) -> list[str]:
        """List all trace IDs persisted on disk.

        Merges IDs from traces.jsonl and legacy *.json files, deduplicated.
        """
        trace_dir = Path(self._trace_dir)
        if not trace_dir.exists():
            return []

        ids: set[str] = set()

        # From JSONL
        jsonl_path = trace_dir / "traces.jsonl"
        if jsonl_path.exists():
            try:
                for line in jsonl_path.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if "trace_id" in data:
                        ids.add(data["trace_id"])
            except Exception:
                pass

        # From legacy files
        for p in trace_dir.glob("*.json"):
            ids.add(p.stem)

        return sorted(ids)


def setup_structured_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure structured JSON logging for the framework."""

    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_entry: dict[str, Any] = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "module": record.module,
                "message": record.getMessage(),
            }
            if hasattr(record, "trace_id"):
                log_entry["trace_id"] = record.trace_id
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_entry, ensure_ascii=False)

    _logger = logging.getLogger("open_agent")
    # Avoid adding duplicate handlers on repeated calls
    if not any(isinstance(h.formatter, JSONFormatter) for h in _logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        _logger.addHandler(handler)
    _logger.setLevel(level)
    return _logger
