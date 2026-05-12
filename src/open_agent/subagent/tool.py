"""SubagentTool — exposes sub-agents as a callable 'task' tool."""

from __future__ import annotations

import logging
from typing import Any

from open_agent.tools.base import Tool

logger = logging.getLogger("open_agent")

_TASK_PARAMETERS = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "Complete task instruction to pass to the sub-agent",
        },
        "subagent_type": {
            "type": "string",
            "description": "Preset sub-agent type (explore, plan, general, or custom)",
            "default": "general",
        },
        "description": {
            "type": "string",
            "description": "Short 3-5 word task description for UI display",
        },
        "run_in_background": {
            "type": "boolean",
            "description": "Whether to run the sub-agent asynchronously",
            "default": False,
        },
        "max_turns": {
            "type": "integer",
            "description": "Maximum iterations for the sub-agent",
            "default": 10,
            "minimum": 1,
            "maximum": 50,
        },
    },
    "required": ["prompt"],
}


class SubagentTool(Tool):
    """Tool that spawns a sub-agent to handle a delegated task."""

    def __init__(self, manager: Any, trace: Any = None) -> None:
        self._manager = manager
        self._trace = trace

    @property
    def name(self) -> str:
        return "task"

    @property
    def description(self) -> str:
        return "Spawn a sub-agent to handle a delegated task. Returns the sub-agent's answer."

    @property
    def parameters(self) -> dict[str, Any]:
        return _TASK_PARAMETERS

    @property
    def read_only(self) -> bool:
        return False

    async def execute(self, **kwargs: Any) -> str:
        prompt: str = kwargs["prompt"]
        subagent_type: str = kwargs.get("subagent_type", "general")
        run_in_background: bool = kwargs.get("run_in_background", False)
        max_turns: int = kwargs.get("max_turns", 10)

        # Create trace span if trace is available
        span = None
        if self._trace is not None:
            from open_agent.trace import SpanKind
            span = self._trace.create_span(
                operation=f"subagent:{subagent_type}",
                kind=SpanKind.SUBAGENT,
            )
            span.set_attribute("subagent_type", subagent_type)
            span.set_attribute("prompt", prompt[:200])
            span.set_attribute("max_turns", max_turns)
            span.set_attribute("background", run_in_background)

        if run_in_background:
            agent_id = await self._manager.start_background(
                prompt=prompt,
                subagent_type=subagent_type,
                max_turns=max_turns,
                trace=self._trace,
            )
            if span:
                span.set_attribute("agent_id", agent_id)
                span.finish()
            return f"[Started subagent: {agent_id}]"

        result = await self._manager.run_subagent(
            prompt=prompt,
            subagent_type=subagent_type,
            max_turns=max_turns,
            trace=self._trace,
        )

        if span:
            span.set_attribute("success", result.success)
            span.set_attribute("result_length", len(result.answer))
            span.finish()

        return result.answer
