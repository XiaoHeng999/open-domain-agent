"""ReAct Loop Core — Thought → Action → Observation → Reflection cycle."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from open_agent.errors import AgentError, ToolError
from open_agent.registry import ToolRegistry
from open_agent.routing.router import RoutingDecision
from open_agent.trace import Span, SpanKind, Trace

logger = logging.getLogger("open_agent")

# Lazy import to avoid circular dependency — resolved at runtime
_PROMPT_BUILDER_TYPES: tuple = ()
_PROMPT_BUILDER_CLS: type | None = None


def _get_prompt_builder_type() -> type:
    global _PROMPT_BUILDER_CLS
    if _PROMPT_BUILDER_CLS is None:
        from open_agent.prompt.builder import PromptBuilder
        _PROMPT_BUILDER_CLS = PromptBuilder
    return _PROMPT_BUILDER_CLS


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class StepType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    REFLECTION = "reflection"


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
    """Agent's evaluation of progress toward the goal."""

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
    reflection: Reflection | None = None

    def is_complete(self) -> bool:
        return all(x is not None for x in (self.thought, self.action, self.observation, self.reflection))


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


class ReActLoop:
    """Execute the Thought → Action → Observation → Reflection cycle.

    Parameters
    ----------
    tool_registry : ToolRegistry
        Registry used to look up and invoke tools.
    max_iterations : int
        Hard cap on ReAct iterations (default 10).
    provider : Any
        Optional LLM provider for generating thoughts and reflections.
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
        """Run the full ReAct loop for *user_input*.

        If *routing_decision.skip_planning* is ``True`` the loop executes
        without a prior planning step (fast-path for simple tasks).
        """
        state = AgentState()

        root_span: Span | None = None
        if trace:
            root_span = trace.create_span(
                "react_loop",
                kind=SpanKind.AGENT_LOOP,
            )
            root_span.set_attribute("user_input", user_input)
            root_span.set_attribute("skip_planning", routing_decision.skip_planning)

        try:
            for iteration in range(self._max_iterations):
                step = ReActStep(index=iteration)

                # 1. Thought
                step.thought = await self._generate_thought(
                    user_input, state, iteration, trace,
                )

                # 2. Action
                step.action = await self._decide_action(
                    user_input, state, step.thought, iteration, trace,
                )

                # 3. Observation
                step.observation = await self._execute_action(
                    step.action, iteration, trace,
                )

                # 4. Reflection
                step.reflection = await self._reflect(
                    user_input, state, step.observation, iteration, trace,
                )

                state.add_step(step)

                if not step.reflection.should_continue:
                    break

            # Build final answer
            if state.steps:
                state.final_answer = self._compose_final_answer(user_input, state)
            else:
                state.final_answer = "No steps were executed."
            state.finished = True

        except AgentError:
            raise
        except Exception as exc:
            logger.exception("ReAct loop failed")
            if root_span:
                root_span.finish(status=SpanKind.AGENT_LOOP, error=str(exc))
            raise AgentError(f"ReAct loop failed: {exc}") from exc

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

    async def _generate_thought(
        self,
        user_input: str,
        state: AgentState,
        iteration: int,
        trace: Trace | None,
    ) -> Thought:
        span = self._begin_step_span(trace, "thought", iteration)

        if self._provider:
            messages = self._build_messages(user_input, state, "Think about what to do next.")
            content = await self._provider.complete(messages)
        else:
            content = self._rule_based_thought(user_input, state, iteration)

        if span:
            span.set_attribute("thought", content)
            span.finish()

        return Thought(content=content, step_index=iteration)

    async def _decide_action(
        self,
        user_input: str,
        state: AgentState,
        thought: Thought,
        iteration: int,
        trace: Trace | None,
    ) -> Action:
        span = self._begin_step_span(trace, "action", iteration)

        if self._provider:
            messages = self._build_messages(
                user_input,
                state,
                f"Based on thought: {thought.content}. Decide which tool to call and with what arguments.",
            )
            raw = await self._provider.complete_structured(
                messages,
                schema={"tool_name": "string", "args": "object"},
            )
            tool_name = raw.get("tool_name", "direct_answer")
            args = raw.get("args", {})
        else:
            tool_name, args = self._rule_based_action(user_input, state)

        if span:
            span.set_attribute("tool_name", tool_name)
            span.set_attribute("args", str(args))
            span.finish()

        return Action(tool_name=tool_name, args=args, step_index=iteration)

    async def _execute_action(
        self,
        action: Action,
        iteration: int,
        trace: Trace | None,
    ) -> Observation:
        span = self._begin_step_span(trace, "observation", iteration)

        try:
            if action.tool_name == "direct_answer":
                content = action.args.get("answer", "")
                success = True
            elif self._registry.has(action.tool_name):
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

    async def _reflect(
        self,
        user_input: str,
        state: AgentState,
        observation: Observation,
        iteration: int,
        trace: Trace | None,
    ) -> Reflection:
        span = self._begin_step_span(trace, "reflection", iteration)

        if self._provider:
            messages = self._build_messages(
                user_input,
                state,
                f"Observation: {observation.content}. Should we continue?",
            )
            raw = await self._provider.complete_structured(
                messages,
                schema={"content": "string", "should_continue": "boolean"},
            )
            content = raw.get("content", "")
            should_continue = raw.get("should_continue", True)
        else:
            content, should_continue = self._rule_based_reflection(
                user_input, observation, iteration,
            )

        if span:
            span.set_attribute("should_continue", should_continue)
            span.finish()

        return Reflection(
            content=content,
            should_continue=should_continue,
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

    def _build_messages(
        self,
        user_input: str,
        state: AgentState,
        prompt: str,
    ) -> list[dict[str, Any]]:
        # System prompt: use PromptBuilder if available, else minimal default
        # Include JSON instruction so providers like DeepSeek accept response_format
        if self._prompt_builder is not None:
            system_content = self._prompt_builder.build(
                context={"matched_skills": getattr(self, "_matched_skills", [])}
            )
        else:
            system_content = "You are a helpful agent using the ReAct framework."
        system_content += "\nWhen asked to decide an action, respond with valid JSON."

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_input},
        ]
        for step in state.steps:
            if step.thought:
                messages.append({"role": "assistant", "content": f"Thought: {step.thought.content}"})
            if step.action:
                messages.append({
                    "role": "assistant",
                    "content": f"Action: {step.action.tool_name}({step.action.args})",
                })
            if step.observation:
                messages.append({"role": "user", "content": f"Observation: {step.observation.content}"})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _rule_based_thought(
        user_input: str,
        state: AgentState,
        iteration: int,
    ) -> str:
        if iteration == 0:
            return f"I need to address the user's request: {user_input}"
        return f"Continuing to work on the request (step {iteration + 1})"

    @staticmethod
    def _rule_based_action(
        user_input: str,
        state: AgentState,
    ) -> tuple[str, dict[str, Any]]:
        # If no tools registered, give a direct answer.
        if len(state.steps) == 0:
            return "direct_answer", {"answer": user_input}
        return "direct_answer", {"answer": user_input}

    @staticmethod
    def _rule_based_reflection(
        user_input: str,
        observation: Observation,
        iteration: int,
    ) -> tuple[str, bool]:
        # For rule-based mode, stop after first successful observation.
        if observation.success and iteration == 0:
            return "Task completed successfully.", False
        if iteration >= 1:
            return "Maximum useful iterations reached.", False
        return "Need more information.", True

    @staticmethod
    def _compose_final_answer(user_input: str, state: AgentState) -> str:
        # Use the last successful observation as the answer basis.
        for step in reversed(state.steps):
            if step.observation and step.observation.success:
                return step.observation.content
        return f"Processed: {user_input}"
