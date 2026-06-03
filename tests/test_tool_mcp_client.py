"""Tests for MCPClientTool — runtime MCP server management."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from open_agent.tools.mcp_client import MCPClientTool


class _FakeManager:
    def __init__(self):
        self._servers: dict = {}

    async def register_server(self, config):
        if config.server_id in self._servers:
            raise ValueError(f"Server already registered: {config.server_id}")
        self._servers[config.server_id] = config

    async def start_server(self, server_id):
        if server_id not in self._servers:
            raise KeyError(f"Server not found: {server_id}")

    async def stop_server(self, server_id):
        if server_id not in self._servers:
            raise KeyError(f"Server not found: {server_id}")
        del self._servers[server_id]

    def list_servers(self):
        return [{"server_id": sid, "status": "connected", "tools_count": 1} for sid in self._servers]


class TestMCPClientTool:
    def test_name_and_description(self):
        tool = MCPClientTool(mcp_manager=MagicMock())
        assert tool.name == "mcp_client"
        assert tool.description

    def test_schema(self):
        tool = MCPClientTool(mcp_manager=MagicMock())
        schema = tool.to_schema()
        assert schema["name"] == "mcp_client"
        assert "input_schema" in schema

    def test_safety_checks(self):
        tool = MCPClientTool(mcp_manager=MagicMock())
        assert tool.safety_checks == ["url"]
        assert tool.read_only is False

    @pytest.mark.asyncio
    async def test_connect_stdio(self):
        mgr = _FakeManager()
        tool = MCPClientTool(mcp_manager=mgr)
        result = await tool.execute(
            action="connect",
            server_id="my-server",
            transport="stdio",
            command="npx my-mcp-server",
        )
        data = json.loads(result)
        assert data["status"] == "connected"
        assert data["server_id"] == "my-server"

    @pytest.mark.asyncio
    async def test_connect_http(self):
        mgr = _FakeManager()
        tool = MCPClientTool(mcp_manager=mgr)
        result = await tool.execute(
            action="connect",
            server_id="remote-server",
            transport="http",
            url="http://localhost:3000/mcp",
        )
        data = json.loads(result)
        assert data["status"] == "connected"

    @pytest.mark.asyncio
    async def test_connect_duplicate(self):
        mgr = _FakeManager()
        tool = MCPClientTool(mcp_manager=mgr)
        await tool.execute(action="connect", server_id="dup", transport="stdio", command="cmd")
        result = await tool.execute(action="connect", server_id="dup", transport="stdio", command="cmd")
        assert "already registered" in result.lower()

    @pytest.mark.asyncio
    async def test_connect_missing_server_id(self):
        tool = MCPClientTool(mcp_manager=_FakeManager())
        result = await tool.execute(action="connect", transport="stdio")
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        mgr = _FakeManager()
        tool = MCPClientTool(mcp_manager=mgr)
        await tool.execute(action="connect", server_id="my-server", transport="stdio", command="cmd")
        result = await tool.execute(action="disconnect", server_id="my-server")
        data = json.loads(result)
        assert data["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_disconnect_not_found(self):
        mgr = _FakeManager()
        tool = MCPClientTool(mcp_manager=mgr)
        result = await tool.execute(action="disconnect", server_id="nonexistent")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_disconnect_missing_server_id(self):
        tool = MCPClientTool(mcp_manager=_FakeManager())
        result = await tool.execute(action="disconnect")
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_list(self):
        mgr = _FakeManager()
        tool = MCPClientTool(mcp_manager=mgr)
        await tool.execute(action="connect", server_id="srv1", transport="stdio", command="cmd")
        result = await tool.execute(action="list")
        data = json.loads(result)
        assert data["count"] == 1
        assert data["servers"][0]["server_id"] == "srv1"

    @pytest.mark.asyncio
    async def test_list_empty(self):
        mgr = _FakeManager()
        tool = MCPClientTool(mcp_manager=mgr)
        result = await tool.execute(action="list")
        data = json.loads(result)
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = MCPClientTool(mcp_manager=MagicMock())
        result = await tool.execute(action="unknown")
        assert "Unknown action" in result

    @pytest.mark.asyncio
    async def test_no_manager(self):
        tool = MCPClientTool(mcp_manager=None)
        result = await tool.execute(action="list")
        assert "not configured" in result.lower()
