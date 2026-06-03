"""Tests for plan 01: Register All 4 New Tools via scan_builtin_tools(**runtime_kwargs)."""
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


class _FakeRuntime:
    pass


# -- RED: Tests that verify scan_builtin_tools registers the 4 new tools via runtime_kwargs --


class TestScanBuiltinToolsWithRuntimeKwargs:
    """scan_builtin_tools(**runtime_kwargs) should register the 4 new tools."""

    def test_search_tool_registered_without_runtime_kwargs(self):
        """SearchTool should be registered even without runtime kwargs (only needs workspace)."""
        config = AgentConfig()
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)
        assert registry.has("search")

    def test_self_tool_registered_with_runtime_kwargs(self):
        """SelfTool should be registered when react_loop and runtime are provided."""
        config = AgentConfig()
        registry = ToolRegistry()
        loop = _FakeLoop()
        runtime = _FakeRuntime()
        scan_builtin_tools(
            registry, config,
            react_loop=loop, runtime=runtime,
        )
        assert registry.has("self")

    def test_sandbox_control_tool_registered_with_runtime_kwargs(self):
        """SandboxControlTool should be registered when sandbox is provided."""
        config = AgentConfig()
        registry = ToolRegistry()
        scan_builtin_tools(
            registry, config,
            sandbox=MagicMock(on_start=AsyncMock()),
        )
        assert registry.has("sandbox_control")

    def test_mcp_client_tool_registered_with_runtime_kwargs(self):
        """MCPClientTool should be registered when mcp_manager is provided."""
        config = AgentConfig()
        registry = ToolRegistry()
        scan_builtin_tools(
            registry, config,
            mcp_manager=MagicMock(),
        )
        assert registry.has("mcp_client")

    def test_all_4_new_tools_registered_with_all_kwargs(self):
        """All 4 new tools should be registered when all runtime kwargs are provided."""
        config = AgentConfig()
        registry = ToolRegistry()
        loop = _FakeLoop()
        scan_builtin_tools(
            registry, config,
            react_loop=loop,
            runtime=_FakeRuntime(),
            sandbox=MagicMock(on_start=AsyncMock()),
            mcp_manager=MagicMock(),
        )
        assert registry.has("self")
        assert registry.has("search")
        assert registry.has("sandbox_control")
        assert registry.has("mcp_client")

    def test_no_duplicate_registration_when_kwargs_provided(self):
        """SearchTool should not cause duplicate registration with existing search tools."""
        config = AgentConfig()
        registry = ToolRegistry()
        scan_builtin_tools(
            registry, config,
            react_loop=_FakeLoop(),
            runtime=_FakeRuntime(),
            sandbox=MagicMock(on_start=AsyncMock()),
            mcp_manager=MagicMock(),
        )
        # Ensure no ValueError from duplicate registration
        names = [t.name for t in registry.list_tools()]
        assert names.count("search") == 1
        assert names.count("self") == 1
        assert names.count("sandbox_control") == 1
        assert names.count("mcp_client") == 1

    def test_tools_not_registered_without_their_required_kwargs(self):
        """Tools should not be registered if their required kwargs are missing."""
        config = AgentConfig()
        registry = ToolRegistry()
        # Only pass workspace-level info (no runtime kwargs for the 3 tools)
        scan_builtin_tools(registry, config)
        assert not registry.has("self")
        assert not registry.has("sandbox_control")
        assert not registry.has("mcp_client")

    def test_all_4_tools_in_definitions(self):
        """All 4 new tools should appear in get_definitions()."""
        config = AgentConfig()
        registry = ToolRegistry()
        scan_builtin_tools(
            registry, config,
            react_loop=_FakeLoop(),
            runtime=_FakeRuntime(),
            sandbox=MagicMock(on_start=AsyncMock()),
            mcp_manager=MagicMock(),
        )
        defs = registry.get_definitions()
        names = {d["name"] for d in defs}
        assert "self" in names
        assert "search" in names
        assert "sandbox_control" in names
        assert "mcp_client" in names
