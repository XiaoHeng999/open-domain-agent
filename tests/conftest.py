"""Shared test fixtures for open_agent tests."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from open_agent.config import PermissionConfig, PermissionMode, SafetyConfig
from open_agent.model import ToolCallResponse
from open_agent.routing.complexity import ComplexityResult
from open_agent.routing.domain import DomainRouteResult
from open_agent.routing.intent import IntentResult
from open_agent.routing.router import RoutingDecision
from open_agent.safety import SafetyManager
from open_agent.safety.hitl import HITLApprovalManager
from open_agent.safety.permission import PermissionGuard
from open_agent.tools.base import FunctionTool
from open_agent.registry import ToolRegistry


def _mock_response(data: dict) -> ToolCallResponse:
    return ToolCallResponse(text=str(data))


@pytest.fixture
def mock_provider():
    """Configurable mock LLM provider with complete_with_tools."""
    provider = AsyncMock()
    provider.complete_with_tools = AsyncMock(
        return_value=_mock_response({"result": "ok"})
    )
    return provider


@pytest.fixture
def tool_registry():
    """ToolRegistry pre-registered with a test tool."""
    registry = ToolRegistry()
    registry.register(
        FunctionTool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
    )
    return registry


@pytest.fixture
def routing_decision():
    """RoutingDecision with sensible defaults."""
    return RoutingDecision(
        complexity=ComplexityResult(
            complexity="simple",
            confidence=0.95,
            method="llm",
        ),
        domain=DomainRouteResult(
            domain="general",
            candidates=["general"],
            routed_as_fallback=True,
        ),
        intent=IntentResult(intent="general_query", slots={"query": "hello"}),
        skip_planning=True,
    )


@pytest.fixture
def safety_manager():
    """SafetyManager configured with strict safety level."""
    return SafetyManager(SafetyConfig(safety_level="strict"))


@pytest.fixture
def permission_guard():
    """PermissionGuard configured in cautious mode with non-interactive HITL."""
    return PermissionGuard(
        config=PermissionConfig(mode=PermissionMode.CAUTIOUS),
        hitl=HITLApprovalManager(interactive=False),
    )
