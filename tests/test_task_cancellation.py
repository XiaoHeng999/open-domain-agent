"""Tests for task cancellation — CancellationToken and graceful loop exit."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent.cancellation import CancellationToken


# ---------------------------------------------------------------------------
# Test 1: CancellationToken basic API
# ---------------------------------------------------------------------------


def test_cancellation_token_not_cancelled_by_default() -> None:
    """New CancellationToken should not be cancelled."""
    token = CancellationToken()
    assert token.is_cancelled is False


def test_cancellation_token_cancel_sets_flag() -> None:
    """Calling cancel() should set is_cancelled to True."""
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled is True


# ---------------------------------------------------------------------------
# Test 2: CancellationToken wraps asyncio.Event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_token_async_wait() -> None:
    """Cancelled token's wait should resolve immediately."""
    token = CancellationToken()
    token.cancel()
    await asyncio.wait_for(token.wait(), timeout=0.1)


@pytest.mark.asyncio
async def test_cancellation_token_uncancelled_wait_times_out() -> None:
    """Un-cancelled token's wait should not resolve."""
    token = CancellationToken()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(token.wait(), timeout=0.05)


# ---------------------------------------------------------------------------
# Test 3: ReActLoop checks token at iteration boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_react_loop_stops_on_cancellation() -> None:
    """ReActLoop should exit cleanly when cancellation token is set."""
    from open_agent.agent.react import ReActLoop, AgentResponse
    from open_agent.registry import ToolRegistry

    registry = ToolRegistry()
    loop = ReActLoop(tool_registry=registry, max_iterations=5)

    # Mock provider that returns tool calls, then we cancel
    call_count = 0

    async def mock_complete_with_tools(messages, tools, **kwargs):
        nonlocal call_count
        call_count += 1
        from open_agent.types import ToolCallResponse, ToolCall
        if call_count == 1:
            return ToolCallResponse(
                text="thinking",
                tool_calls=[ToolCall(id="1", name="test", input={})],
                stop_reason="tool_use",
            )
        return ToolCallResponse(text="done", stop_reason="end_turn")

    provider = MagicMock()
    provider.complete_with_tools = mock_complete_with_tools
    loop._provider = provider

    # Register a no-op tool
    from open_agent.tools.base import FunctionTool
    tool = FunctionTool(
        name="test",
        description="test tool",
        parameters={"type": "object", "properties": {}},
        handler=AsyncMock(return_value="ok"),
    )
    registry.register(tool)

    # Set up cancellation token and cancel after first iteration
    token = CancellationToken()
    loop._cancellation_token = token
    token.cancel()

    from open_agent.routing.router import RoutingDecision
    from open_agent.routing.complexity import ComplexityResult
    from open_agent.routing.domain import DomainRouteResult
    from open_agent.routing.intent import IntentResult

    routing = RoutingDecision(
        complexity=ComplexityResult(complexity="simple", confidence=0.9, method="rule"),
        domain=DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=False),
        intent=IntentResult(intent="general"),
        method="react",
        skip_planning=True,
    )

    response = await loop.run("test input", routing_decision=routing)
    assert isinstance(response, AgentResponse)
    # Should stop early due to cancellation
    assert response.total_steps <= 2


# ---------------------------------------------------------------------------
# Test 4: Loop state is consistent after cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_state_consistent_after_cancellation() -> None:
    """After cancellation, loop state should have valid steps."""
    from open_agent.agent.react import ReActLoop
    from open_agent.registry import ToolRegistry

    registry = ToolRegistry()
    loop = ReActLoop(tool_registry=registry, max_iterations=5)

    call_count = 0

    async def mock_complete_with_tools(messages, tools, **kwargs):
        nonlocal call_count
        call_count += 1
        from open_agent.types import ToolCallResponse, ToolCall
        return ToolCallResponse(
            text="thinking",
            tool_calls=[ToolCall(id="1", name="test", input={})],
            stop_reason="tool_use",
        )

    provider = MagicMock()
    provider.complete_with_tools = mock_complete_with_tools
    loop._provider = provider

    from open_agent.tools.base import FunctionTool
    tool = FunctionTool(
        name="test",
        description="test tool",
        parameters={"type": "object", "properties": {}},
        handler=AsyncMock(return_value="result"),
    )
    registry.register(tool)

    token = CancellationToken()
    loop._cancellation_token = token
    token.cancel()

    from open_agent.routing.router import RoutingDecision
    from open_agent.routing.complexity import ComplexityResult
    from open_agent.routing.domain import DomainRouteResult
    from open_agent.routing.intent import IntentResult

    routing = RoutingDecision(
        complexity=ComplexityResult(complexity="simple", confidence=0.9, method="rule"),
        domain=DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=False),
        intent=IntentResult(intent="general"),
        method="react",
        skip_planning=True,
    )

    response = await loop.run("test input", routing_decision=routing)
    # State should be non-null and have valid answer
    assert response.answer is not None
    assert response.state is not None
