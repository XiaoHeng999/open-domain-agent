"""MCP client tool — dynamically connect/disconnect MCP servers at runtime."""
from __future__ import annotations

import json
from typing import Any

from open_agent.tools.base import Tool


class MCPClientTool(Tool):
    """Runtime MCP server management: connect, disconnect, list."""

    def __init__(self, mcp_manager: Any) -> None:
        self._manager = mcp_manager

    @property
    def name(self) -> str:
        return "mcp_client"

    @property
    def description(self) -> str:
        return "Manage MCP server connections: connect to new servers, disconnect, list active connections."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["connect", "disconnect", "list"],
                    "description": "MCP client action",
                },
                "server_id": {
                    "type": "string",
                    "description": "Server identifier (for connect/disconnect)",
                },
                "transport": {
                    "type": "string",
                    "enum": ["stdio", "http", "sse"],
                    "description": "Transport type (default: stdio)",
                },
                "command": {
                    "type": "string",
                    "description": "Command to start MCP server (for stdio transport)",
                },
                "url": {
                    "type": "string",
                    "description": "Server URL (for http/sse transport)",
                },
            },
            "required": ["action"],
        }

    @property
    def read_only(self) -> bool:
        return False

    @property
    def safety_checks(self) -> list[str]:
        return ["command"]

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        if action == "connect":
            return await self._connect(kwargs)
        if action == "disconnect":
            return await self._disconnect(kwargs)
        if action == "list":
            return await self._list()
        return f"Error: Unknown action: {action}"

    async def _connect(self, kwargs: dict[str, Any]) -> str:
        server_id = kwargs.get("server_id", "")
        if not server_id:
            return "Error: server_id is required for connect"

        if self._manager is None:
            return "Error: MCP manager not configured"

        from open_agent.mcp_integration import ServerConfig, TransportType

        transport_str = kwargs.get("transport", "stdio")
        try:
            transport = TransportType(transport_str)
        except ValueError:
            return f"Error: Invalid transport type: {transport_str}"

        config = ServerConfig(
            server_id=server_id,
            transport=transport,
            command=kwargs.get("command"),
            url=kwargs.get("url"),
        )

        try:
            await self._manager.register_server(config)
            await self._manager.start_server(server_id)
            return json.dumps({"status": "connected", "server_id": server_id})
        except ValueError as exc:
            return f"Error: {exc}"
        except Exception as exc:
            return f"Error: Failed to connect MCP server: {exc}"

    async def _disconnect(self, kwargs: dict[str, Any]) -> str:
        server_id = kwargs.get("server_id", "")
        if not server_id:
            return "Error: server_id is required for disconnect"

        if self._manager is None:
            return "Error: MCP manager not configured"

        try:
            await self._manager.stop_server(server_id)
            return json.dumps({"status": "disconnected", "server_id": server_id})
        except KeyError as exc:
            return f"Error: {exc}"
        except Exception as exc:
            return f"Error: Failed to disconnect: {exc}"

    async def _list(self) -> str:
        if self._manager is None:
            return "Error: MCP manager not configured"

        try:
            servers = self._manager.list_servers()
            return json.dumps({"servers": servers, "count": len(servers)})
        except Exception as exc:
            return f"Error: Failed to list servers: {exc}"
