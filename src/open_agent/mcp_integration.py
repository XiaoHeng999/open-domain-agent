"""MCP integration — transport abstraction, server lifecycle, tool call interface."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from open_agent.base import BaseComponent
from open_agent.decorators import tool_schema
from open_agent.registry import ToolRegistry
from open_agent.trace import SpanKind, Trace

logger = logging.getLogger("open_agent")


class TransportType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


@dataclass
class ServerConfig:
    """Configuration for an MCP server connection."""

    server_id: str
    transport: TransportType = TransportType.STDIO
    command: str | None = None  # for stdio
    url: str | None = None  # for sse/http
    headers: dict[str, str] = field(default_factory=dict)
    health_check_interval: int = 30


@dataclass
class ServerHealth:
    """Health status for an MCP server."""

    healthy: bool = True
    consecutive_failures: int = 0
    max_failures: int = 3
    last_check: float = 0.0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_failures:
            self.healthy = False

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.healthy = True


class MCPTransport:
    """Abstraction over MCP transport — stdio/SSE/HTTP."""

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self._session = None

    async def connect(self) -> None:
        """Establish transport connection."""
        if self.config.transport == TransportType.STDIO:
            # stdio transport via subprocess
            if self.config.command:
                self._process = await asyncio.create_subprocess_exec(
                    *self.config.command.split(),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
        elif self.config.transport in (TransportType.SSE, TransportType.HTTP):
            # HTTP/SSE transport — connection is per-request
            pass

    async def disconnect(self) -> None:
        """Close transport connection."""
        if hasattr(self, "_process") and self._process:
            self._process.terminate()
            await self._process.wait()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool through the transport."""
        # This is a simplified implementation; real MCP SDK integration
        # would use the mcp package's session management
        if hasattr(self, "_process") and self._process:
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": 1,
            })
            self._process.stdin.write((request + "\n").encode())
            await self._process.stdin.drain()
            response_line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=30
            )
            return json.loads(response_line)
        else:
            # HTTP transport — use httpx
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.config.url}/tools/call",
                    json={"name": tool_name, "arguments": arguments},
                    headers=self.config.headers,
                    timeout=30,
                )
                return resp.json()


class MCPServerManager(BaseComponent):
    """Manage MCP server registration, lifecycle, and health."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry
        self._servers: dict[str, ServerConfig] = {}
        self._transports: dict[str, MCPTransport] = {}
        self._health: dict[str, ServerHealth] = {}

    async def register_server(self, config: ServerConfig) -> str:
        """Register an MCP server and discover its tools."""
        if config.server_id in self._servers:
            raise ValueError(f"Server already registered: {config.server_id}")

        self._servers[config.server_id] = config
        self._health[config.server_id] = ServerHealth()
        return config.server_id

    async def start_server(self, server_id: str) -> None:
        """Start an MCP server and register its tools."""
        config = self._servers.get(server_id)
        if not config:
            raise KeyError(f"Server not found: {server_id}")

        transport = MCPTransport(config)
        await transport.connect()
        self._transports[server_id] = transport
        self._health[server_id].last_check = time.time()

    async def stop_server(self, server_id: str) -> None:
        """Stop an MCP server and unregister its tools."""
        transport = self._transports.pop(server_id, None)
        if transport:
            await transport.disconnect()
        count = self._tool_registry.unregister_by_server(server_id)
        logger.info(f"Stopped server {server_id}, unregistered {count} tools")

    async def health_check(self, server_id: str) -> ServerHealth:
        """Check health of an MCP server."""
        health = self._health.get(server_id)
        if not health:
            raise KeyError(f"Server not found: {server_id}")

        transport = self._transports.get(server_id)
        if not transport:
            health.record_failure()
            return health

        try:
            # Simple ping-style health check
            await asyncio.wait_for(transport.call_tool("ping", {}), timeout=5)
            health.record_success()
        except Exception:
            health.record_failure()

        health.last_check = time.time()
        return health

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any], trace: Trace | None = None
    ) -> dict[str, Any]:
        """Unified tool call — route to correct server."""
        entry = self._tool_registry.get(tool_name)
        server_id = entry.server_id

        span = None
        if trace:
            span = trace.create_span(f"tool_call:{tool_name}", kind=SpanKind.TOOL_CALL)
            span.set_attribute("tool_name", tool_name)
            span.set_attribute("arguments", json.dumps(arguments))

        transport = self._transports.get(server_id)
        if not transport:
            if span:
                span.finish(status="error", error=f"Server not connected: {server_id}")
            return {"success": False, "error": f"Server not connected: {server_id}"}

        start = time.time()
        try:
            result = await transport.call_tool(tool_name, arguments)
            latency_ms = (time.time() - start) * 1000

            if span:
                span.set_attribute("latency_ms", latency_ms)
                span.finish()
            self._health.get(server_id, ServerHealth()).record_success()

            return {"success": True, "result": result, "latency_ms": latency_ms}
        except Exception as e:
            if span:
                span.finish(status="error", error=str(e))
            self._health.get(server_id, ServerHealth()).record_failure()
            return {"success": False, "error": str(e)}

    def list_servers(self) -> list[dict[str, Any]]:
        """List all registered servers with health status."""
        result = []
        for sid, config in self._servers.items():
            health = self._health.get(sid, ServerHealth())
            result.append({
                "server_id": sid,
                "transport": config.transport.value,
                "healthy": health.healthy,
                "consecutive_failures": health.consecutive_failures,
            })
        return result


def register_tool_with_schema(
    registry: ToolRegistry,
    handler: Callable[..., Any],
    server_id: str | None = None,
    tags: list[str] | None = None,
) -> None:
    """Register a tool using FunctionTool adapter.

    Accepts handlers decorated with @tool_schema (legacy) or raw handlers
    with explicit schema. Wraps in FunctionTool for Tool ABC compatibility.
    """
    from open_agent.tools.base import FunctionTool

    if hasattr(handler, "_tool_schema"):
        schema = handler._tool_schema
        name = schema["name"]
        description = schema.get("description", "")
        # Convert MCP inputSchema format to Anthropic input_schema format
        parameters = schema.get("inputSchema", schema.get("input_schema", {
            "type": "object", "properties": {},
        }))
    else:
        raise ValueError(
            f"Tool handler must be decorated with @tool_schema or provide a schema. "
            f"Handler: {handler.__name__}"
        )

    tool = FunctionTool(
        name=name,
        description=description,
        parameters=parameters,
        handler=handler,
    )
    tool._server_id = server_id
    registry.register(tool, tags=tags)
