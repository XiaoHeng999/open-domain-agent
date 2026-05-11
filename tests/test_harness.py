"""Tests for harness infrastructure — config, ABC, factory, registry, trace, CLI."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from open_agent.base import BaseComponent, LifecycleState, MemoryManager, Router
from open_agent.config import AgentConfig, load_config
from open_agent.decorators import tool_schema
from open_agent.errors import AgentError, ToolError, SSRFError
from open_agent.fallback import FallbackChain
from open_agent.registry import ToolRegistry
from open_agent.trace import Span, SpanKind, SpanStatus, Trace, TraceManager


# --- Config tests ---

class TestConfig:
    def test_default_config(self):
        cfg = AgentConfig()
        assert cfg.model.provider == "openai"
        assert cfg.model.temperature == 0.7
        assert cfg.safety.safety_level == "strict"
        assert cfg.checkpoint.enabled is True

    def test_yaml_loading(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("""
model:
  provider: anthropic
  name: claude-3-opus
  temperature: 0.5
safety:
  safety_level: permissive
""")
        cfg = load_config(str(yaml_file))
        assert cfg.model.provider == "anthropic"
        assert cfg.model.name == "claude-3-opus"
        assert cfg.safety.safety_level == "permissive"

    def test_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPEN_AGENT_MODEL_PROVIDER", "deepseek")
        monkeypatch.setenv("OPEN_AGENT_MODEL_API_KEY", "test-key")
        cfg = load_config()
        assert cfg.model.provider == "deepseek"
        assert cfg.model.api_key == "test-key"

    def test_runtime_overrides(self):
        cfg = load_config(model={"name": "gpt-4o-mini"}, workspace="/tmp")
        assert cfg.model.name == "gpt-4o-mini"
        assert cfg.workspace == "/tmp"

    def test_validation_error(self):
        with pytest.raises(Exception):
            AgentConfig(model={"temperature": 5.0})


# --- ABC / Lifecycle tests ---

class DummyMemory(MemoryManager):
    async def read(self, query, **kwargs):
        return {"result": query}

    async def write(self, data, **kwargs):
        pass


class TestABC:
    @pytest.mark.asyncio
    async def test_lifecycle_hooks(self):
        mem = DummyMemory()
        assert not mem._registered
        await mem.on_register()
        assert mem._registered
        await mem.on_start()
        assert mem._started
        await mem.on_stop()
        assert not mem._started

    @pytest.mark.asyncio
    async def test_on_error(self):
        mem = DummyMemory()
        await mem.on_error(ValueError("test"))
        # Should not raise

    def test_lifecycle_state(self):
        state = LifecycleState()
        assert not state.registered
        state.registered = True
        assert state.registered


# --- Factory tests ---

class TestProviderFactory:
    def test_create_local_provider(self):
        from open_agent.config import ModelConfig
        from open_agent.model import ProviderFactory

        cfg = ModelConfig(provider="local")
        provider = ProviderFactory.create(cfg)
        assert provider is not None

    def test_unknown_provider(self):
        from open_agent.config import ModelConfig
        from open_agent.model import ProviderFactory

        with pytest.raises(Exception):  # Pydantic validation or ValueError
            ProviderFactory.create(ModelConfig(provider="foobar"))

    def test_available_providers(self):
        from open_agent.model import ProviderFactory

        providers = ProviderFactory.available()
        assert "local" in providers
        assert "openai" in providers


# --- Registry tests ---

def _make_tool(name: str, tags: list[str] | None = None, server_id: str | None = None):
    """Helper to create a FunctionTool for testing."""
    from open_agent.tools.base import FunctionTool
    tool = FunctionTool(
        name=name,
        description=f"Tool {name}",
        parameters={"type": "object", "properties": {}},
        handler=lambda: "ok",
    )
    if server_id:
        tool._server_id = server_id
    return tool


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register(_make_tool("test_tool"))
        tool = reg.get("test_tool")
        assert tool.name == "test_tool"
        assert tool.description == "Tool test_tool"

    def test_duplicate_register(self):
        reg = ToolRegistry()
        reg.register(_make_tool("t1"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_make_tool("t1"))

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register(_make_tool("t1"))
        reg.unregister("t1")
        assert not reg.has("t1")

    def test_unregister_missing(self):
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.unregister("nope")

    def test_list_by_tag(self):
        reg = ToolRegistry()
        reg.register(_make_tool("t1"), tags=["search"])
        reg.register(_make_tool("t2"), tags=["code"])
        reg.register(_make_tool("t3"), tags=["search", "web"])
        assert len(reg.list_by_tag("search")) == 2

    def test_unregister_by_server(self):
        reg = ToolRegistry()
        reg.register(_make_tool("t1", server_id="s1"))
        reg.register(_make_tool("t2", server_id="s1"))
        reg.register(_make_tool("t3", server_id="s2"))
        removed = reg.unregister_by_server("s1")
        assert removed == 2
        assert len(reg) == 1

    def test_snapshot(self):
        reg = ToolRegistry()
        reg.register(_make_tool("t1"))
        reg.register(_make_tool("t2"))
        snap = reg.snapshot()
        assert isinstance(snap, frozenset)
        assert snap == frozenset(["t1", "t2"])

    def test_restore(self):
        reg = ToolRegistry()
        reg.register(_make_tool("t1"))
        reg.register(_make_tool("t2"))
        snap = reg.snapshot()
        reg.register(_make_tool("t3"))
        assert len(reg) == 3
        reg.restore(snap)
        assert len(reg) == 2
        assert reg.has("t1")
        assert reg.has("t2")
        assert not reg.has("t3")

    def test_filter_by_tags(self):
        reg = ToolRegistry()
        reg.register(_make_tool("t1"), tags=["coding", "file"])
        reg.register(_make_tool("t2"), tags=["web"])
        reg.register(_make_tool("t3"), tags=["coding"])
        result = reg.filter_by_tags(["coding"])
        names = [t.name for t in result]
        assert "t1" in names
        assert "t3" in names
        assert "t2" not in names

    def test_filter_by_tags_multiple(self):
        reg = ToolRegistry()
        reg.register(_make_tool("t1"), tags=["coding"])
        reg.register(_make_tool("t2"), tags=["web"])
        result = reg.filter_by_tags(["coding", "web"])
        assert len(result) == 2


# --- Trace tests ---

class TestTrace:
    def test_span_creation(self):
        span = Span(operation="test_op", kind=SpanKind.TOOL_CALL)
        assert span.operation == "test_op"
        assert span.status == SpanStatus.OK

    def test_span_finish(self):
        span = Span(operation="test")
        span.finish()
        assert span.end_time is not None
        assert span.duration_ms is not None
        assert span.duration_ms >= 0

    def test_span_error(self):
        span = Span(operation="test")
        span.finish(status=SpanStatus.ERROR, error="something failed")
        assert span.error_message == "something failed"

    def test_trace_create_span(self):
        trace = Trace()
        span = trace.create_span("routing", kind=SpanKind.ROUTING)
        assert span.operation == "routing"
        assert span.attributes["trace_id"] == trace.trace_id

    def test_trace_serialization(self):
        trace = Trace(metadata={"user": "test"})
        span = trace.create_span("tool_call", kind=SpanKind.TOOL_CALL)
        span.set_attribute("tool", "search")
        span.finish()

        d = trace.to_dict()
        assert d["trace_id"] == trace.trace_id
        assert len(d["spans"]) == 1

        json_str = trace.to_json()
        parsed = json.loads(json_str)
        assert parsed["trace_id"] == trace.trace_id

    def test_trace_manager(self):
        mgr = TraceManager()
        trace = mgr.create_trace(metadata={"test": True})
        assert mgr.get_trace(trace.trace_id) is trace
        assert trace.trace_id in mgr.list_traces()


# --- Decorator tests ---

class TestToolSchema:
    def test_basic_schema(self):
        @tool_schema
        def search(query: str, limit: int = 10) -> str:
            """Search the web.
            Args:
                query: Search query string
                limit: Max results
            """
            ...

        schema = search._tool_schema
        assert schema["name"] == "search"
        assert "query" in schema["inputSchema"]["properties"]
        assert "required" in schema["inputSchema"]
        assert "query" in schema["inputSchema"]["required"]

    def test_custom_name(self):
        @tool_schema(name="web_search")
        def search(q: str) -> str:
            """Search."""
            ...

        assert search._tool_schema["name"] == "web_search"

    def test_registry_with_decorated(self):
        from open_agent.tools.base import FunctionTool
        reg = ToolRegistry()

        @tool_schema
        def search(query: str) -> str:
            """Search."""
            ...

        schema = search._tool_schema
        tool = FunctionTool(
            name=schema["name"],
            description=schema.get("description", ""),
            parameters=schema.get("inputSchema", {"type": "object", "properties": {}}),
            handler=search,
        )
        reg.register(tool)
        t = reg.get("search")
        assert t.name == "search"


# --- Fallback tests ---

class TestFallbackChain:
    @pytest.mark.asyncio
    async def test_first_succeeds(self):
        chain = FallbackChain()
        chain.add("primary", lambda: "ok")
        result = await chain.execute()
        assert result.success
        assert result.value == "ok"
        assert result.provider_used == "primary"

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        chain = FallbackChain()
        chain.add("bad", lambda: (_ for _ in ()).throw(ValueError("fail")))
        chain.add("good", lambda: "ok")

        result = await chain.execute()
        assert result.success
        assert result.value == "ok"
        assert result.provider_used == "good"

    @pytest.mark.asyncio
    async def test_all_fail(self):
        chain = FallbackChain()
        chain.add("a", lambda: (_ for _ in ()).throw(ValueError("a")))
        chain.add("b", lambda: (_ for _ in ()).throw(ValueError("b")))

        result = await chain.execute()
        assert not result.success
        assert result.error is not None


# --- Error hierarchy tests ---

class TestErrors:
    def test_agent_error_with_cause(self):
        err = AgentError("base", cause=ValueError("root"))
        assert "caused by" in str(err)

    def test_tool_error(self):
        err = ToolError("tool failed", tool_name="search")
        assert err.tool_name == "search"

    def test_ssrf_error(self):
        err = SSRFError("blocked", url="http://127.0.0.1", reason="private IP")
        assert err.url == "http://127.0.0.1"
