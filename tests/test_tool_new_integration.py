"""Integration tests — verify all new tools work through ToolRegistry pipeline."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from open_agent.registry import ToolRegistry, scan_builtin_tools
from open_agent.config import AgentConfig
from open_agent.tools.self import SelfTool
from open_agent.tools.search import SearchTool
from open_agent.tools.sandbox_control import SandboxControlTool
from open_agent.tools.mcp_client import MCPClientTool


class _FakeLoop:
    _max_iterations = 10
    _staleness_rounds = 3
    _tool_messages = []
    _runtime_memory = None


def _registry_with_all_tools():
    config = AgentConfig()
    registry = ToolRegistry()
    scan_builtin_tools(registry, config)

    # Keep loop reference alive to prevent weakref GC
    loop = _FakeLoop()
    registry.register(SelfTool(react_loop=loop))
    registry.register(SandboxControlTool(sandbox=MagicMock(on_start=AsyncMock())))
    # Store loop on registry to prevent GC
    registry._test_loop_ref = loop
    return registry


class TestRegistryIntegration:
    def test_all_new_tools_registered(self):
        registry = _registry_with_all_tools()
        assert registry.has("self")
        assert registry.has("search")
        assert registry.has("sandbox_control")

    def test_all_tools_in_definitions(self):
        registry = _registry_with_all_tools()
        defs = registry.get_definitions()
        names = {d["name"] for d in defs}
        assert "self" in names
        assert "search" in names
        assert "sandbox_control" in names

    def test_definitions_have_valid_schema(self):
        registry = _registry_with_all_tools()
        for d in registry.get_definitions():
            if d["name"] in ("self", "search", "sandbox_control", "mcp_client"):
                assert "input_schema" in d
                assert "properties" in d["input_schema"]
                assert "action" in d["input_schema"]["properties"]

    @pytest.mark.asyncio
    async def test_self_tool_through_registry(self):
        registry = _registry_with_all_tools()
        result = await registry.execute("self", {"action": "status"})
        data = json.loads(result)
        assert data["max_iterations"] == 10

    @pytest.mark.asyncio
    async def test_self_set_config_through_registry(self):
        registry = _registry_with_all_tools()
        result = await registry.execute("self", {"action": "set_config", "key": "max_iterations", "value": 20})
        data = json.loads(result)
        assert data["new_value"] == 20

    @pytest.mark.asyncio
    async def test_search_glob_through_registry(self):
        registry = _registry_with_all_tools()
        result = await registry.execute("search", {"action": "glob", "pattern": "*.py", "path": "."})
        assert "Error" not in result

    @pytest.mark.asyncio
    async def test_sandbox_control_through_registry(self):
        registry = _registry_with_all_tools()
        result = await registry.execute("sandbox_control", {"action": "start"})
        data = json.loads(result)
        assert data["status"] == "started"


class TestMCPClientToolIntegration:
    """Separate tests for MCPClientTool since it needs a mock manager."""

    def _make_registry_with_mcp(self):
        config = AgentConfig()
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)

        from tests.test_tool_mcp_client import _FakeManager
        mgr = _FakeManager()
        registry.register(MCPClientTool(mcp_manager=mgr))
        return registry, mgr

    @pytest.mark.asyncio
    async def test_mcp_connect_through_registry(self):
        registry, mgr = self._make_registry_with_mcp()
        result = await registry.execute("mcp_client", {
            "action": "connect",
            "server_id": "test-srv",
            "transport": "stdio",
            "command": "echo test",
        })
        data = json.loads(result)
        assert data["status"] == "connected"

    @pytest.mark.asyncio
    async def test_mcp_list_through_registry(self):
        registry, mgr = self._make_registry_with_mcp()
        result = await registry.execute("mcp_client", {"action": "list"})
        data = json.loads(result)
        assert data["count"] == 0
