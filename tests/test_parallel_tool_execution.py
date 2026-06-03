"""Tests for parallel tool execution in ReActLoop."""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from open_agent.agent.react import ReActLoop
from open_agent.registry import ToolRegistry
from open_agent.tools.base import Tool
from open_agent.types import ToolCall, ToolCallResponse


class _SlowTool(Tool):
    """Tool that tracks concurrent executions via a shared counter."""

    def __init__(self, shared_state: dict) -> None:
        self._state = shared_state

    @property
    def name(self) -> str:
        return "slow"

    @property
    def description(self) -> str:
        return "Slow tool"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def execute(self, **kwargs):
        self._state["concurrent"] += 1
        self._state["max_concurrent"] = max(
            self._state["max_concurrent"], self._state["concurrent"]
        )
        await asyncio.sleep(0.05)
        self._state["concurrent"] -= 1
        return f"slow-{kwargs['text']}"


class _FailTool(Tool):
    """Tool that always returns an error."""

    @property
    def name(self) -> str:
        return "fail"

    @property
    def description(self) -> str:
        return "Always fails"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "required": ["msg"],
        }

    async def execute(self, **kwargs):
        return f"Error: {kwargs['msg']}"


class _EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def execute(self, **kwargs):
        return kwargs["text"]


class TestParallelExecution:
    @pytest.mark.asyncio
    async def test_two_calls_execute_in_parallel(self):
        """Two tool calls in one turn execute concurrently."""
        shared_state = {"concurrent": 0, "max_concurrent": 0}
        registry = ToolRegistry()
        registry.register(_SlowTool(shared_state))

        provider = MagicMock()
        tool_response = ToolCallResponse(
            text="",
            tool_calls=[
                ToolCall(id="tc_1", name="slow", input={"text": "a"}),
                ToolCall(id="tc_2", name="slow", input={"text": "b"}),
            ],
            stop_reason="tool_use",
        )
        answer_response = ToolCallResponse(
            text="Done",
            tool_calls=[],
            stop_reason="end_turn",
        )
        provider.complete_with_tools = AsyncMock(
            side_effect=[tool_response, answer_response]
        )

        loop = ReActLoop(tool_registry=registry, provider=provider)
        await loop.run(
            user_input="Run two slow tools",
            routing_decision=MagicMock(skip_planning=True),
        )

        assert shared_state["max_concurrent"] == 2

    @pytest.mark.asyncio
    async def test_results_in_original_order(self):
        """Tool results are appended in original action order."""
        registry = ToolRegistry()
        registry.register(_EchoTool())

        provider = MagicMock()
        tool_response = ToolCallResponse(
            text="",
            tool_calls=[
                ToolCall(id="tc_1", name="echo", input={"text": "first"}),
                ToolCall(id="tc_2", name="echo", input={"text": "second"}),
            ],
            stop_reason="tool_use",
        )
        answer_response = ToolCallResponse(
            text="Done",
            tool_calls=[],
            stop_reason="end_turn",
        )
        provider.complete_with_tools = AsyncMock(
            side_effect=[tool_response, answer_response]
        )

        loop = ReActLoop(tool_registry=registry, provider=provider)
        result = await loop.run(
            user_input="Two echoes",
            routing_decision=MagicMock(skip_planning=True),
        )

        # 2 tool steps + 1 answer step = 3 total
        assert result.total_steps == 3
        steps = result.state.steps
        # First 2 steps are the tool calls
        assert steps[0].action.tool_name == "echo"
        assert steps[0].observation.content == "first"
        assert steps[1].action.tool_name == "echo"
        assert steps[1].observation.content == "second"

    @pytest.mark.asyncio
    async def test_error_in_one_does_not_cancel_other(self):
        """Error in one parallel call does not prevent the other from completing."""
        registry = ToolRegistry()
        registry.register(_EchoTool())
        registry.register(_FailTool())

        provider = MagicMock()
        tool_response = ToolCallResponse(
            text="",
            tool_calls=[
                ToolCall(id="tc_1", name="echo", input={"text": "hello"}),
                ToolCall(id="tc_2", name="fail", input={"msg": "boom"}),
            ],
            stop_reason="tool_use",
        )
        answer_response = ToolCallResponse(
            text="Done",
            tool_calls=[],
            stop_reason="end_turn",
        )
        provider.complete_with_tools = AsyncMock(
            side_effect=[tool_response, answer_response]
        )

        loop = ReActLoop(tool_registry=registry, provider=provider)
        result = await loop.run(
            user_input="Echo and fail",
            routing_decision=MagicMock(skip_planning=True),
        )

        steps = result.state.steps
        # First 2 steps are the tool calls (3rd is the answer)
        assert steps[0].observation.content == "hello"
        assert steps[0].observation.success is True
        assert "boom" in steps[1].observation.content
        assert steps[1].observation.success is False

    @pytest.mark.asyncio
    async def test_single_tool_call_still_works(self):
        """Single tool call path still works correctly (backward compat)."""
        registry = ToolRegistry()
        registry.register(_EchoTool())

        provider = MagicMock()
        tool_response = ToolCallResponse(
            text="",
            tool_calls=[ToolCall(id="tc_1", name="echo", input={"text": "solo"})],
            stop_reason="tool_use",
        )
        answer_response = ToolCallResponse(
            text="Done",
            tool_calls=[],
            stop_reason="end_turn",
        )
        provider.complete_with_tools = AsyncMock(
            side_effect=[tool_response, answer_response]
        )

        loop = ReActLoop(tool_registry=registry, provider=provider)
        result = await loop.run(
            user_input="Echo solo",
            routing_decision=MagicMock(skip_planning=True),
        )

        assert result.total_steps == 2
        steps = result.state.steps
        assert len(steps) == 2
        assert steps[0].observation.content == "solo"
