"""Tests for ReAct loop native tool_use message flow."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from open_agent.agent.react import ReActLoop, AgentResponse
from open_agent.registry import ToolRegistry
from open_agent.tools.base import Tool
from open_agent.types import ToolCall, ToolCallResponse
from typing import Any


class _EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo back the input"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def execute(self, **kwargs):
        return kwargs.get("text", "")


class TestReActToolUse:
    @pytest.mark.asyncio
    async def test_direct_answer(self):
        """LLM returns text without calling any tool → loop stops."""
        registry = ToolRegistry()
        registry.register(_EchoTool())

        provider = MagicMock()
        response = ToolCallResponse(
            text="The answer is 42",
            tool_calls=[],
            stop_reason="end_turn",
        )
        provider.complete_with_tools = AsyncMock(return_value=response)

        loop = ReActLoop(
            tool_registry=registry,
            provider=provider,
        )
        result = await loop.run(
            user_input="What is the answer?",
            routing_decision=MagicMock(skip_planning=True),
        )

        assert isinstance(result, AgentResponse)
        assert "42" in result.answer
        assert result.total_steps == 1

    @pytest.mark.asyncio
    async def test_tool_call_then_answer(self):
        """LLM calls a tool, gets result, then gives final answer."""
        registry = ToolRegistry()
        registry.register(_EchoTool())

        provider = MagicMock()

        # First call: tool_use
        tool_response = ToolCallResponse(
            text="Let me echo that",
            tool_calls=[ToolCall(id="call_1", name="echo", input={"text": "hello"})],
            stop_reason="tool_use",
        )
        # Second call: direct answer
        answer_response = ToolCallResponse(
            text="The echo result is: hello",
            tool_calls=[],
            stop_reason="end_turn",
        )
        provider.complete_with_tools = AsyncMock(
            side_effect=[tool_response, answer_response]
        )

        loop = ReActLoop(
            tool_registry=registry,
            provider=provider,
        )
        result = await loop.run(
            user_input="Echo hello",
            routing_decision=MagicMock(skip_planning=True),
        )

        assert "hello" in result.answer
        assert result.total_steps == 2

    @pytest.mark.asyncio
    async def test_tool_result_messages(self):
        """Verify tool_use/tool_result messages are appended correctly."""
        registry = ToolRegistry()
        registry.register(_EchoTool())

        provider = MagicMock()
        call_count = 0

        async def mock_complete(messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ToolCallResponse(
                    text="",
                    tool_calls=[ToolCall(id="tc_1", name="echo", input={"text": "test"})],
                    stop_reason="tool_use",
                )
            # Verify tool_result messages are in the conversation
            has_tool_result = False
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            has_tool_result = True
            assert has_tool_result, "tool_result message should be in conversation"
            return ToolCallResponse(
                text="Done",
                tool_calls=[],
                stop_reason="end_turn",
            )

        provider.complete_with_tools = mock_complete

        loop = ReActLoop(
            tool_registry=registry,
            provider=provider,
        )
        await loop.run(
            user_input="test",
            routing_decision=MagicMock(skip_planning=True),
        )

    @pytest.mark.asyncio
    async def test_no_provider_fallback(self):
        """Without a provider, uses rule-based fallback."""
        registry = ToolRegistry()
        loop = ReActLoop(tool_registry=registry)
        result = await loop.run(
            user_input="Hello",
            routing_decision=MagicMock(skip_planning=True),
        )
        assert result.answer  # Should have some answer


class _FailingTool(Tool):
    """Tool that always fails with a consistent error."""

    def __init__(self, error_msg: str = "Connection refused"):
        self._error = error_msg

    @property
    def name(self) -> str:
        return "fail_tool"

    @property
    def description(self) -> str:
        return "Always fails"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return f"Error: {self._error}"


class TestAnomalyTermination:
    @pytest.mark.asyncio
    async def test_tool_loop_terminates(self):
        """Same tool called >=4 times triggers termination."""
        registry = ToolRegistry()
        registry.register(_EchoTool())

        provider = MagicMock()

        tool_response = ToolCallResponse(
            text="calling echo",
            tool_calls=[ToolCall(id="call_1", name="echo", input={"text": "hi"})],
            stop_reason="tool_use",
        )
        answer_response = ToolCallResponse(
            text="Final answer",
            tool_calls=[],
            stop_reason="end_turn",
        )
        provider.complete_with_tools = AsyncMock(
            side_effect=[tool_response, tool_response, tool_response, tool_response, answer_response]
        )

        loop = ReActLoop(
            tool_registry=registry,
            provider=provider,
        )
        result = await loop.run(
            user_input="Keep echoing",
            routing_decision=MagicMock(skip_planning=True),
        )

        assert result.total_steps <= 5
        assert "tool loop detected" in result.answer or result.total_steps < 5

    @pytest.mark.asyncio
    async def test_repeated_error_terminates(self):
        """Same error message appearing >=3 times triggers termination."""
        registry = ToolRegistry()
        registry.register(_FailingTool("Connection refused"))

        provider = MagicMock()

        fail_response = ToolCallResponse(
            text="trying",
            tool_calls=[ToolCall(id="call_1", name="fail_tool", input={})],
            stop_reason="tool_use",
        )
        answer_response = ToolCallResponse(
            text="Final answer",
            tool_calls=[],
            stop_reason="end_turn",
        )
        provider.complete_with_tools = AsyncMock(
            side_effect=[fail_response, fail_response, fail_response, answer_response]
        )

        loop = ReActLoop(
            tool_registry=registry,
            provider=provider,
        )
        result = await loop.run(
            user_input="Try the failing tool",
            routing_decision=MagicMock(skip_planning=True),
        )

        assert "repeated error detected" in result.answer or result.total_steps < 4

    @pytest.mark.asyncio
    async def test_below_threshold_does_not_terminate(self):
        """Below threshold (2 tool calls, 2 errors) does not trigger termination."""
        registry = ToolRegistry()
        registry.register(_EchoTool())

        provider = MagicMock()

        tool_response = ToolCallResponse(
            text="calling echo",
            tool_calls=[ToolCall(id="call_1", name="echo", input={"text": "hi"})],
            stop_reason="tool_use",
        )
        answer_response = ToolCallResponse(
            text="Final answer",
            tool_calls=[],
            stop_reason="end_turn",
        )
        provider.complete_with_tools = AsyncMock(
            side_effect=[tool_response, tool_response, answer_response]
        )

        loop = ReActLoop(
            tool_registry=registry,
            provider=provider,
        )
        result = await loop.run(
            user_input="Echo twice",
            routing_decision=MagicMock(skip_planning=True),
        )

        assert result.total_steps == 3
        assert "terminated" not in result.answer.lower()
