"""ReAct Loop Core — Thought → Action → Observation cycle.

Implements the industry-standard agentic loop pattern used by Claude Code
and OpenAI Codex:

- Tool schemas are passed to the LLM so it knows exactly what tools exist.
- The loop continues when the LLM calls a tool, stops when it gives a
  direct text answer (no tool call).
- Deterministic stop conditions: direct_answer, repeated actions, max steps.
- No separate "reflection" LLM call — stopping is structural, not probabilistic.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from open_agent.errors import AgentError, ToolError
from open_agent.registry import ToolRegistry
from open_agent.routing.router import RoutingDecision
from open_agent.trace import Span, SpanKind, Trace

logger = logging.getLogger("open_agent")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class StepType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"


@dataclass
class Thought:
    """Agent's reasoning about the current state."""

    content: str
    step_index: int = 0


@dataclass
class Action:
    """A tool invocation decided by the agent."""

    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    step_index: int = 0


@dataclass
class Observation:
    """Result returned from a tool execution."""

    content: str
    tool_name: str = ""
    success: bool = True
    step_index: int = 0


@dataclass
class Reflection:
    """Agent's evaluation of progress — kept for backward compat."""

    content: str
    should_continue: bool = True
    step_index: int = 0


@dataclass
class ReActStep:
    """A single step in the ReAct loop containing one of each phase."""

    index: int
    thought: Thought | None = None
    action: Action | None = None
    observation: Observation | None = None

    def is_complete(self) -> bool:
        return all(x is not None for x in (self.thought, self.action, self.observation))


@dataclass
class AgentState:
    """Mutable state carried through the ReAct loop."""

    steps: list[ReActStep] = field(default_factory=list)
    current_step: int = 0
    final_answer: str = ""
    finished: bool = False
    plan: Any | None = None  # Optional Plan reference

    def add_step(self, step: ReActStep) -> None:
        self.steps.append(step)
        self.current_step = len(self.steps)


@dataclass
class AgentResponse:
    """Final response returned by the agent loop."""

    answer: str
    state: AgentState
    trace: Trace | None = None
    routing_decision: RoutingDecision | None = None
    total_steps: int = 0


# ---------------------------------------------------------------------------
# ReAct Loop
# ---------------------------------------------------------------------------

# Sentinel: the LLM returns this tool_name when it wants to give a final
# answer without calling any real tool.
_DIRECT_ANSWER_TOOL = "direct_answer"


class ReActLoop:
    """Execute the Thought → Action → Observation cycle.

    Parameters
    ----------
    tool_registry : ToolRegistry
        Registry used to look up and invoke tools.
    max_iterations : int
        Hard cap on ReAct iterations (default 10).
    provider : Any
        Optional LLM provider for generating thoughts and actions.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        max_iterations: int = 10,
        provider: Any = None,
        prompt_builder: Any = None,
    ) -> None:
        self._registry = tool_registry
        self._max_iterations = max_iterations
        self._provider = provider
        self._prompt_builder = prompt_builder

    # -- public API ----------------------------------------------------------

    async def run(
        self,
        user_input: str,
        routing_decision: RoutingDecision,
        trace: Trace | None = None,
    ) -> AgentResponse:
        """Run the full ReAct loop for *user_input*."""
        state = AgentState()

        root_span: Span | None = None
        if trace:
            root_span = trace.create_span(
                "react_loop",
                kind=SpanKind.AGENT_LOOP,
            )
            root_span.set_attribute("user_input", user_input)
            root_span.set_attribute("skip_planning", routing_decision.skip_planning)

        # Track last action for repeat detection
        last_action_key: tuple[str, str] | None = None
        repeat_count = 0

        try:
            for iteration in range(self._max_iterations):
                step = ReActStep(index=iteration)

                # 1. Thought + Action (single LLM call — decides tool & args)
                thought_content, action = await self._think_and_act(
                    user_input, state, iteration, trace,
                )
                step.thought = Thought(content=thought_content, step_index=iteration)
                step.action = action

                # -- Deterministic stop conditions ------------------------

                # (a) direct_answer → LLM chose not to call any tool → stop
                if action.tool_name == _DIRECT_ANSWER_TOOL:
                    step.observation = Observation(
                        content=action.args.get("answer", ""),
                        tool_name=_DIRECT_ANSWER_TOOL,
                        success=True,
                        step_index=iteration,
                    )
                    state.add_step(step)
                    break

                # (b) Repeated action detection (same tool + same args)
                action_key = (action.tool_name, json.dumps(action.args, sort_keys=True))
                if action_key == last_action_key:
                    repeat_count += 1
                    if repeat_count >= 3:
                        logger.warning(
                            "Stopping: action %s repeated %d times",
                            action.tool_name, repeat_count + 1,
                        )
                        step.observation = Observation(
                            content=f"Action {action.tool_name} repeated with identical arguments. Stopping to prevent loop.",
                            tool_name=action.tool_name,
                            success=False,
                            step_index=iteration,
                        )
                        state.add_step(step)
                        break
                else:
                    repeat_count = 0
                last_action_key = action_key

                # 2. Execute the tool
                step.observation = await self._execute_action(
                    step.action, iteration, trace,
                )
                state.add_step(step)

        except AgentError:
            raise
        except Exception as exc:
            logger.exception("ReAct loop failed")
            if root_span:
                root_span.finish(status=SpanKind.AGENT_LOOP, error=str(exc))
            raise AgentError(f"ReAct loop failed: {exc}") from exc

        # Build final answer
        if state.steps:
            state.final_answer = self._compose_final_answer(user_input, state)
        else:
            state.final_answer = "No steps were executed."
        state.finished = True

        if root_span:
            root_span.set_attribute("total_steps", len(state.steps))
            root_span.finish()

        return AgentResponse(
            answer=state.final_answer,
            state=state,
            trace=trace,
            routing_decision=routing_decision,
            total_steps=len(state.steps),
        )

    # -- internal steps ------------------------------------------------------

    async def _think_and_act(
        self,
        user_input: str,
        state: AgentState,
        iteration: int,
        trace: Trace | None,
    ) -> tuple[str, Action]:
        """Single LLM call: generate thought and decide action.

        Returns (thought_content, Action).
        """
        span = self._begin_step_span(trace, "think_and_act", iteration)

        if self._provider:
            messages = self._build_messages(user_input, state)
            raw = await self._provider.complete_structured(
                messages,
                schema=self._tool_schema(),
            )
            thought_content = raw.get("thought", "")
            tool_name = raw.get("tool_name", _DIRECT_ANSWER_TOOL)
            args = raw.get("args", {})
        else:
            thought_content, tool_name, args = self._rule_based_think_and_act(
                user_input, state, iteration,
            )

        action = Action(tool_name=tool_name, args=args, step_index=iteration)

        if span:
            span.set_attribute("thought", thought_content)
            span.set_attribute("tool_name", tool_name)
            span.set_attribute("args", str(args))
            span.finish()

        return thought_content, action

    async def _execute_action(
        self,
        action: Action,
        iteration: int,
        trace: Trace | None,
    ) -> Observation:
        span = self._begin_step_span(trace, "observation", iteration)

        try:
            if self._registry.has(action.tool_name):
                entry = self._registry.get(action.tool_name)
                result = entry.handler(**action.args)
                content = str(result)
                success = True
            else:
                content = f"Tool not found: {action.tool_name}"
                success = False
        except ToolError as exc:
            content = f"Tool error: {exc}"
            success = False
        except Exception as exc:
            content = f"Execution error: {exc}"
            success = False

        if span:
            span.set_attribute("success", success)
            span.finish()

        return Observation(
            content=content,
            tool_name=action.tool_name,
            success=success,
            step_index=iteration,
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _begin_step_span(
        trace: Trace | None, phase: str, iteration: int,
    ) -> Span | None:
        if trace is None:
            return None
        span = trace.create_span(
            f"react_{phase}",
            kind=SpanKind.AGENT_LOOP,
        )
        span.set_attribute("iteration", iteration)
        span.set_attribute("phase", phase)
        return span

    def _tool_schema(self) -> dict[str, Any]:
        """Build the JSON schema describing the expected LLM output.

        This is the industry-standard pattern: the schema tells the LLM
        exactly what tools exist and what arguments they accept, so it can
        produce well-structured output.  The special ``direct_answer`` tool
        acts as the "no tool call" signal — when the LLM returns this,
        the loop stops (same as ``stop_reason: "end_turn"`` in Claude/OpenAI).
        """
        available = []
        for entry in self._registry.list_tools():
            desc = entry.description or entry.schema.get("description", "")
            schema = entry.schema.get("inputSchema", entry.schema.get("parameters", {}))
            available.append({
                "name": entry.name,
                "description": desc,
                "parameters": schema.get("properties", {}),
            })

        return {
            "thought": "string — your reasoning about what to do next",
            "tool_name": f"string — name of the tool to call. Use '{_DIRECT_ANSWER_TOOL}' if you can answer directly without any tool.",
            "args": "object — arguments for the tool. For direct_answer, use {\"answer\": \"your response\"}.",
            "_available_tools": available,
        }

    def _build_messages(
        self,
        user_input: str,
        state: AgentState,
    ) -> list[dict[str, Any]]:
        """Build the message list for the LLM call.

        The system prompt includes:
        1. Agent identity
        2. Available tools with their schemas (so the LLM knows what it can call)
        3. The expected JSON output format
        """
        # System prompt: use PromptBuilder if available, else minimal default
        if self._prompt_builder is not None:
            system_content = self._prompt_builder.build(
                context={"matched_skills": getattr(self, "_matched_skills", [])}
            )
        else:
            system_content = "You are a helpful agent using the ReAct framework."

        # Append tool definitions and JSON format instructions
        tool_schema = self._tool_schema()
        tools_desc = tool_schema["_available_tools"]

        if tools_desc:
            tools_text = "Available tools:\n"
            for t in tools_desc:
                params = t["parameters"]
                params_str = ", ".join(
                    f"{k}: {v}" for k, v in params.items()
                ) if params else "(no parameters)"
                tools_text += f"- {t['name']}: {t['description']} — params: {params_str}\n"
            tools_text += (
                f"\nIf you can answer the user's question directly without using any tool, "
                f"set tool_name to \"{_DIRECT_ANSWER_TOOL}\" and args to {{\"answer\": \"your response\"}}."
            )
        else:
            tools_text = (
                f"No tools are available. Set tool_name to \"{_DIRECT_ANSWER_TOOL}\" "
                f"and args to {{\"answer\": \"your response\"}}."
            )

        system_content += (
            f"\n\n{tools_text}"
            "\n\nYou MUST respond in valid JSON with exactly these fields:"
            f"\n- \"thought\": your reasoning (string)"
            f"\n- \"tool_name\": the tool to call, or \"{_DIRECT_ANSWER_TOOL}\" to answer directly (string)"
            '\n- "args": the arguments object'
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_input},
        ]
        # Conversation history: previous steps
        for step in state.steps:
            if step.thought:
                messages.append({"role": "assistant", "content": f"Thought: {step.thought.content}"})
            if step.action:
                messages.append({
                    "role": "assistant",
                    "content": f"Action: {step.action.tool_name}({json.dumps(step.action.args)})",
                })
            if step.observation:
                messages.append({"role": "user", "content": f"Observation: {step.observation.content}"})
        return messages

    @staticmethod
    def _rule_based_think_and_act(
        user_input: str,
        state: AgentState,
        iteration: int,
    ) -> tuple[str, str, dict[str, Any]]:
        """Fallback for when no LLM provider is configured."""
        # After first step, stop — rule-based mode has no tools.
        if state.steps:
            return "Task already addressed.", _DIRECT_ANSWER_TOOL, {"answer": ""}
        if iteration == 0:
            thought = f"I need to address the user's request: {user_input}"
        else:
            thought = f"Continuing to work on the request (step {iteration + 1})"
        return thought, _DIRECT_ANSWER_TOOL, {"answer": user_input}

    @staticmethod
    def _compose_final_answer(user_input: str, state: AgentState) -> str:
        # Use the last direct_answer observation, or last successful observation
        for step in reversed(state.steps):
            if (
                step.observation
                and step.observation.success
                and step.action
                and step.action.tool_name == _DIRECT_ANSWER_TOOL
            ):
                return step.observation.content or step.action.args.get("answer", "")
        for step in reversed(state.steps):
            if step.observation and step.observation.success:
                return step.observation.content
        return f"Processed: {user_input}"
