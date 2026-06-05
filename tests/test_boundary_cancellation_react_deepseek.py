"""Boundary tests for Cancellation, ReAct loop, and DeepSeek provider."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent.cancellation import CancellationToken
from open_agent.routing.router import RoutingDecision
from open_agent.routing.complexity import ComplexityResult
from open_agent.routing.domain import DomainRouteResult
from open_agent.routing.intent import IntentResult


def _make_routing():
    return RoutingDecision(
        complexity=ComplexityResult(complexity="simple", confidence=0.9, method="llm"),
        domain=DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=False),
        intent=IntentResult(intent="general"),
        method="react",
        skip_planning=True,
    )


# ===========================================================================
# Cancellation boundary tests
# ===========================================================================


@pytest.mark.asyncio
async def test_nested_cancellation_no_deadlock() -> None:
    """Multiple cancellation calls from nested contexts should not deadlock."""
    token = CancellationToken()

    async def inner():
        token.cancel()
        assert token.is_cancelled

    async def outer():
        token.cancel()
        await inner()

    await outer()
    assert token.is_cancelled


@pytest.mark.asyncio
async def test_cancel_then_immediate_use() -> None:
    """CancellationToken can be checked immediately after cancel without async yield."""
    token = CancellationToken()
    token.cancel()
    # Immediate synchronous check should work
    assert token.is_cancelled is True
    # Async wait should resolve immediately
    await asyncio.wait_for(token.wait(), timeout=0.01)


@pytest.mark.asyncio
async def test_cancel_idle_state_no_side_effects() -> None:
    """Cancelling an idle token (no pending operations) should not raise."""
    token = CancellationToken()
    token.cancel()
    # Second cancel should be idempotent
    token.cancel()
    assert token.is_cancelled is True


# ===========================================================================
# ReAct boundary tests
# ===========================================================================


@pytest.mark.asyncio
async def test_react_max_iterations_exits_gracefully() -> None:
    """ReActLoop should exit when max_iterations is reached."""
    from open_agent.agent.react import ReActLoop
    from open_agent.registry import ToolRegistry
    from open_agent.types import ToolCallResponse, ToolCall
    from open_agent.tools.base import FunctionTool

    registry = ToolRegistry()
    loop = ReActLoop(tool_registry=registry, max_iterations=2)

    call_count = 0

    async def always_tool_call(messages, tools, **kwargs):
        nonlocal call_count
        call_count += 1
        return ToolCallResponse(
            text="thinking",
            tool_calls=[ToolCall(id=str(call_count), name="spin", input={})],
            stop_reason="tool_use",
        )

    provider = MagicMock()
    provider.complete_with_tools = always_tool_call
    loop._provider = provider

    registry.register(FunctionTool(
        name="spin",
        description="Spin tool",
        parameters={"type": "object", "properties": {}},
        handler=AsyncMock(return_value="spun"),
    ))

    response = await loop.run("keep going", routing_decision=_make_routing())
    assert response.total_steps <= 2


@pytest.mark.asyncio
async def test_react_tool_error_recovery() -> None:
    """ReActLoop should continue when a tool raises an error."""
    from open_agent.agent.react import ReActLoop
    from open_agent.registry import ToolRegistry
    from open_agent.types import ToolCallResponse, ToolCall
    from open_agent.tools.base import FunctionTool

    registry = ToolRegistry()
    loop = ReActLoop(tool_registry=registry, max_iterations=5)

    call_count = 0

    async def mock_complete(messages, tools, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ToolCallResponse(
                text="using tool",
                tool_calls=[ToolCall(id="1", name="fail_tool", input={})],
                stop_reason="tool_use",
            )
        return ToolCallResponse(text="Recovered", stop_reason="end_turn")

    provider = MagicMock()
    provider.complete_with_tools = mock_complete
    loop._provider = provider

    async def failing_handler(**kwargs):
        raise RuntimeError("Tool failed!")

    registry.register(FunctionTool(
        name="fail_tool",
        description="Fails",
        parameters={"type": "object", "properties": {}},
        handler=failing_handler,
    ))

    response = await loop.run("use failing tool", routing_decision=_make_routing())
    # Loop should have recovered and continued
    assert call_count >= 2
    assert "Recovered" in response.answer


@pytest.mark.asyncio
async def test_react_empty_tool_response() -> None:
    """ReActLoop should handle tool returning empty string."""
    from open_agent.agent.react import ReActLoop
    from open_agent.registry import ToolRegistry
    from open_agent.types import ToolCallResponse, ToolCall
    from open_agent.tools.base import FunctionTool

    registry = ToolRegistry()
    loop = ReActLoop(tool_registry=registry, max_iterations=5)

    call_count = 0

    async def mock_complete(messages, tools, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ToolCallResponse(
                text="calling empty tool",
                tool_calls=[ToolCall(id="1", name="empty_tool", input={})],
                stop_reason="tool_use",
            )
        return ToolCallResponse(text="Final answer: nothing", stop_reason="end_turn")

    provider = MagicMock()
    provider.complete_with_tools = mock_complete
    loop._provider = provider

    registry.register(FunctionTool(
        name="empty_tool",
        description="Returns empty",
        parameters={"type": "object", "properties": {}},
        handler=AsyncMock(return_value=""),
    ))

    response = await loop.run("use empty tool", routing_decision=_make_routing())
    assert call_count >= 2


# ===========================================================================
# DeepSeek provider boundary tests
# ===========================================================================


@pytest.mark.asyncio
async def test_deepseek_api_error_propagates() -> None:
    """DeepSeek provider should propagate API errors."""
    from open_agent.config import ModelConfig
    from open_agent.model import DeepSeekProvider

    provider = DeepSeekProvider(ModelConfig(provider="deepseek", name="deepseek-chat"))
    assert provider.config.base_url == "https://api.deepseek.com/v1"

    # Mock client that raises an error
    provider._client = MagicMock()
    provider._client.chat.completions.create = AsyncMock(
        side_effect=Exception("API error: 500 Internal Server Error")
    )

    with pytest.raises(Exception, match="API error: 500"):
        await provider.complete_with_tools(
            messages=[{"role": "user", "content": "hello"}],
            tool_definitions=[],
        )


@pytest.mark.asyncio
async def test_deepseek_rate_limit_with_retry() -> None:
    """DeepSeek provider should handle rate limit (429) via tenacity retry."""
    from open_agent.config import ModelConfig
    from open_agent.model import DeepSeekProvider

    provider = DeepSeekProvider(ModelConfig(provider="deepseek", name="deepseek-chat"))

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            exc = Exception("429 Rate limit exceeded")
            exc.response = MagicMock(status_code=429)
            raise exc
        # Success on 3rd call
        mock_msg = MagicMock()
        mock_msg.content = "retry success"
        mock_msg.tool_calls = None
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = mock_msg
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        return mock_response

    provider._client = MagicMock()
    provider._client.chat.completions.create = mock_create

    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "hello"}],
        tool_definitions=[],
    )
    assert result.text == "retry success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_deepseek_timeout_propagates() -> None:
    """DeepSeek provider should propagate timeout errors."""
    from open_agent.config import ModelConfig
    from open_agent.model import DeepSeekProvider

    provider = DeepSeekProvider(ModelConfig(provider="deepseek", name="deepseek-chat"))

    import asyncio as _asyncio

    async def mock_timeout(**kwargs):
        raise _asyncio.TimeoutError("Request timed out")

    provider._client = MagicMock()
    provider._client.chat.completions.create = mock_timeout

    with pytest.raises(TimeoutError):
        await provider.complete_with_tools(
            messages=[{"role": "user", "content": "hello"}],
            tool_definitions=[],
        )
