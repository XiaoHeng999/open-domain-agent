"""Streaming boundary condition tests — edge cases for _stream_openai."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_provider():
    from open_agent.config import ModelConfig
    from open_agent.model import OpenAIProvider

    provider = OpenAIProvider(ModelConfig(provider="openai", name="gpt-4o"))
    provider._client = MagicMock()
    provider._client.chat = MagicMock()
    provider._client.chat.completions = MagicMock()
    return provider


class MockAsyncStream:
    def __init__(self, items):
        self._items = items

    async def __aiter__(self):
        for item in self._items:
            yield item


# ---------------------------------------------------------------------------
# 1. Empty chunk sequence — no content, no tool_calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_empty_chunks() -> None:
    """Empty stream (only usage chunk) should return empty text and no tool_calls."""
    provider = _make_provider()

    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock()]
    mock_chunk.choices[0].delta = MagicMock()
    mock_chunk.choices[0].delta.content = None
    mock_chunk.choices[0].delta.tool_calls = None
    mock_chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=0)

    provider._client.chat.completions.create = AsyncMock(
        return_value=MockAsyncStream([mock_chunk])
    )

    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
        stream=True,
        on_chunk=lambda t: None,
    )

    assert result.text == ""
    assert result.tool_calls == []
    assert result.stop_reason == "end_turn"
    assert result.usage == {"input_tokens": 5, "output_tokens": 0}


# ---------------------------------------------------------------------------
# 2. Pure tool_calls with no text content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_pure_tool_calls_no_text() -> None:
    """Stream with only tool_call deltas and no text should collect tool_calls."""
    provider = _make_provider()

    tc_delta = MagicMock()
    tc_delta.index = 0
    tc_delta.id = "call_pure"
    tc_delta.function = MagicMock()
    tc_delta.function.name = "calculator"
    tc_delta.function.arguments = '{"expr": "2+2"}'

    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock()]
    mock_chunk.choices[0].delta = MagicMock()
    mock_chunk.choices[0].delta.content = None
    mock_chunk.choices[0].delta.tool_calls = [tc_delta]
    mock_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    provider._client.chat.completions.create = AsyncMock(
        return_value=MockAsyncStream([mock_chunk])
    )

    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "calc 2+2"}],
        tool_definitions=[{"name": "calculator", "description": "Calc", "input_schema": {}}],
        stream=True,
        on_chunk=lambda t: None,
    )

    assert result.text == ""
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "calculator"
    assert result.tool_calls[0].input == {"expr": "2+2"}
    assert result.stop_reason == "tool_use"


# ---------------------------------------------------------------------------
# 3. Non-sequential / duplicate indices
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_non_sequential_indices() -> None:
    """Tool calls with non-sequential indices (0, 2) should be collected by index."""
    provider = _make_provider()

    tc1 = MagicMock()
    tc1.index = 0
    tc1.id = "call_0"
    tc1.function = MagicMock()
    tc1.function.name = "tool_a"
    tc1.function.arguments = '{"x": 1}'

    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta = MagicMock()
    mock_chunk1.choices[0].delta.content = None
    mock_chunk1.choices[0].delta.tool_calls = [tc1]
    mock_chunk1.usage = None

    tc2 = MagicMock()
    tc2.index = 2
    tc2.id = "call_2"
    tc2.function = MagicMock()
    tc2.function.name = "tool_c"
    tc2.function.arguments = '{"z": 3}'

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock()]
    mock_chunk2.choices[0].delta = MagicMock()
    mock_chunk2.choices[0].delta.content = None
    mock_chunk2.choices[0].delta.tool_calls = [tc2]
    mock_chunk2.usage = MagicMock(prompt_tokens=10, completion_tokens=10)

    provider._client.chat.completions.create = AsyncMock(
        return_value=MockAsyncStream([mock_chunk1, mock_chunk2])
    )

    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "do stuff"}],
        tool_definitions=[],
        stream=True,
        on_chunk=lambda t: None,
    )

    assert len(result.tool_calls) == 2
    assert result.tool_calls[0].name == "tool_a"
    assert result.tool_calls[1].name == "tool_c"
    assert result.stop_reason == "tool_use"


# ---------------------------------------------------------------------------
# 4. Arguments split across multiple chunks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_arguments_split_across_chunks() -> None:
    """Arguments split across 3 chunks should be concatenated correctly."""
    provider = _make_provider()

    chunks_data = [
        ("call_split", "search", '{"qu'),
        (None, None, 'ery": "he'),
        (None, None, 'llo"}'),
    ]
    mock_chunks = []
    for idx, (cid, name, args) in enumerate(chunks_data):
        tc = MagicMock()
        tc.index = 0
        tc.id = cid
        tc.function = MagicMock()
        tc.function.name = name
        tc.function.arguments = args

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = None
        chunk.choices[0].delta.tool_calls = [tc]
        chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=10) if idx == 2 else None
        mock_chunks.append(chunk)

    provider._client.chat.completions.create = AsyncMock(
        return_value=MockAsyncStream(mock_chunks)
    )

    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "search hello"}],
        tool_definitions=[],
        stream=True,
        on_chunk=lambda t: None,
    )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_split"
    assert result.tool_calls[0].name == "search"
    assert result.tool_calls[0].input == {"query": "hello"}


# ---------------------------------------------------------------------------
# 5. Mid-stream error should propagate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_mid_stream_error() -> None:
    """Exception during stream iteration should propagate (not swallowed)."""

    class FailingStream:
        async def __aiter__(self):
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta = MagicMock()
            mock_chunk.choices[0].delta.content = "partial"
            mock_chunk.choices[0].delta.tool_calls = None
            yield mock_chunk
            raise ConnectionError("Stream interrupted")

    provider = _make_provider()
    provider._client.chat.completions.create = AsyncMock(
        return_value=FailingStream()
    )

    with pytest.raises(ConnectionError, match="Stream interrupted"):
        await provider.complete_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tool_definitions=[],
            stream=True,
            on_chunk=lambda t: None,
        )
