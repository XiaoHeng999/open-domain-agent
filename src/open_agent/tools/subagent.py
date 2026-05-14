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
            "description": "Preset sub-agent type: explore (read-only search), plan (task planning), code-reviewer (read-only review), code-writer (code changes + exec), researcher (web research), or custom",
            "default": "explore",
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

    def __init__(self, manager: Any, trace: Any = None, agent_id: str | None = None) -> None:
        self._manager = manager
        self._trace = trace
        self._agent_id = agent_id

    @property
    def name(self) -> str:
        return "task"

    @property
    def description(self) -> str:
        return (
            "Spawn a sub-agent to handle a delegated task. "
            "Built-in presets: explore (read-only codebase search and analysis), "
            "plan (task analysis and structured planning), "
            "code-reviewer (read-only code review with structured feedback), "
            "code-writer (code modification with post-change verification), "
            "researcher (web search and information synthesis, read-only). "
            "Returns the sub-agent's answer."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return _TASK_PARAMETERS

    @property
    def read_only(self) -> bool:
        return False

    async def execute(self, **kwargs: Any) -> str:
        prompt: str = kwargs["prompt"]
        subagent_type: str = kwargs.get("subagent_type", "explore")
        description: str = kwargs.get("description", "")
        run_in_background: bool = kwargs.get("run_in_background", False)
        max_turns: int = kwargs.get("max_turns", 10)

        # Print sub-agent call info to console
        from rich.console import Console
        _console = Console()
        _prompt_preview = prompt[:80] + "..." if len(prompt) > 80 else prompt
        _label = f"[bold magenta]🤖 Sub-Agent:[/] [magenta]{subagent_type}[/]"
        if description:
            _label += f"  [dim]({description})[/]"
        _console.print(
            f"  {_label}\n"
            f"    [dim]Prompt: {_prompt_preview}[/]\n"
            f"    [dim]Background: {run_in_background} | Max turns: {max_turns}[/]"
        )

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
            parent_id=self._agent_id,
        )

        if span:
            span.set_attribute("success", result.success)
            span.set_attribute("result_length", len(result.answer))
            span.finish()

        return result.answer
