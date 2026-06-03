"""Test that tool safety_checks declarations are accurate and not misleading."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from open_agent.middleware import (
    MiddlewareContext,
    SafetyMiddleware,
    ExecuteMiddleware,
    build_middleware_chain,
)
from open_agent.tools.self import SelfTool
from open_agent.tools.mcp_client import MCPClientTool


class TestSelfToolNoMisleadingSafetyChecks:
    """SelfTool must not declare safety_checks types that no middleware handles."""

    def test_self_tool_safety_checks_is_empty(self):
        tool = SelfTool()
        assert tool.safety_checks == [], (
            f"SelfTool.safety_checks should be [], got {tool.safety_checks!r}"
        )

    @pytest.mark.asyncio
    async def test_self_tool_passes_safety_middleware_without_false_positive(self):
        """SelfTool should pass through safety middleware without triggering any checks."""
        tool = SelfTool()
        safety_manager = MagicMock()
        context = MiddlewareContext(
            tool=tool,
            params={"action": "status"},
            tool_name="self",
            safety_manager=safety_manager,
        )
        chain = build_middleware_chain([
            SafetyMiddleware(),
            ExecuteMiddleware(),
        ])
        result = await chain(context)
        # safety_manager.check_* should never be called since safety_checks is empty
        safety_manager.check_command.assert_not_called()
        safety_manager.check_url.assert_not_called()
        safety_manager.check_path.assert_not_called()


class TestMCPClientToolSafetyChecks:
    """MCPClientTool must declare ["url"] not ["command"]."""

    def test_mcp_client_safety_checks_is_url(self):
        manager = MagicMock()
        tool = MCPClientTool(manager)
        assert tool.safety_checks == ["url"], (
            f"MCPClientTool.safety_checks should be ['url'], got {tool.safety_checks!r}"
        )

    @pytest.mark.asyncio
    async def test_mcp_client_url_safety_check_fires(self):
        """When url param is present, safety middleware should check_url."""
        manager = MagicMock()
        tool = MCPClientTool(manager)
        safety_manager = MagicMock()
        safety_manager.check_url.return_value = MagicMock(risk_level="safe")
        safety_manager.check_command.return_value = MagicMock(risk_level="safe")

        context = MiddlewareContext(
            tool=tool,
            params={"action": "connect", "server_id": "s1", "url": "http://evil.com"},
            tool_name="mcp_client",
            safety_manager=safety_manager,
        )
        chain = build_middleware_chain([
            SafetyMiddleware(),
            ExecuteMiddleware(),
        ])
        await chain(context)

        # check_url should be called with the URL
        safety_manager.check_url.assert_called_once_with("http://evil.com")
        # check_command should NOT be called
        safety_manager.check_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_mcp_client_no_false_positive_on_command_param(self):
        """The 'command' param (for stdio transport) should NOT trigger safety check."""
        manager = MagicMock()
        tool = MCPClientTool(manager)
        safety_manager = MagicMock()
        safety_manager.check_url.return_value = MagicMock(risk_level="safe")
        safety_manager.check_command.return_value = MagicMock(risk_level="safe")

        context = MiddlewareContext(
            tool=tool,
            params={
                "action": "connect",
                "server_id": "s1",
                "transport": "stdio",
                "command": "npx mcp-server",
            },
            tool_name="mcp_client",
            safety_manager=safety_manager,
        )
        chain = build_middleware_chain([
            SafetyMiddleware(),
            ExecuteMiddleware(),
        ])
        await chain(context)

        # check_url should NOT be called (no url param present)
        safety_manager.check_url.assert_not_called()
        # check_command should NOT be called (safety_checks is ["url"], not ["command"])
        safety_manager.check_command.assert_not_called()
