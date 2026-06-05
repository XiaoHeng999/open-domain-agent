"""Tests for provider complete_with_tools implementations."""
import json
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent.types import ToolCall, ToolCallResponse


class TestAnthropicProviderTools:
    @pytest.mark.asyncio
    async def test_tool_use_response(self):
        from open_agent.model import AnthropicProvider
        from open_agent.config import ModelConfig

        provider = AnthropicProvider(ModelConfig(provider="anthropic", name="claude-3"))
        provider._client = MagicMock()

        text_block = MagicMock(type="text", text="Let me read that file")
        tool_block = MagicMock(type="tool_use")
        tool_block.id = "call_123"
        tool_block.name = "read_file"
        tool_block.input = {"path": "main.py"}
        mock_response = MagicMock()
        mock_response.content = [text_block, tool_block]
        mock_response.stop_reason = "tool_use"
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.complete_with_tools(
            messages=[{"role": "user", "content": "Read main.py"}],
            tool_definitions=[{
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
            }],
        )

        assert isinstance(result, ToolCallResponse)
        assert result.text == "Let me read that file"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"
        assert result.tool_calls[0].input == {"path": "main.py"}
        assert result.stop_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_text_only_response(self):
        from open_agent.model import AnthropicProvider
        from open_agent.config import ModelConfig

        provider = AnthropicProvider(ModelConfig(provider="anthropic", name="claude-3"))
        provider._client = MagicMock()

        text_block = MagicMock(type="text", text="The answer is 42")
        mock_response = MagicMock()
        mock_response.content = [text_block]
        mock_response.stop_reason = "end_turn"
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.complete_with_tools(
            messages=[{"role": "user", "content": "What is the answer?"}],
            tool_definitions=[],
        )

        assert result.text == "The answer is 42"
        assert result.tool_calls == []
        assert result.stop_reason == "end_turn"


class TestOpenAIProviderTools:
    @pytest.mark.asyncio
    async def test_tool_use_response(self):
        from open_agent.model import OpenAIProvider
        from open_agent.config import ModelConfig

        provider = OpenAIProvider(ModelConfig(provider="openai", name="gpt-4o"))
        provider._client = MagicMock()

        tc = MagicMock()
        tc.id = "call_abc"
        tc.function.name = "read_file"
        tc.function.arguments = json.dumps({"path": "main.py"})
        message = MagicMock()
        message.content = None
        message.tool_calls = [tc]
        choice = MagicMock()
        choice.message = message
        mock_response = MagicMock()
        mock_response.choices = [choice]
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.complete_with_tools(
            messages=[{"role": "user", "content": "Read main.py"}],
            tool_definitions=[{
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
            }],
        )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"
        assert result.tool_calls[0].input == {"path": "main.py"}

    @pytest.mark.asyncio
    async def test_text_only_response(self):
        from open_agent.model import OpenAIProvider
        from open_agent.config import ModelConfig

        provider = OpenAIProvider(ModelConfig(provider="openai", name="gpt-4o"))
        provider._client = MagicMock()

        message = MagicMock()
        message.content = "The answer is 42"
        message.tool_calls = None
        choice = MagicMock()
        choice.message = message
        mock_response = MagicMock()
        mock_response.choices = [choice]
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.complete_with_tools(
            messages=[{"role": "user", "content": "What is the answer?"}],
            tool_definitions=[],
        )

        assert result.text == "The answer is 42"
        assert result.tool_calls == []
        assert result.stop_reason == "end_turn"
