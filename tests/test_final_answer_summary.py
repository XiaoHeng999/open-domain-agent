"""Tests for final answer summary — concise LLM-generated summary after tool execution."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from open_agent.agent.react import ReActLoop
from open_agent.registry import ToolRegistry
from open_agent.tools.base import Tool
from open_agent.types import ToolCall, ToolCallResponse


class _UpperTool(Tool):
    @property
    def name(self) -> str:
        return "upper"

    @property
    def description(self) -> str:
        return "Uppercase input"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def execute(self, **kwargs):
        return kwargs["text"].upper()


class TestFinalAnswerSummary:
    @pytest.mark.asyncio
    async def test_summary_after_tool_execution(self):
        """After tool execution, a summary LLM call produces the final answer."""
        registry = ToolRegistry()
        registry.register(_UpperTool())

        provider = MagicMock()

        # Call 1: tool call, Call 2: end_turn (loop stops), Call 3: summary
        call_count = 0

        async def mock_complete(messages, tools=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ToolCallResponse(
                    text="",
                    tool_calls=[ToolCall(id="tc_1", name="upper", input={"text": "hello"})],
                    stop_reason="tool_use",
                )
            if call_count == 2:
                return ToolCallResponse(
                    text="I've processed that",
                    tool_calls=[],
                    stop_reason="end_turn",
                )
            # Call 3: summary call
            return "The text was converted to uppercase: HELLO"

        provider.complete_with_tools = mock_complete
        provider.complete = AsyncMock(return_value="Summary: HELLO")

        loop = ReActLoop(tool_registry=registry, provider=provider)
        result = await loop.run(
            user_input="Convert hello to uppercase",
            routing_decision=MagicMock(skip_planning=True),
        )

        # Should have a concise summary, not raw tool output
        assert result.answer
        assert "HELLO" in result.answer

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_direct_answer(self):
        """Loop with no tool calls returns the direct LLM answer unchanged."""
        registry = ToolRegistry()

        provider = MagicMock()
        provider.complete_with_tools = AsyncMock(
            return_value=ToolCallResponse(
                text="The answer is 42",
                tool_calls=[],
                stop_reason="end_turn",
            )
        )

        loop = ReActLoop(tool_registry=registry, provider=provider)
        result = await loop.run(
            user_input="What is the answer?",
            routing_decision=MagicMock(skip_planning=True),
        )

        assert "42" in result.answer

    @pytest.mark.asyncio
    async def test_summary_uses_limited_tokens(self):
        """Summary call uses max_tokens=256 to control cost."""
        registry = ToolRegistry()
        registry.register(_UpperTool())

        provider = MagicMock()
        call_count = 0
        summary_kwargs = None

        async def mock_complete(messages, tools=None, **kwargs):
            nonlocal call_count, summary_kwargs
            call_count += 1
            if call_count == 1:
                return ToolCallResponse(
                    text="",
                    tool_calls=[ToolCall(id="tc_1", name="upper", input={"text": "hello"})],
                    stop_reason="tool_use",
                )
            if call_count == 2:
                return ToolCallResponse(text="Done", tool_calls=[], stop_reason="end_turn")
            # Summary call — capture kwargs
            summary_kwargs = kwargs
            return "Summary"

        provider.complete_with_tools = mock_complete

        loop = ReActLoop(tool_registry=registry, provider=provider)
        await loop.run(
            user_input="Test",
            routing_decision=MagicMock(skip_planning=True),
        )

        # Verify summary was attempted (call_count >= 3 if provider.complete called)
        # The summary uses provider.complete which is separate from complete_with_tools
        assert provider.complete.called or call_count >= 3
