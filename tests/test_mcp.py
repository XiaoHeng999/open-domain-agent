"""Tests for MCP integration."""

from __future__ import annotations

import pytest

from open_agent.decorators import tool_schema
from open_agent.mcp_integration import (
    MCPServerManager,
    ServerConfig,
    ServerHealth,
    TransportType,
    register_tool_with_schema,
)
from open_agent.registry import ToolRegistry


class TestServerHealth:
    def test_initial_state(self):
        health = ServerHealth()
        assert health.healthy
        assert health.consecutive_failures == 0

    def test_record_failure(self):
        health = ServerHealth(max_failures=3)
        health.record_failure()
        assert health.consecutive_failures == 1
        assert health.healthy

        health.record_failure()
        health.record_failure()
        assert health.consecutive_failures == 3
        assert not health.healthy

    def test_record_success_resets(self):
        health = ServerHealth()
        health.record_failure()
        health.record_failure()
        health.record_success()
        assert health.consecutive_failures == 0
        assert health.healthy


class TestMCPRegistration:
    @pytest.mark.asyncio
    async def test_register_server(self):
        registry = ToolRegistry()
        mgr = MCPServerManager(registry)
        config = ServerConfig(server_id="test-server", transport=TransportType.STDIO)
        sid = await mgr.register_server(config)
        assert sid == "test-server"
        assert len(mgr.list_servers()) == 1

    @pytest.mark.asyncio
    async def test_duplicate_server(self):
        registry = ToolRegistry()
        mgr = MCPServerManager(registry)
        config = ServerConfig(server_id="s1")
        await mgr.register_server(config)
        with pytest.raises(ValueError, match="already registered"):
            await mgr.register_server(config)


class TestToolSchemaRegistration:
    def test_schema_required(self):
        registry = ToolRegistry()
        handler = lambda: None  # no @tool_schema
        with pytest.raises(ValueError, match="must be decorated with @tool_schema"):
            register_tool_with_schema(registry, handler)

    def test_register_with_schema(self):
        registry = ToolRegistry()

        @tool_schema(name="test_tool")
        def my_tool(query: str) -> str:
            """A test tool."""
            ...

        register_tool_with_schema(registry, my_tool, server_id="s1")
        assert registry.has("test_tool")
        entry = registry.get("test_tool")
        assert getattr(entry, "_server_id", None) == "s1"
        assert "query" in entry.parameters["properties"]

    def test_register_with_tags(self):
        registry = ToolRegistry()

        @tool_schema(name="tagged_tool")
        def tagged(x: int) -> str:
            """Tagged."""
            ...

        register_tool_with_schema(registry, tagged, tags=["math"])
        assert len(registry.list_by_tag("math")) == 1
