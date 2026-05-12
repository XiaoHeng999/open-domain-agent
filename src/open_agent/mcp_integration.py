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


class MCPError(Exception):
    """JSON-RPC 2.0 error from MCP server."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"MCPError({code}): {message}")


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

    _request_counter: int = 0

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self._session = None

    def _next_id(self) -> str:
        """Generate a unique request id (atomic increment)."""
        MCPTransport._request_counter += 1
        return str(MCPTransport._request_counter)

    def _build_request(self, method: str, params: dict[str, Any] | None = None) -> tuple[str, str]:
        """Build a JSON-RPC 2.0 request. Returns (request_id, json_str)."""
        request_id = self._next_id()
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "id": request_id,
        }
        if params is not None:
            payload["params"] = params
        return request_id, json.dumps(payload)

    @staticmethod
    def _parse_response(raw: dict[str, Any], expected_id: str) -> Any:
        """Parse JSON-RPC 2.0 response. Raises MCPError on error response."""
        if "error" in raw:
            err = raw["error"]
            raise MCPError(err.get("code", -1), err.get("message", "Unknown error"))
        resp_id = raw.get("id")
        if resp_id is not None and str(resp_id) != expected_id:
            logger.warning("Response id mismatch: expected %s, got %s", expected_id, resp_id)
            return None
        return raw.get("result")

    async def connect(self) -> None:
        """Establish transport connection."""
        if self.config.transport == TransportType.STDIO:
            if self.config.command:
                self._process = await asyncio.create_subprocess_exec(
                    *self.config.command.split(),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
        elif self.config.transport == TransportType.SSE:
            await self._connect_sse()
        elif self.config.transport == TransportType.HTTP:
            pass

    async def disconnect(self) -> None:
        """Close transport connection."""
        if hasattr(self, "_process") and self._process:
            self._process.terminate()
            await self._process.wait()
        if hasattr(self, "_sse_client") and self._sse_client:
            await self._sse_client.aclose()
            self._sse_client = None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool through the transport."""
        if hasattr(self, "_process") and self._process:
            return await self._call_stdio(tool_name, arguments)
        elif self.config.transport == TransportType.SSE:
            return await self._call_sse(tool_name, arguments)
        else:
            return await self._call_http(tool_name, arguments)

    async def tools_list(self) -> list[dict[str, Any]]:
        """Send tools/list JSON-RPC 2.0 request and return tool list."""
        if hasattr(self, "_process") and self._process:
            request_id, payload = self._build_request("tools/list", {})
            self._process.stdin.write((payload + "\n").encode())
            await self._process.stdin.drain()
            response_line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=30
            )
            raw = json.loads(response_line)
            result = self._parse_response(raw, request_id)
            return result.get("tools", []) if result else []
        elif self.config.transport == TransportType.SSE:
            return await self._tools_list_sse()
        else:
            return await self._tools_list_http()

    async def _call_stdio(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """STDIO transport: send JSON-RPC via subprocess stdin."""
        request_id, payload = self._build_request(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )
        self._process.stdin.write((payload + "\n").encode())
        await self._process.stdin.drain()
        response_line = await asyncio.wait_for(
            self._process.stdout.readline(), timeout=30
        )
        raw = json.loads(response_line)
        return self._parse_response(raw, request_id)

    async def _call_http(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """HTTP transport: send JSON-RPC 2.0 via httpx."""
        import httpx
        request_id, payload = self._build_request(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.config.url,
                content=payload,
                headers={**self.config.headers, "Content-Type": "application/json"},
                timeout=30,
            )
            raw = resp.json()
            return self._parse_response(raw, request_id)

    async def _tools_list_http(self) -> list[dict[str, Any]]:
        """HTTP transport: tools/list request."""
        import httpx
        request_id, payload = self._build_request("tools/list", {})
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.config.url,
                content=payload,
                headers={**self.config.headers, "Content-Type": "application/json"},
                timeout=30,
            )
            raw = resp.json()
            result = self._parse_response(raw, request_id)
            return result.get("tools", []) if result else []

    # ── SSE Transport ──

    async def _connect_sse(self) -> None:
        """SSE transport: establish SSE connection to {url}/sse."""
        import httpx
        self._sse_client = httpx.AsyncClient()
        self._sse_response = None
        self._sse_event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._sse_connected = asyncio.Event()
        self._sse_task = asyncio.create_task(self._sse_listener())

    async def _sse_listener(self) -> None:
        """Background task that reads SSE events."""
        import httpx
        retries = 0
        max_retries = 5
        backoff = 1.0
        while retries < max_retries:
            try:
                async with self._sse_client.stream(
                    "GET", f"{self.config.url}/sse",
                    headers=self.config.headers,
                    timeout=httpx.Timeout(30.0, read=None),
                ) as response:
                    self._sse_connected.set()
                    retries = 0
                    backoff = 1.0
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str:
                                try:
                                    event = json.loads(data_str)
                                    await self._sse_event_queue.put(event)
                                except json.JSONDecodeError:
                                    pass
            except Exception as e:
                logger.warning("SSE connection error: %s, retry %d/%d", e, retries + 1, max_retries)
                retries += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
        logger.error("SSE connection failed after %d retries", max_retries)
        self._sse_connected.clear()

    async def _call_sse(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """SSE transport: POST JSON-RPC to {url}/messages, read response from SSE stream."""
        import httpx
        request_id, payload = self._build_request(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )
        resp = await self._sse_client.post(
            f"{self.config.url}/messages",
            content=payload,
            headers={**self.config.headers, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        # Wait for response via SSE event stream (match by request id)
        try:
            event = await asyncio.wait_for(self._sse_event_queue.get(), timeout=30)
            return self._parse_response(event, request_id)
        except asyncio.TimeoutError:
            raise MCPError(-1, "SSE response timeout")

    async def _tools_list_sse(self) -> list[dict[str, Any]]:
        """SSE transport: tools/list request."""
        import httpx
        request_id, payload = self._build_request("tools/list", {})
        resp = await self._sse_client.post(
            f"{self.config.url}/messages",
            content=payload,
            headers={**self.config.headers, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        try:
            event = await asyncio.wait_for(self._sse_event_queue.get(), timeout=30)
            result = self._parse_response(event, request_id)
            return result.get("tools", []) if result else []
        except asyncio.TimeoutError:
            raise MCPError(-1, "SSE tools/list response timeout")


class MCPServerManager(BaseComponent):
    """Manage MCP server registration, lifecycle, and health."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry
        self._servers: dict[str, ServerConfig] = {}
        self._transports: dict[str, MCPTransport] = {}
        self._health: dict[str, ServerHealth] = {}
        self._discovery_failed: set[str] = set()

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
        await self._discover_tools(server_id)

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

        was_unhealthy = not health.healthy
        try:
            await asyncio.wait_for(transport.call_tool("ping", {}), timeout=5)
            health.record_success()
        except Exception:
            health.record_failure()

        # Re-discover tools on recovery
        if was_unhealthy and health.healthy:
            await self._discover_tools(server_id)

        health.last_check = time.time()
        return health

    async def _discover_tools(self, server_id: str) -> None:
        """Discover tools from an MCP server and register them."""
        transport = self._transports.get(server_id)
        if not transport:
            return

        try:
            tools = await asyncio.wait_for(transport.tools_list(), timeout=30)
            if not tools:
                logger.info("No tools discovered from server %s", server_id)
                self._discovery_failed.discard(server_id)
                return

            for tool_info in tools:
                name = tool_info.get("name", "")
                if not name:
                    continue
                if self._tool_registry.has(name):
                    logger.warning(
                        "Tool name conflict: %s from server %s, skipping", name, server_id
                    )
                    continue
                description = tool_info.get("description", "")
                raw_schema = tool_info.get("inputSchema", tool_info.get("input_schema", {
                    "type": "object", "properties": {},
                }))
                parameters = _convert_mcp_schema(raw_schema)

                from open_agent.tools.base import FunctionTool
                _mgr = self
                _sid = server_id
                _tn = name
                def _make_handler(mgr, s_id, t_name):
                    async def _handler(**kwargs):
                        return await mgr.call_tool(t_name, kwargs)
                    return _handler
                ft = FunctionTool(
                    name=name,
                    description=description,
                    parameters=parameters,
                    handler=_make_handler(self, server_id, name),
                )
                ft._server_id = server_id
                self._tool_registry.register(ft)

            self._discovery_failed.discard(server_id)
            logger.info(
                "Discovered %d tools from server %s", len(tools), server_id
            )
        except asyncio.TimeoutError:
            logger.warning("Tool discovery timeout for server %s", server_id)
            self._discovery_failed.add(server_id)
        except Exception as e:
            logger.warning("Tool discovery failed for server %s: %s", server_id, e)
            self._discovery_failed.add(server_id)

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
        raw_schema = schema.get("inputSchema", schema.get("input_schema", {
            "type": "object", "properties": {},
        }))
        parameters = _convert_mcp_schema(raw_schema)
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


def _convert_mcp_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively convert MCP inputSchema to Anthropic-compatible input_schema.

    Handles $defs/definitions, anyOf/oneOf, nested properties.
    """
    if not isinstance(input_schema, dict):
        return input_schema

    result: dict[str, Any] = {}
    for key, value in input_schema.items():
        # Normalize $defs → definitions if present (Anthropic format)
        if key == "$defs":
            result["definitions"] = _convert_mcp_schema(value) if isinstance(value, dict) else value
        elif key in ("properties", "definitions") and isinstance(value, dict):
            result[key] = {k: _convert_mcp_schema(v) for k, v in value.items()}
        elif key in ("anyOf", "oneOf", "allOf") and isinstance(value, list):
            result[key] = [_convert_mcp_schema(item) for item in value]
        elif key == "items" and isinstance(value, dict):
            result[key] = _convert_mcp_schema(value)
        elif key == "additionalProperties" and isinstance(value, dict):
            result[key] = _convert_mcp_schema(value)
        elif isinstance(value, dict):
            result[key] = _convert_mcp_schema(value)
        else:
            result[key] = value
    return result
