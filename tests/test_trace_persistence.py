"""Tests for trace persistence: persist, load, list, auto-mkdir, and env var overrides."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent.trace import SpanKind, TraceManager


@pytest.fixture
def trace_dir():
    """Create a temporary trace directory."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def manager(trace_dir):
    """Create a TraceManager with a temp trace_dir."""
    return TraceManager(trace_dir=trace_dir)


class TestPersistTrace:
    async def test_persist_creates_json_file(self, manager, trace_dir):
        trace = manager.create_trace(metadata={"user_input": "hello"})
        span = trace.create_span("routing", kind=SpanKind.ROUTING)
        span.finish()

        await manager.persist_trace(trace.trace_id)

        path = Path(trace_dir) / f"{trace.trace_id}.json"
        assert path.exists()

    async def test_persist_load_roundtrip(self, manager):
        trace = manager.create_trace(metadata={"user_input": "test"})
        span = trace.create_span("tool_call", kind=SpanKind.TOOL_CALL)
        span.set_attribute("tool", "read_file")
        span.finish()

        await manager.persist_trace(trace.trace_id)
        loaded = manager.load_trace(trace.trace_id)

        assert loaded is not None
        assert loaded.trace_id == trace.trace_id
        assert len(loaded.spans) == 1
        assert loaded.spans[0].operation == "tool_call"
        assert loaded.spans[0].attributes["tool"] == "read_file"

    async def test_persist_auto_creates_directory(self, trace_dir):
        nested = os.path.join(trace_dir, "nested", "traces")
        mgr = TraceManager(trace_dir=nested)
        trace = mgr.create_trace()
        await mgr.persist_trace(trace.trace_id)
        assert Path(nested).exists()
        assert (Path(nested) / f"{trace.trace_id}.json").exists()


class TestLoadTrace:
    def test_load_nonexistent_returns_none(self, manager):
        result = manager.load_trace("nonexistent_id")
        assert result is None

    def test_load_returns_trace_with_correct_metadata(self, manager):
        trace = manager.create_trace(metadata={"key": "value"})
        span = trace.create_span("test_op", kind=SpanKind.INTERNAL)
        span.finish()

        # Manually write to simulate persisted file
        path = Path(manager._trace_dir) / f"{trace.trace_id}.json"
        path.write_text(trace.to_json())

        loaded = manager.load_trace(trace.trace_id)
        assert loaded is not None
        assert loaded.metadata["key"] == "value"


class TestListPersistedTraces:
    async def test_list_empty_dir(self, manager, trace_dir):
        result = manager.list_persisted_traces()
        assert result == []

    async def test_list_returns_trace_ids(self, manager):
        t1 = manager.create_trace()
        t2 = manager.create_trace()
        await manager.persist_trace(t1.trace_id)
        await manager.persist_trace(t2.trace_id)

        ids = manager.list_persisted_traces()
        assert set(ids) == {t1.trace_id, t2.trace_id}


class TestPersistAllInOnStop:
    async def test_persist_all_traces_on_stop(self, trace_dir):
        # Test the persist_all_traces path directly via TraceManager
        mgr = TraceManager(trace_dir=trace_dir)
        t1 = mgr.create_trace(metadata={"test": 1})
        t2 = mgr.create_trace(metadata={"test": 2})
        for t in [t1, t2]:
            t.create_span("op").finish()

        await mgr.persist_all_traces()

        ids = mgr.list_persisted_traces()
        assert set(ids) == {t1.trace_id, t2.trace_id}


class TestPersistFailureGraceful:
    async def test_persist_failure_does_not_raise(self, trace_dir):
        mgr = TraceManager(trace_dir="/nonexistent/path/that/cannot/be/created/xyz")
        trace = mgr.create_trace()
        # Should not raise, even though path is invalid
        await mgr.persist_trace(trace.trace_id)


class TestEnvVarOverrides:
    def test_trace_dir_from_env(self):
        with patch.dict(os.environ, {"OPEN_AGENT_TRACE_DIR": "/tmp/custom_traces"}):
            from open_agent.config import load_config
            cfg = load_config()
            assert cfg.trace.trace_dir == "/tmp/custom_traces"

    def test_store_traces_from_env(self):
        with patch.dict(os.environ, {"OPEN_AGENT_STORE_TRACES": "false"}):
            from open_agent.config import load_config
            cfg = load_config()
            assert cfg.trace.store_traces is False
