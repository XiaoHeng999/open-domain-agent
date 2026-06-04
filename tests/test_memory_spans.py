"""Tests for MEMORY_OP spans — trace instrumentation of memory subsystem."""

from __future__ import annotations

import asyncio
import tempfile
import shutil
from unittest.mock import AsyncMock

import pytest

from open_agent.trace import SpanKind, TraceManager


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def trace_manager():
    return TraceManager()


def _inject_tracing(memory_instance, trace_manager, trace_id):
    """Simulate what runtime.run() does to inject tracing into memory."""
    memory_instance._trace_manager = trace_manager
    memory_instance._current_trace_id = trace_id


class TestRuntimeMemorySpans:
    async def test_add_message_creates_span(self, trace_manager, tmp_dir):
        from open_agent.config import MemoryConfig
        from open_agent.memory.runtime import RuntimeMemory

        cfg = MemoryConfig(
            persistence_enabled=False,
            runtime_token_budget=100000,
        )
        rm = RuntimeMemory(config=cfg)
        trace = trace_manager.create_trace()
        _inject_tracing(rm, trace_manager, trace.trace_id)

        await rm.add_message("user", "hello world")

        memory_spans = [s for s in trace.spans if s.kind == SpanKind.MEMORY_OP]
        assert len(memory_spans) >= 1
        span = memory_spans[0]
        assert span.operation == "add_message"
        assert span.attributes.get("operation") == "write"
        assert span.attributes.get("role") == "user"
        assert span.attributes.get("content_length") == len("hello world")
        assert span.end_time is not None

    async def test_no_span_without_tracing(self, tmp_dir):
        from open_agent.config import MemoryConfig
        from open_agent.memory.runtime import RuntimeMemory

        cfg = MemoryConfig(persistence_enabled=False, runtime_token_budget=100000)
        rm = RuntimeMemory(config=cfg)
        # No _trace_manager injected — should work without error

        await rm.add_message("user", "hello")
        # No assertion needed — just verify no exception


class TestProfileMemorySpans:
    def test_load_creates_span(self, trace_manager, tmp_dir):
        from open_agent.config import MemoryConfig
        from open_agent.memory.profile import ProfileMemory

        cfg = MemoryConfig(profile_db_path=f"{tmp_dir}/profile.sqlite")
        pm = ProfileMemory(config=cfg)
        trace = trace_manager.create_trace()
        _inject_tracing(pm, trace_manager, trace.trace_id)

        pm.load()

        memory_spans = [s for s in trace.spans if s.kind == SpanKind.MEMORY_OP]
        assert len(memory_spans) == 1
        span = memory_spans[0]
        assert span.attributes.get("operation") == "profile_read"
        assert span.end_time is not None

    def test_save_creates_span(self, trace_manager, tmp_dir):
        from open_agent.config import MemoryConfig
        from open_agent.memory.profile import ProfileMemory

        cfg = MemoryConfig(profile_db_path=f"{tmp_dir}/profile.sqlite")
        pm = ProfileMemory(config=cfg)
        trace = trace_manager.create_trace()
        _inject_tracing(pm, trace_manager, trace.trace_id)

        pm.save({"preferences": {"language": "python"}})

        memory_spans = [s for s in trace.spans if s.kind == SpanKind.MEMORY_OP]
        assert len(memory_spans) == 1
        span = memory_spans[0]
        assert span.attributes.get("operation") == "profile_write"
        assert span.end_time is not None


class TestRetrievalMemorySpans:
    async def test_query_creates_span(self, trace_manager, tmp_dir):
        from open_agent.memory.retrieval import RetrievalMemory
        from open_agent.config import MemoryConfig

        cfg = MemoryConfig(retrieval_store_dir=f"{tmp_dir}/retrieval")
        rm = RetrievalMemory(config=cfg)
        trace = trace_manager.create_trace()
        _inject_tracing(rm, trace_manager, trace.trace_id)

        await rm.query("test query", top_k=3)

        memory_spans = [s for s in trace.spans if s.kind == SpanKind.MEMORY_OP]
        assert len(memory_spans) == 1
        span = memory_spans[0]
        assert span.attributes.get("operation") == "retrieval_query"
        assert span.attributes.get("top_k") == 3
        assert span.end_time is not None

    async def test_write_episodic_creates_span(self, trace_manager, tmp_dir):
        from open_agent.memory.retrieval import RetrievalMemory
        from open_agent.config import MemoryConfig

        cfg = MemoryConfig(retrieval_store_dir=f"{tmp_dir}/retrieval")
        rm = RetrievalMemory(config=cfg)
        trace = trace_manager.create_trace()
        _inject_tracing(rm, trace_manager, trace.trace_id)

        await rm.write_episodic(intent="test", steps_summary="did stuff", result="ok")

        memory_spans = [s for s in trace.spans if s.kind == SpanKind.MEMORY_OP]
        assert len(memory_spans) == 1
        span = memory_spans[0]
        assert span.attributes.get("operation") == "episodic_write"
        assert span.end_time is not None


class TestArchiveMemorySpans:
    def test_write_record_creates_span(self, trace_manager, tmp_dir):
        from open_agent.config import MemoryConfig
        from open_agent.memory.archive import ArchiveMemory

        cfg = MemoryConfig(archive_dir=f"{tmp_dir}/archive")
        am = ArchiveMemory(config=cfg)
        trace = trace_manager.create_trace()
        _inject_tracing(am, trace_manager, trace.trace_id)

        am.write_record({"type": "message", "role": "user", "content": "hi"})

        memory_spans = [s for s in trace.spans if s.kind == SpanKind.MEMORY_OP]
        assert len(memory_spans) == 1
        span = memory_spans[0]
        assert span.attributes.get("operation") == "archive_write"
        assert span.end_time is not None
