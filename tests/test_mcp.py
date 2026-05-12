"""Tests for MCP integration — JSON-RPC 2.0, transport, tool discovery, config."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent.decorators import tool_schema
from open_agent.mcp_integration import (
    MCPError,
    MCPTransport,
    MCPServerManager,
    ServerConfig,
    ServerHealth,
    TransportType,
    _convert_mcp_schema,
    register_tool_with_schema,
)
from open_agent.registry import ToolRegistry


# ── ServerHealth ──


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


# ── JSON-RPC 2.0 ──


class TestJSONRPC:
    def test_unique_request_ids(self):
        config = ServerConfig(server_id="test", transport=TransportType.HTTP, url="http://localhost")
        t1 = MCPTransport(config)
        t2 = MCPTransport(config)
        id1a, _ = t1._build_request("tools/call")
        id1b, _ = t1._build_request("tools/call")
        id2a, _ = t2._build_request("tools/call")
        assert id1a != id1b
        assert id1b != id2a

    def test_build_request_format(self):
        config = ServerConfig(server_id="test", transport=TransportType.HTTP, url="http://localhost")
        t = MCPTransport(config)
        rid, payload_str = t._build_request("tools/list", {})
        payload = json.loads(payload_str)
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "tools/list"
        assert payload["id"] == rid
        assert payload["params"] == {}

    def test_parse_response_success(self):
        config = ServerConfig(server_id="test", transport=TransportType.HTTP, url="http://localhost")
        t = MCPTransport(config)
        result = t._parse_response({"jsonrpc": "2.0", "result": {"tools": []}, "id": "42"}, "42")
        assert result == {"tools": []}

    def test_parse_response_error(self):
        config = ServerConfig(server_id="test", transport=TransportType.HTTP, url="http://localhost")
        t = MCPTransport(config)
        with pytest.raises(MCPError) as exc_info:
            t._parse_response(
                {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": "3"},
                "3",
            )
        assert exc_info.value.code == -32600
        assert "Invalid Request" in exc_info.value.message

    def test_parse_response_id_mismatch(self):
        config = ServerConfig(server_id="test", transport=TransportType.HTTP, url="http://localhost")
        t = MCPTransport(config)
        result = t._parse_response({"jsonrpc": "2.0", "result": "data", "id": "99"}, "1")
        assert result is None

    def test_parse_response_no_id(self):
        config = ServerConfig(server_id="test", transport=TransportType.HTTP, url="http://localhost")
        t = MCPTransport(config)
        result = t._parse_response({"jsonrpc": "2.0", "result": "data"}, "1")
        assert result == "data"


# ── MCPError ──


class TestMCPError:
    def test_error_attributes(self):
        err = MCPError(-32600, "Invalid Request")
        assert err.code == -32600
        assert err.message == "Invalid Request"
        assert "MCPError(-32600)" in str(err)


# ── STDIO Transport ──


class TestSTDIOTransport:
    @pytest.mark.asyncio
    async def test_stdio_call_tool_uses_unique_id(self):
        config = ServerConfig(
            server_id="stdio-test",
            transport=TransportType.STDIO,
            command="echo test",
        )
        transport = MCPTransport(config)

        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()

        # Capture the written request to echo back matching id
        written_payload = {}

        def mock_write(data):
            parsed = json.loads(data.decode().strip())
            written_payload.update(parsed)

        mock_process.stdin.write = mock_write
        mock_process.stdin.drain = AsyncMock()

        async def mock_readline():
            rid = written_payload.get("id", "1")
            return (json.dumps({"jsonrpc": "2.0", "result": {"content": "ok"}, "id": rid}) + "\n").encode()

        mock_process.stdout.readline = mock_readline
        transport._process = mock_process

        result = await transport.call_tool("my_tool", {"arg": "val"})
        assert result == {"content": "ok"}

        # Verify the written request is JSON-RPC 2.0 format
        assert written_payload["jsonrpc"] == "2.0"
        assert written_payload["method"] == "tools/call"
        assert written_payload["params"]["name"] == "my_tool"
        assert "id" in written_payload


# ── HTTP Transport ──


class TestHTTPTransport:
    @pytest.mark.asyncio
    async def test_http_call_tool_jsonrpc_format(self):
        config = ServerConfig(
            server_id="http-test",
            transport=TransportType.HTTP,
            url="http://localhost:8080/mcp",
        )
        transport = MCPTransport(config)

        captured_payload = {}

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                captured_payload["url"] = url
                captured_payload["content"] = kwargs.get("content")
                captured_payload["headers"] = kwargs.get("headers")
                # Echo back the request id in the response
                req = json.loads(kwargs.get("content", "{}"))
                return MagicMock(json=lambda: {
                    "jsonrpc": "2.0",
                    "result": "done",
                    "id": req.get("id"),
                })

        with patch("httpx.AsyncClient", MockAsyncClient):
            result = await transport.call_tool("query", {"q": "test"})

        assert result == "done"
        assert captured_payload["url"] == "http://localhost:8080/mcp"
        payload = json.loads(captured_payload["content"])
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "query"
        assert captured_payload["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_http_tools_list(self):
        config = ServerConfig(
            server_id="http-test",
            transport=TransportType.HTTP,
            url="http://localhost:8080/mcp",
        )
        transport = MCPTransport(config)

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                req = json.loads(kwargs.get("content", "{}"))
                return MagicMock(json=lambda: {
                    "jsonrpc": "2.0",
                    "result": {"tools": [{"name": "tool1"}]},
                    "id": req.get("id"),
                })

        with patch("httpx.AsyncClient", MockAsyncClient):
            tools = await transport.tools_list()

        assert len(tools) == 1
        assert tools[0]["name"] == "tool1"


# ── SSE Transport ──


class TestSSETransport:
    @pytest.mark.asyncio
    async def test_sse_call_tool(self):
        config = ServerConfig(
            server_id="sse-test",
            transport=TransportType.SSE,
            url="http://localhost:9090",
        )
        transport = MCPTransport(config)

        mock_sse_client = AsyncMock()
        mock_post_response = MagicMock()
        mock_post_response.raise_for_status = MagicMock()
        mock_sse_client.post = AsyncMock(return_value=mock_post_response)
        transport._sse_client = mock_sse_client
        transport._sse_event_queue = asyncio.Queue()
        transport._sse_connected = asyncio.Event()
        transport._sse_connected.set()

        # Enqueue a response event
        request_id_holder = {}
        original_build = transport._build_request

        def capture_build(method, params=None):
            rid, payload = original_build(method, params)
            request_id_holder["id"] = rid
            return rid, payload

        transport._build_request = capture_build

        # Put matching response in queue before calling
        async def enqueue_response():
            await asyncio.sleep(0.01)
            await transport._sse_event_queue.put({
                "jsonrpc": "2.0",
                "result": {"content": "sse_result"},
                "id": request_id_holder.get("id", "unknown"),
            })

        asyncio.create_task(enqueue_response())
        result = await transport._call_sse("tool1", {"a": 1})
        assert result == {"content": "sse_result"}


# ── MCP Registration ──


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


# ── Tool Schema Registration ──


class TestToolSchemaRegistration:
    def test_schema_required(self):
        registry = ToolRegistry()
        handler = lambda: None
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


# ── Tool Discovery ──


class TestToolDiscovery:
    @pytest.mark.asyncio
    async def test_discover_tools_registers_to_registry(self):
        registry = ToolRegistry()
        mgr = MCPServerManager(registry)
        config = ServerConfig(
            server_id="disc-test",
            transport=TransportType.HTTP,
            url="http://localhost/mcp",
        )
        await mgr.register_server(config)

        # Mock transport with tools_list
        mock_transport = AsyncMock()
        mock_transport.tools_list.return_value = [
            {
                "name": "db_query",
                "description": "Query the database",
                "inputSchema": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                },
            },
        ]
        mgr._transports["disc-test"] = mock_transport

        await mgr._discover_tools("disc-test")
        assert registry.has("db_query")
        tool = registry.get("db_query")
        assert getattr(tool, "_server_id") == "disc-test"

    @pytest.mark.asyncio
    async def test_discover_tools_empty_list(self):
        registry = ToolRegistry()
        mgr = MCPServerManager(registry)
        config = ServerConfig(server_id="empty-disc", transport=TransportType.HTTP, url="http://localhost")
        await mgr.register_server(config)

        mock_transport = AsyncMock()
        mock_transport.tools_list.return_value = []
        mgr._transports["empty-disc"] = mock_transport

        await mgr._discover_tools("empty-disc")
        assert len(registry) == 0

    @pytest.mark.asyncio
    async def test_discover_tools_timeout(self):
        registry = ToolRegistry()
        mgr = MCPServerManager(registry)
        config = ServerConfig(server_id="timeout-disc", transport=TransportType.HTTP, url="http://localhost")
        await mgr.register_server(config)

        mock_transport = AsyncMock()
        mock_transport.tools_list.side_effect = asyncio.TimeoutError()
        mgr._transports["timeout-disc"] = mock_transport

        await mgr._discover_tools("timeout-disc")
        assert "timeout-disc" in mgr._discovery_failed

    @pytest.mark.asyncio
    async def test_discover_tools_name_conflict(self):
        registry = ToolRegistry()

        # Pre-register a tool with the same name
        @tool_schema(name="conflict_tool")
        def conflict(x: str) -> str:
            ...

        register_tool_with_schema(registry, conflict, server_id="s0")

        mgr = MCPServerManager(registry)
        config = ServerConfig(server_id="s1", transport=TransportType.HTTP, url="http://localhost")
        await mgr.register_server(config)

        mock_transport = AsyncMock()
        mock_transport.tools_list.return_value = [
            {"name": "conflict_tool", "description": "Another one", "inputSchema": {"type": "object", "properties": {}}},
        ]
        mgr._transports["s1"] = mock_transport

        await mgr._discover_tools("s1")
        # Original tool still exists, no duplicate
        assert len(registry) == 1


# ── Schema Conversion ──


class TestSchemaConversion:
    def test_simple_schema_passthrough(self):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = _convert_mcp_schema(schema)
        assert result == schema

    def test_defs_to_definitions(self):
        schema = {
            "type": "object",
            "$defs": {"Address": {"type": "object", "properties": {"city": {"type": "string"}}}},
            "properties": {"home": {"$ref": "#/$defs/Address"}},
        }
        result = _convert_mcp_schema(schema)
        assert "definitions" in result
        assert "Address" in result["definitions"]

    def test_anyof_conversion(self):
        schema = {
            "anyOf": [
                {"type": "string"},
                {"type": "integer"},
            ]
        }
        result = _convert_mcp_schema(schema)
        assert len(result["anyOf"]) == 2

    def test_nested_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                    },
                },
            },
        }
        result = _convert_mcp_schema(schema)
        assert "city" in result["properties"]["address"]["properties"]

    def test_items_conversion(self):
        schema = {
            "type": "array",
            "items": {"type": "object", "properties": {"id": {"type": "integer"}}},
        }
        result = _convert_mcp_schema(schema)
        assert "properties" in result["items"]

    def test_deeply_nested(self):
        schema = {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "anyOf": [
                                {"type": "string"},
                                {
                                    "type": "object",
                                    "properties": {"deep": {"type": "boolean"}},
                                },
                            ],
                        },
                    },
                },
            },
        }
        result = _convert_mcp_schema(schema)
        inner = result["properties"]["level1"]["properties"]["level2"]["anyOf"][1]
        assert "deep" in inner["properties"]


# ── MCP Config ──


class TestMCPConfig:
    def test_load_config_with_mcp(self):
        from open_agent.config import AgentConfig

        config = AgentConfig.model_validate({
            "mcp": {
                "servers": [
                    {"server_id": "s1", "transport": "stdio", "command": "python server.py"},
                    {"server_id": "s2", "transport": "http", "url": "http://localhost:8080/mcp"},
                ],
                "connect_timeout": 15,
                "tool_discovery_timeout": 45,
            }
        })
        assert len(config.mcp.servers) == 2
        assert config.mcp.connect_timeout == 15
        assert config.mcp.servers[0].server_id == "s1"
        assert config.mcp.servers[0].command == "python server.py"
        assert config.mcp.servers[1].url == "http://localhost:8080/mcp"

    def test_load_config_without_mcp(self):
        from open_agent.config import AgentConfig

        config = AgentConfig()
        assert config.mcp.servers == []
        assert config.mcp.connect_timeout == 10

    def test_config_validation_stdio_requires_command(self):
        from open_agent.config import AgentConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="stdio transport requires 'command'"):
            AgentConfig.model_validate({
                "mcp": {
                    "servers": [{"server_id": "s1", "transport": "stdio"}],
                }
            })

    def test_config_validation_http_requires_url(self):
        from open_agent.config import AgentConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="http transport requires 'url'"):
            AgentConfig.model_validate({
                "mcp": {
                    "servers": [{"server_id": "s2", "transport": "http"}],
                }
            })

    def test_config_validation_sse_requires_url(self):
        from open_agent.config import AgentConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="sse transport requires 'url'"):
            AgentConfig.model_validate({
                "mcp": {
                    "servers": [{"server_id": "s3", "transport": "sse"}],
                }
            })

    def test_env_override_mcp_servers(self):
        import os
        from open_agent.config import load_config

        env_val = json.dumps([
            {"server_id": "env-srv", "transport": "stdio", "command": "env_cmd"},
        ])
        with patch.dict(os.environ, {"OPEN_AGENT_MCP_SERVERS": env_val}):
            config = load_config()
            assert len(config.mcp.servers) == 1
            assert config.mcp.servers[0].server_id == "env-srv"


# ── Runtime MCP Integration ──


class TestRuntimeMCPIntegration:
    @pytest.mark.asyncio
    async def test_runtime_on_start_initializes_mcp(self):
        from open_agent.config import AgentConfig

        config = AgentConfig.model_validate({
            "model": {"provider": "openai", "name": "gpt-4o"},
            "mcp": {
                "servers": [
                    {"server_id": "test-srv", "transport": "stdio", "command": "echo hello"},
                ],
            },
        })

        # We mock the provider to avoid API calls
        with patch("open_agent.model.ProviderFactory.create") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.on_start = AsyncMock()
            mock_provider.complete_with_tools = AsyncMock(return_value=MagicMock())
            mock_provider.complete = AsyncMock(return_value="test")
            mock_provider.complete_structured = AsyncMock(return_value={})
            mock_factory.return_value = mock_provider

            from open_agent.runtime import AgentRuntime
            runtime = AgentRuntime(config)

            # Mock MCP server startup
            with patch.object(MCPServerManager, "start_server", new_callable=AsyncMock):
                await runtime.on_start()

                assert runtime._mcp_manager is not None
                assert len(runtime._mcp_manager.list_servers()) == 1

                await runtime.on_stop()

    @pytest.mark.asyncio
    async def test_runtime_on_stop_cleans_mcp(self):
        from open_agent.config import AgentConfig

        config = AgentConfig.model_validate({
            "model": {"provider": "openai", "name": "gpt-4o"},
            "mcp": {
                "servers": [
                    {"server_id": "s1", "transport": "stdio", "command": "echo"},
                ],
            },
        })

        with patch("open_agent.model.ProviderFactory.create") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.on_start = AsyncMock()
            mock_factory.return_value = mock_provider

            from open_agent.runtime import AgentRuntime
            runtime = AgentRuntime(config)

            with patch.object(MCPServerManager, "start_server", new_callable=AsyncMock):
                await runtime.on_start()
                assert runtime._mcp_manager is not None

            with patch.object(MCPServerManager, "stop_server", new_callable=AsyncMock) as mock_stop:
                await runtime.on_stop()
                mock_stop.assert_called_once_with("s1")

    @pytest.mark.asyncio
    async def test_runtime_no_mcp_when_empty_config(self):
        from open_agent.config import AgentConfig

        config = AgentConfig.model_validate({"model": {"provider": "openai", "name": "gpt-4o"}})

        with patch("open_agent.model.ProviderFactory.create") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.on_start = AsyncMock()
            mock_factory.return_value = mock_provider

            from open_agent.runtime import AgentRuntime
            runtime = AgentRuntime(config)
            await runtime.on_start()

            assert runtime._mcp_manager is None
            await runtime.on_stop()


# ── Unified Tool Definitions ──


class TestUnifiedToolDefinitions:
    def test_mcp_tools_in_get_definitions(self):
        registry = ToolRegistry()
        mgr = MCPServerManager(registry)
        config = ServerConfig(server_id="def-test", transport=TransportType.HTTP, url="http://localhost")
        asyncio.get_event_loop().run_until_complete(mgr.register_server(config))

        mock_transport = AsyncMock()
        mock_transport.tools_list.return_value = [
            {
                "name": "db_query",
                "description": "Query DB",
                "inputSchema": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                },
            },
        ]
        mgr._transports["def-test"] = mock_transport
        asyncio.get_event_loop().run_until_complete(mgr._discover_tools("def-test"))

        defs = registry.get_definitions()
        assert len(defs) >= 1
        db_def = next(d for d in defs if d["name"] == "db_query")
        assert "input_schema" in db_def
        assert "sql" in db_def["input_schema"]["properties"]

    def test_mcp_tool_unified_format(self):
        """MCP tools output same Anthropic tool_use format as built-in tools."""
        registry = ToolRegistry()
        mgr = MCPServerManager(registry)
        config = ServerConfig(server_id="fmt-test", transport=TransportType.HTTP, url="http://localhost")
        asyncio.get_event_loop().run_until_complete(mgr.register_server(config))

        mock_transport = AsyncMock()
        mock_transport.tools_list.return_value = [
            {
                "name": "remote_fn",
                "description": "A remote function",
                "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}}},
            },
        ]
        mgr._transports["fmt-test"] = mock_transport
        asyncio.get_event_loop().run_until_complete(mgr._discover_tools("fmt-test"))

        defs = registry.get_definitions()
        remote_def = next(d for d in defs if d["name"] == "remote_fn")
        # Same format as built-in tools: name, description, input_schema
        assert set(remote_def.keys()) == {"name", "description", "input_schema"}
