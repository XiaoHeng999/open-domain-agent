"""Tests for multi tool_use execution (tasks 2.1-2.4)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from open_agent.agent.react import Action, AgentState, ReActLoop
from open_agent.registry import ToolRegistry
from open_agent.types import ToolCall, ToolCallResponse


def _make_registry() -> ToolRegistry:
    return ToolRegistry()


def _make_loop(registry: ToolRegistry | None = None) -> ReActLoop:
    from open_agent.hooks import HookManager
    return ReActLoop(
        tool_registry=registry or _make_registry(),
        max_iterations=5,
        provider=None,  # use rule-based fallback
    )


class TestMultiToolUseExecution:
    async def test_two_tool_calls_returned(self):
        """When LLM returns 2 tool_calls, both should be returned as Actions."""
        provider = MagicMock()
        provider.complete_with_tools = AsyncMock(return_value=ToolCallResponse(
            text="Calling two tools",
            tool_calls=[
                ToolCall(id="t1", name="read_file", input={"path": "/a"}),
                ToolCall(id="t2", name="list_dir", input={"path": "/b"}),
            ],
            stop_reason="tool_use",
        ))
        loop = _make_loop()
        loop._provider = provider

        thought, actions = await loop._think_and_act(
            "test input", AgentState(), 0, None,
        )
        assert len(actions) == 2
        assert actions[0].tool_name == "read_file"
        assert actions[1].tool_name == "list_dir"

    async def test_zero_tool_calls_end_turn(self):
        """When LLM returns 0 tool_calls, actions list should be empty (end_turn)."""
        provider = MagicMock()
        provider.complete_with_tools = AsyncMock(return_value=ToolCallResponse(
            text="Direct answer",
            tool_calls=[],
            stop_reason="end_turn",
        ))
        loop = _make_loop()
        loop._provider = provider

        thought, actions = await loop._think_and_act(
            "test input", AgentState(), 0, None,
        )
        assert len(actions) == 0
        assert thought == "Direct answer"

    async def test_one_tool_call_failure_still_records(self):
        """Single tool call that fails should still produce an observation."""
        registry = _make_registry()
        from open_agent.tools.base import FunctionTool

        failing_tool = FunctionTool(
            name="fail_tool",
            description="fails",
            parameters={"type": "object", "properties": {}},
            handler=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        registry.register(failing_tool)

        loop = _make_loop(registry)
        action = Action(tool_name="fail_tool", args={}, tool_use_id="t1", step_index=0)
        obs = await loop._execute_action(action, 0, None)
        assert obs.success is False
        assert "Error" in obs.content or "error" in obs.content
