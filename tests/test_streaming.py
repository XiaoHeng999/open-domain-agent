"""Tests for streaming output — provider streaming, callbacks, and CLI display."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test 1: Streaming callback receives text chunks in order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_callback_receives_chunks() -> None:
    """When stream=True, complete_with_tools should invoke callback with chunks."""
    from open_agent.config import ModelConfig
    from open_agent.model import AnthropicProvider

    provider = AnthropicProvider(ModelConfig(provider="anthropic", name="claude-3-sonnet"))

    chunks_received: list[str] = []

    async def on_chunk(text: str) -> None:
        chunks_received.append(text)

    # Simulate streaming response
    class MockStreamResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def __aiter__(self):
            yield MagicMock(type="message_start", message=MagicMock(usage=MagicMock(input_tokens=10, output_tokens=0)))
            yield MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Hello "))
            yield MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="world"))
            yield MagicMock(type="message_delta", delta=MagicMock(stop_reason="end_turn"), usage=MagicMock(output_tokens=5))

        async def get_final_message(self):
            msg = MagicMock()
            msg.content = [MagicMock(type="text", text="Hello world")]
            msg.usage = MagicMock(input_tokens=10, output_tokens=5)
            return msg

    provider._client = MagicMock()
    provider._client.messages = MagicMock()
    provider._client.messages.stream = MagicMock(return_value=MockStreamResponse())

    from open_agent.types import ToolCallResponse
    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
        stream=True,
        on_chunk=on_chunk,
    )

    assert isinstance(result, ToolCallResponse)
    assert result.text == "Hello world"
    assert chunks_received == ["Hello ", "world"]


# ---------------------------------------------------------------------------
# Test 2: Non-streaming mode still works correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_streaming_mode_works() -> None:
    """When stream is not set, complete_with_tools works as before."""
    from open_agent.config import ModelConfig
    from open_agent.model import AnthropicProvider

    provider = AnthropicProvider(ModelConfig(provider="anthropic", name="claude-3-sonnet"))

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="hello")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

    provider._client = MagicMock()
    provider._client.messages = MagicMock()
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    from open_agent.types import ToolCallResponse
    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
    )

    assert isinstance(result, ToolCallResponse)
    assert result.text == "hello"


# ---------------------------------------------------------------------------
# Test 3: ReActLoop streams thought text via callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_react_loop_streams_thought() -> None:
    """ReActLoop should invoke on_thought callback with streaming text."""
    from open_agent.agent.react import ReActLoop
    from open_agent.registry import ToolRegistry
    from open_agent.types import ToolCallResponse

    registry = ToolRegistry()
    loop = ReActLoop(tool_registry=registry, max_iterations=2)

    thoughts_received: list[str] = []

    def on_thought(text: str) -> None:
        thoughts_received.append(text)

    loop._on_thought = on_thought

    async def mock_complete_with_tools(messages, tools, **kwargs):
        return ToolCallResponse(text="I think the answer is 42", stop_reason="end_turn")

    provider = MagicMock()
    provider.complete_with_tools = mock_complete_with_tools
    loop._provider = provider

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

    await loop.run("What is the answer?", routing_decision=routing)
    assert len(thoughts_received) > 0
    assert "42" in thoughts_received[0]


# ---------------------------------------------------------------------------
# Test 4: Tool progress callback fires during execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_progress_callback() -> None:
    """Tools should invoke on_progress callback during long execution."""
    from open_agent.tools.base import FunctionTool

    progress_calls: list[str] = []

    async def slow_handler(**kwargs):
        progress = kwargs.get("_on_progress")
        if progress:
            progress("Starting work...")
            progress("Halfway done...")
        return "done"

    tool = FunctionTool(
        name="slow_tool",
        description="A slow tool",
        parameters={"type": "object", "properties": {}},
        handler=slow_handler,
    )

    # Execute via tool's execute method with progress callback
    result = await tool.execute(on_progress=lambda msg: progress_calls.append(msg))
    assert result == "done"
    assert len(progress_calls) == 2
    assert "Starting" in progress_calls[0]


# ---------------------------------------------------------------------------
# Test 5: OpenAI streaming with chunks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_streaming_works() -> None:
    """OpenAI provider streaming should invoke callback with chunks."""
    from open_agent.config import ModelConfig
    from open_agent.model import OpenAIProvider

    provider = OpenAIProvider(ModelConfig(provider="openai", name="gpt-4o"))

    chunks_received: list[str] = []

    async def on_chunk(text: str) -> None:
        chunks_received.append(text)

    # Simulate streaming response
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta.content = "Hi "
    mock_chunk1.choices[0].delta.tool_calls = None

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock()]
    mock_chunk2.choices[0].delta.content = "there"
    mock_chunk2.choices[0].delta.tool_calls = None

    mock_chunk3 = MagicMock()
    mock_chunk3.choices = [MagicMock()]
    mock_chunk3.choices[0].delta.content = None
    mock_chunk3.choices[0].delta.tool_calls = None
    mock_chunk3.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    class MockAsyncStream:
        def __init__(self, items):
            self._items = items
        async def __aiter__(self):
            for item in self._items:
                yield item

    provider._client = MagicMock()
    provider._client.chat = MagicMock()
    provider._client.chat.completions = MagicMock()
    provider._client.chat.completions.create = AsyncMock(
        return_value=MockAsyncStream([mock_chunk1, mock_chunk2, mock_chunk3])
    )

    from open_agent.types import ToolCallResponse
    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
        stream=True,
        on_chunk=on_chunk,
    )

    assert isinstance(result, ToolCallResponse)
    assert result.text == "Hi there"
    assert chunks_received == ["Hi ", "there"]
