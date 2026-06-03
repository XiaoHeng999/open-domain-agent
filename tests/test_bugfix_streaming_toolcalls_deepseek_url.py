"""Tests for streaming tool_calls bug fix and DeepSeek URL default fix."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# RED Test 1: OpenAI streaming collects tool_calls correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_streaming_collects_tool_calls() -> None:
    """_stream_openai should collect tool_calls from streaming chunks."""
    from open_agent.config import ModelConfig
    from open_agent.model import OpenAIProvider

    provider = OpenAIProvider(ModelConfig(provider="openai", name="gpt-4o"))

    chunks_received: list[str] = []

    async def on_chunk(text: str) -> None:
        chunks_received.append(text)

    # Simulate streaming response with tool_calls
    # Chunk 1: text content
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta = MagicMock()
    mock_chunk1.choices[0].delta.content = "Let me check "
    mock_chunk1.choices[0].delta.tool_calls = None
    mock_chunk1.usage = None

    # Chunk 2: start of tool_call (index 0, function name + partial args)
    tc_delta1 = MagicMock()
    tc_delta1.index = 0
    tc_delta1.id = "call_abc123"
    tc_delta1.function = MagicMock()
    tc_delta1.function.name = "get_weather"
    tc_delta1.function.arguments = '{"ci'

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock()]
    mock_chunk2.choices[0].delta = MagicMock()
    mock_chunk2.choices[0].delta.content = None
    mock_chunk2.choices[0].delta.tool_calls = [tc_delta1]
    mock_chunk2.usage = None

    # Chunk 3: continuation of tool_call arguments
    tc_delta2 = MagicMock()
    tc_delta2.index = 0
    tc_delta2.id = None
    tc_delta2.function = MagicMock()
    tc_delta2.function.name = None
    tc_delta2.function.arguments = 'ty": "SF"}'

    mock_chunk3 = MagicMock()
    mock_chunk3.choices = [MagicMock()]
    mock_chunk3.choices[0].delta = MagicMock()
    mock_chunk3.choices[0].delta.content = None
    mock_chunk3.choices[0].delta.tool_calls = [tc_delta2]
    mock_chunk3.usage = None

    # Chunk 4: final chunk with usage
    mock_chunk4 = MagicMock()
    mock_chunk4.choices = [MagicMock()]
    mock_chunk4.choices[0].delta = MagicMock()
    mock_chunk4.choices[0].delta.content = None
    mock_chunk4.choices[0].delta.tool_calls = None
    mock_chunk4.usage = MagicMock(prompt_tokens=20, completion_tokens=15)

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
        return_value=MockAsyncStream([mock_chunk1, mock_chunk2, mock_chunk3, mock_chunk4])
    )

    from open_agent.types import ToolCallResponse

    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "weather in SF?"}],
        tool_definitions=[{"name": "get_weather", "description": "Get weather", "input_schema": {}}],
        stream=True,
        on_chunk=on_chunk,
    )

    assert isinstance(result, ToolCallResponse)
    assert result.text == "Let me check "
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_abc123"
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].input == {"city": "SF"}
    assert result.stop_reason == "tool_use"
    assert chunks_received == ["Let me check "]


# ---------------------------------------------------------------------------
# RED Test 2: OpenAI streaming with multiple tool_calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_streaming_multiple_tool_calls() -> None:
    """_stream_openai should handle multiple tool_calls across chunks."""
    from open_agent.config import ModelConfig
    from open_agent.model import OpenAIProvider

    provider = OpenAIProvider(ModelConfig(provider="openai", name="gpt-4o"))

    # Chunk 1: tool_call index 0
    tc_delta1 = MagicMock()
    tc_delta1.index = 0
    tc_delta1.id = "call_001"
    tc_delta1.function = MagicMock()
    tc_delta1.function.name = "get_weather"
    tc_delta1.function.arguments = '{"city": "NYC"}'

    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta = MagicMock()
    mock_chunk1.choices[0].delta.content = None
    mock_chunk1.choices[0].delta.tool_calls = [tc_delta1]
    mock_chunk1.usage = None

    # Chunk 2: tool_call index 1
    tc_delta2 = MagicMock()
    tc_delta2.index = 1
    tc_delta2.id = "call_002"
    tc_delta2.function = MagicMock()
    tc_delta2.function.name = "get_time"
    tc_delta2.function.arguments = '{"timezone": "EST"}'

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock()]
    mock_chunk2.choices[0].delta = MagicMock()
    mock_chunk2.choices[0].delta.content = None
    mock_chunk2.choices[0].delta.tool_calls = [tc_delta2]
    mock_chunk2.usage = MagicMock(prompt_tokens=15, completion_tokens=10)

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
        return_value=MockAsyncStream([mock_chunk1, mock_chunk2])
    )

    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "weather and time"}],
        tool_definitions=[],
        stream=True,
        on_chunk=lambda t: None,
    )

    assert len(result.tool_calls) == 2
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].input == {"city": "NYC"}
    assert result.tool_calls[1].name == "get_time"
    assert result.tool_calls[1].input == {"timezone": "EST"}
    assert result.stop_reason == "tool_use"


# ---------------------------------------------------------------------------
# RED Test 3: DeepSeek default URL includes /v1
# ---------------------------------------------------------------------------


def test_deepseek_default_url_includes_v1() -> None:
    """DeepSeekProvider should default to https://api.deepseek.com/v1."""
    from open_agent.config import ModelConfig
    from open_agent.model import DeepSeekProvider

    config = ModelConfig(provider="deepseek", name="deepseek-chat")
    assert config.base_url is None

    provider = DeepSeekProvider(config)
    assert provider.config.base_url == "https://api.deepseek.com/v1"


# ---------------------------------------------------------------------------
# Test 4: DeepSeek explicit base_url is preserved
# ---------------------------------------------------------------------------


def test_deepseek_explicit_base_url_preserved() -> None:
    """DeepSeekProvider should not override an explicitly set base_url."""
    from open_agent.config import ModelConfig
    from open_agent.model import DeepSeekProvider

    config = ModelConfig(
        provider="deepseek",
        name="deepseek-chat",
        base_url="https://custom.api.com/v1",
    )
    provider = DeepSeekProvider(config)
    assert provider.config.base_url == "https://custom.api.com/v1"


# ---------------------------------------------------------------------------
# Test 5: Streaming and non-streaming produce same format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_non_streaming_same_format() -> None:
    """Both streaming and non-streaming should return ToolCallResponse with same structure."""
    from open_agent.config import ModelConfig
    from open_agent.model import OpenAIProvider
    from open_agent.types import ToolCallResponse

    provider = OpenAIProvider(ModelConfig(provider="openai", name="gpt-4o"))

    # --- Non-streaming response ---
    mock_tc = MagicMock()
    mock_tc.id = "call_123"
    mock_tc.function.name = "search"
    mock_tc.function.arguments = '{"q": "test"}'

    mock_msg = MagicMock()
    mock_msg.content = "Searching..."
    mock_msg.tool_calls = [mock_tc]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = mock_msg
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    # --- Streaming response ---
    tc_delta = MagicMock()
    tc_delta.index = 0
    tc_delta.id = "call_123"
    tc_delta.function = MagicMock()
    tc_delta.function.name = "search"
    tc_delta.function.arguments = '{"q": "test"}'

    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock()]
    mock_chunk.choices[0].delta = MagicMock()
    mock_chunk.choices[0].delta.content = "Searching..."
    mock_chunk.choices[0].delta.tool_calls = [tc_delta]
    mock_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    class MockAsyncStream:
        def __init__(self, items):
            self._items = items

        async def __aiter__(self):
            for item in self._items:
                yield item

    # Non-streaming call
    provider._client = MagicMock()
    provider._client.chat = MagicMock()
    provider._client.chat.completions = MagicMock()
    provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

    non_stream_result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "search test"}],
        tool_definitions=[{"name": "search", "description": "Search", "input_schema": {}}],
    )

    # Streaming call
    provider._client.chat.completions.create = AsyncMock(
        return_value=MockAsyncStream([mock_chunk])
    )

    stream_result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "search test"}],
        tool_definitions=[{"name": "search", "description": "Search", "input_schema": {}}],
        stream=True,
        on_chunk=lambda t: None,
    )

    # Same format: both have tool_calls, same stop_reason
    assert isinstance(non_stream_result, ToolCallResponse)
    assert isinstance(stream_result, ToolCallResponse)
    assert len(non_stream_result.tool_calls) == len(stream_result.tool_calls) == 1
    assert non_stream_result.tool_calls[0].name == stream_result.tool_calls[0].name
    assert non_stream_result.tool_calls[0].input == stream_result.tool_calls[0].input
    assert non_stream_result.stop_reason == stream_result.stop_reason == "tool_use"
