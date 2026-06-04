"""Tests for trace JSONL persistence (Issue 05)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_agent.trace import SpanKind, Trace, TraceManager


class TestTraceJSONLPersist:
    async def test_persist_appends_to_jsonl(self, tmp_path: Path):
        """persist_trace should append a line to traces.jsonl."""
        mgr = TraceManager(trace_dir=str(tmp_path))
        trace = mgr.create_trace(metadata={"user_input": "hello"})
        trace.create_span("routing", kind=SpanKind.ROUTING).finish()

        await mgr.persist_trace(trace.trace_id)

        jsonl = tmp_path / "traces.jsonl"
        assert jsonl.exists()
        lines = jsonl.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["trace_id"] == trace.trace_id

    async def test_persist_load_roundtrip_jsonl(self, tmp_path: Path):
        """persist_trace → load_trace roundtrip via JSONL."""
        mgr = TraceManager(trace_dir=str(tmp_path))
        trace = mgr.create_trace(metadata={"key": "value"})
        span = trace.create_span("tool_call", kind=SpanKind.TOOL_CALL)
        span.set_attribute("tool", "read_file")
        span.finish()

        await mgr.persist_trace(trace.trace_id)
        loaded = mgr.load_trace(trace.trace_id)

        assert loaded is not None
        assert loaded.trace_id == trace.trace_id
        assert len(loaded.spans) == 1
        assert loaded.spans[0].operation == "tool_call"
        assert loaded.spans[0].attributes["tool"] == "read_file"


class TestTraceRetention:
    async def test_retention_keeps_latest(self, tmp_path: Path):
        """Writing 150 traces should keep only 100 in JSONL."""
        mgr = TraceManager(trace_dir=str(tmp_path))
        for _ in range(150):
            t = mgr.create_trace()
            t.create_span("op").finish()
            await mgr.persist_trace(t.trace_id)

        await mgr.persist_all_traces()

        jsonl = tmp_path / "traces.jsonl"
        lines = jsonl.read_text().strip().splitlines()
        assert len(lines) <= 100


class TestTraceBackwardCompat:
    def test_load_old_json_file(self, tmp_path: Path):
        """load_trace should still read old {trace_id}.json files."""
        mgr = TraceManager(trace_dir=str(tmp_path))
        trace = Trace(trace_id="legacy123", metadata={"old": True})
        span = trace.create_span("op", kind=SpanKind.INTERNAL)
        span.finish()

        # Write in old format
        old_file = tmp_path / "legacy123.json"
        old_file.write_text(trace.to_json())

        loaded = mgr.load_trace("legacy123")
        assert loaded is not None
        assert loaded.trace_id == "legacy123"
        assert loaded.metadata["old"] is True

    def test_list_includes_old_json_files(self, tmp_path: Path):
        """list_persisted_traces should include old {id}.json stems."""
        (tmp_path / "abc123.json").write_text('{"trace_id": "abc123"}')
        (tmp_path / "def456.json").write_text('{"trace_id": "def456"}')

        mgr = TraceManager(trace_dir=str(tmp_path))
        ids = mgr.list_persisted_traces()
        assert "abc123" in ids
        assert "def456" in ids


class TestTraceListJSONL:
    async def test_list_from_jsonl(self, tmp_path: Path):
        """list_persisted_traces should read trace IDs from JSONL."""
        mgr = TraceManager(trace_dir=str(tmp_path))
        t1 = mgr.create_trace()
        t2 = mgr.create_trace()
        await mgr.persist_trace(t1.trace_id)
        await mgr.persist_trace(t2.trace_id)

        ids = mgr.list_persisted_traces()
        assert t1.trace_id in ids
        assert t2.trace_id in ids
