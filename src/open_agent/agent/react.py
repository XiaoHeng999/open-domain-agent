"""ReAct Loop Core — Thought → Action → Observation cycle.

Implements the industry-standard agentic loop pattern used by Claude Code
and OpenAI Codex:

- Tool definitions passed via native tool_use API (Anthropic/OpenAI format).
- Loop continues when LLM calls a tool (stop_reason="tool_use").
- Loop stops when LLM gives text answer (stop_reason="end_turn").
- Deterministic stop conditions: repeated actions, max steps.
- No separate "reflection" LLM call — stopping is structural, not probabilistic.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from open_agent.checkpoint.manager import ExecutionState
from open_agent.errors import AgentError, ToolError
from open_agent.registry import ToolRegistry
from open_agent.routing.router import RoutingDecision
from open_agent.trace import Span, SpanKind, Trace

from open_agent.hooks import HookEvent, HookManager

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
    tool_use_id: str = ""
    step_index: int = 0


@dataclass
class Observation:
    """Result returned from a tool execution."""

    content: str
    tool_name: str = ""
    tool_use_id: str = ""
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


class ReActLoop:
    """Execute the Thought → Action → Observation cycle.

    Uses native tool_use API instead of structured JSON simulation.
    The LLM calls tools via the API's tool_use mechanism, and results
    are returned via tool_result content blocks.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        max_iterations: int = 10,
        provider: Any = None,
        prompt_builder: Any = None,
        runtime_memory: Any = None,
        todo_manager: Any = None,
        staleness_rounds: int = 3,
        hook_manager: HookManager | None = None,
        checkpoint_manager: Any = None,
    ) -> None:
        self._registry = tool_registry
        self._max_iterations = max_iterations
        self._provider = provider
        self._prompt_builder = prompt_builder
        self._runtime_memory = runtime_memory
        self._todo_manager = todo_manager
        self._staleness_rounds = staleness_rounds
        self._hook_manager = hook_manager
        self._checkpoint_manager = checkpoint_manager
        # Backward compat: internal conversation history when no RuntimeMemory
        self._conversation_history: list[dict[str, str]] = []
        # Injected externally by AgentRuntime
        self._matched_skills: list[dict[str, Any]] = []
        # tool_use/tool_result message history (accumulated during loop)
        self._tool_messages: list[dict[str, Any]] = []

        # Domain system prompt override from routing
        self._domain_system_prompt: str | None = None

        # Session welcome text injected by hooks
        self._session_welcome: str = ""

        # Missing slots hint from routing (injected by runtime for non-simple tasks)
        self._missing_slots_hint: str = ""

    # -- public API ----------------------------------------------------------

    async def run(
        self,
        user_input: str,
        routing_decision: RoutingDecision,
        trace: Trace | None = None,
        resume_state: ExecutionState | None = None,
    ) -> AgentResponse:
        """Run the full ReAct loop for *user_input*."""
        state = AgentState()
        self._tool_messages = []
        self._domain_system_prompt = (
            routing_decision.domain.system_prompt
            if routing_decision and routing_decision.domain and routing_decision.domain.system_prompt
            else None
        )
        self._resumed_from_step: int | None = None

        # Resume: rebuild tool messages and set start iteration
        start_iteration = 0
        if resume_state is not None:
            self._tool_messages = list(resume_state.tool_calls_completed)
            start_iteration = resume_state.next_step
            self._resumed_from_step = resume_state.next_step

        root_span: Span | None = None
        if trace:
            root_span = trace.create_span(
                "react_loop",
                kind=SpanKind.AGENT_LOOP,
            )
            root_span.set_attribute("user_input", user_input)
            root_span.set_attribute("skip_planning", routing_decision.skip_planning)

        # Initialize task state if using RuntimeMemory
        if self._runtime_memory is not None:
            self._runtime_memory.reset_task_state()

        # Track last action for repeat detection
        last_action_keys: list[tuple[str, str]] = []
        repeat_count = 0

        # Tool health tracking
        tool_failure_counts: dict[str, int] = {}
        degraded_tools: set[str] = set()

        try:
            for iteration in range(start_iteration, self._max_iterations):
                logger.info("react.iteration.start iter=%d/%d", iteration + 1, self._max_iterations)
                step = ReActStep(index=iteration)

                # Increment task state
                if self._runtime_memory is not None:
                    self._runtime_memory.task_state.increment_step()

                # 1. Thought + Actions (single LLM call via native tool_use)
                thought_content, actions = await self._think_and_act(
                    user_input, state, iteration, trace,
                )
                step.thought = Thought(content=thought_content, step_index=iteration)

                # -- Deterministic stop conditions ------------------------

                # (a) end_turn → LLM gave text answer, no tool calls → stop
                if not actions:
                    step.action = Action(
                        tool_name="",
                        args={"answer": thought_content},
                        step_index=iteration,
                    )
                    step.observation = Observation(
                        content=thought_content,
                        tool_name="",
                        success=True,
                        step_index=iteration,
                    )
                    state.add_step(step)
                    if self._runtime_memory is not None:
                        self._runtime_memory.task_state.mark_finished("direct_answer")
                    break

                # Store first action in step for backward compat
                step.action = actions[0]

                # (b) Repeated action batch detection
                current_keys = sorted(
                    (a.tool_name, json.dumps(a.args, sort_keys=True))
                    for a in actions
                )
                if current_keys == last_action_keys:
                    repeat_count += 1
                    if repeat_count >= 3:
                        logger.warning(
                            "Stopping: action batch repeated %d times",
                            repeat_count + 1,
                        )
                        step.observation = Observation(
                            content=f"Action batch repeated with identical arguments. Stopping to prevent loop.",
                            tool_name=actions[0].tool_name,
                            success=False,
                            step_index=iteration,
                        )
                        state.add_step(step)
                        if self._runtime_memory is not None:
                            self._runtime_memory.task_state.mark_finished("repeated_action")
                        break
                else:
                    repeat_count = 0
                last_action_keys = current_keys

                # 2. Execute each tool action
                for act in actions:
                    # Check if all tools are degraded — force terminate
                    if degraded_tools and all(
                        a.tool_name in degraded_tools for a in actions
                    ):
                        tool_failures = "; ".join(
                            f"{name} (consecutive failures)" for name in sorted(degraded_tools)
                        )
                        obs = Observation(
                            content=f"All available tools are degraded. {tool_failures}",
                            tool_name=act.tool_name,
                            success=False,
                            step_index=iteration,
                        )
                        state.add_step(ReActStep(
                            index=iteration,
                            thought=Thought(content=thought_content, step_index=iteration) if act == actions[0] else None,
                            action=act,
                            observation=obs,
                        ))
                        if self._runtime_memory is not None:
                            self._runtime_memory.task_state.mark_finished("all_tools_degraded")
                        break

                    obs = await self._execute_action(act, iteration, trace)

                    # Update tool health tracking
                    if obs.success:
                        tool_failure_counts[act.tool_name] = 0
                        degraded_tools.discard(act.tool_name)
                    else:
                        tool_failure_counts[act.tool_name] = tool_failure_counts.get(act.tool_name, 0) + 1
                        if tool_failure_counts[act.tool_name] >= 3:
                            degraded_tools.add(act.tool_name)

                    # Append degraded warning if tool is degraded
                    if act.tool_name in degraded_tools:
                        obs.content += f"\n[Warning: Tool '{act.tool_name}' has been failing repeatedly. Consider using an alternative approach.]"

                    state.add_step(ReActStep(
                        index=iteration,
                        thought=Thought(content=thought_content, step_index=iteration) if act == actions[0] else None,
                        action=act,
                        observation=obs,
                    ))

                # 3. Checkpoint after each completed step
                if self._checkpoint_manager is not None:
                    step_num = len(state.steps)
                    if self._checkpoint_manager.should_checkpoint(step_num):
                        context = {
                            "steps_summary": [
                                {
                                    "thought": s.thought.content if s.thought else None,
                                    "action": s.action.tool_name if s.action else None,
                                    "observation": (s.observation.content[:200] if s.observation else None),
                                }
                                for s in state.steps
                            ],
                        }
                        tool_calls = list(self._tool_messages)
                        memory_state: dict[str, Any] = {}
                        if self._runtime_memory is not None:
                            ts = self._runtime_memory.task_state
                            memory_state = {
                                "step_count": ts.current_step,
                                "status": "finished" if ts.finished else "running",
                            }
                        cp = self._checkpoint_manager.save_checkpoint(
                            step_number=step_num,
                            context=context,
                            tool_calls=tool_calls,
                            memory_state=memory_state,
                        )
                        if trace is not None:
                            cp_span = trace.create_span(
                                "checkpoint_save",
                                kind=SpanKind.CHECKPOINT,
                            )
                            cp_span.set_attribute("step_number", step_num)
                            cp_span.set_attribute("checkpoint_id", cp.idempotency_key)
                            cp_span.finish()

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

        logger.info(
            "react.done steps=%d final_answer=%s",
            len(state.steps),
            state.final_answer[:80],
        )

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
    ) -> tuple[str, list[Action]]:
        """Single LLM call via native tool_use: returns (thought, list[Action])."""
        span = self._begin_step_span(trace, "think_and_act", iteration)

        if self._provider:
            messages = await self._build_messages(user_input, state)
            tool_definitions = self._registry.get_definitions()

            # Use complete_with_tools if available
            if hasattr(self._provider, "complete_with_tools"):
                from open_agent.types import ToolCallResponse
                response: ToolCallResponse = await self._provider.complete_with_tools(
                    messages, tool_definitions,
                )
                thought_content = response.text

                if response.tool_calls:
                    actions = [
                        Action(
                            tool_name=tc.name,
                            args=tc.input,
                            tool_use_id=tc.id,
                            step_index=iteration,
                        )
                        for tc in response.tool_calls
                    ]
                else:
                    # No tool call — LLM gave direct answer
                    actions = []
            else:
                # Fallback to complete_structured for providers without tool_use
                raw = await self._provider.complete_structured(
                    messages,
                    schema=self._legacy_tool_schema(),
                )
                thought_content = raw.get("thought", "")
                tool_name = raw.get("tool_name", "")
                args = raw.get("args", {})
                if tool_name == "direct_answer":
                    tool_name = ""
                    args = {"answer": args.get("answer", "")}
                actions = [Action(tool_name=tool_name, args=args, step_index=iteration)] if tool_name else []
        else:
            thought_content, tool_name, args = self._rule_based_think_and_act(
                user_input, state, iteration,
            )
            if tool_name == "direct_answer":
                actions = []
            else:
                actions = [Action(tool_name=tool_name, args=args, step_index=iteration)]

        if span:
            span.set_attribute("thought", thought_content)
            span.set_attribute("tool_count", len(actions))
            if actions:
                span.set_attribute("tool_names", [a.tool_name for a in actions])
            span.finish()

        if actions:
            logger.info(
                "react.think_and_act tools=%s thought=%s",
                [a.tool_name for a in actions],
                thought_content[:80],
            )
        else:
            logger.info("react.think_and_act tools=[] (direct answer)")

        return thought_content, actions

    async def _execute_action(
        self,
        action: Action,
        iteration: int,
        trace: Trace | None,
    ) -> Observation:
        span = self._begin_step_span(trace, "observation", iteration)
        _exec_start = time.monotonic()

        # Staleness reminder injection
        staleness_prefix = self._check_staleness()

        # --- TOOL_BEFORE hooks ---
        hook_prefix = ""
        if self._hook_manager is not None:
            before_ctx: dict[str, Any] = {
                "tool_name": action.tool_name,
                "args": action.args,
            }
            before_results = await self._hook_manager.fire(
                HookEvent.TOOL_BEFORE, before_ctx,
            )
            for hr in before_results:
                if hr.blocked:
                    content = hr.content or "Blocked by hook"
                    if staleness_prefix:
                        content = staleness_prefix + content
                    if span:
                        span.set_attribute("success", False)
                        span.set_attribute("blocked", True)
                        span.finish()
                    return Observation(
                        content=content,
                        tool_name=action.tool_name,
                        tool_use_id=action.tool_use_id,
                        success=False,
                        step_index=iteration,
                    )
                if hr.content:
                    hook_prefix += hr.content + "\n"

        start_time = None
        try:
            if self._hook_manager is not None:
                import time as _time
                start_time = _time.monotonic()

            if self._registry.has(action.tool_name):
                # Print tool call info to console
                from rich.console import Console
                _console = Console()
                _args_preview = json.dumps(action.args, ensure_ascii=False)
                if len(_args_preview) > 120:
                    _args_preview = _args_preview[:120] + "..."
                _console.print(
                    f"  [bold blue]🔧 Tool Call:[/] [cyan]{action.tool_name}[/]"
                    f"  [dim]{_args_preview}[/]"
                )
                result = await self._registry.execute(action.tool_name, action.args)
                content = str(result)
                success = not content.startswith("Error:")

                # Build tool_result message for next LLM call
                if action.tool_use_id:
                    self._tool_messages.append({
                        "role": "assistant",
                        "tool_calls": [{
                            "id": action.tool_use_id,
                            "type": "function",
                            "function": {
                                "name": action.tool_name,
                                "arguments": json.dumps(action.args),
                            },
                        }],
                    })
                    self._tool_messages.append({
                        "role": "tool",
                        "tool_call_id": action.tool_use_id,
                        "content": content,
                    })
            else:
                content = f"Tool not found: {action.tool_name}"
                success = False

        except ToolError as exc:
            success = False
            # --- Recovery integration ---
            recovery_trace = await self._try_recover(exc, action)
            if recovery_trace is not None and recovery_trace.final_status.value == "success":
                last_attempt = recovery_trace.attempts[-1]
                content = str(last_attempt.data.get("result", last_attempt.message))
                success = True
            else:
                content = f"Tool error: {exc}"
                if recovery_trace is not None:
                    trace_summary = ", ".join(
                        f"{a.strategy_name}({a.status.value})"
                        for a in recovery_trace.attempts
                    )
                    content += f"\nRecovery trace: [{trace_summary}]"

        except Exception as exc:
            content = f"Execution error: {exc}"
            success = False

        # --- TOOL_AFTER hooks ---
        hook_suffix = ""
        if self._hook_manager is not None:
            duration_ms = 0.0
            if start_time is not None:
                import time as _time
                duration_ms = (_time.monotonic() - start_time) * 1000
            after_ctx: dict[str, Any] = {
                "tool_name": action.tool_name,
                "success": success,
                "duration_ms": duration_ms,
            }
            after_results = await self._hook_manager.fire(
                HookEvent.TOOL_AFTER, after_ctx,
            )
            for hr in after_results:
                if hr.content:
                    hook_suffix += "\n" + hr.content

        # Assemble final content
        parts: list[str] = []
        if staleness_prefix:
            parts.append(staleness_prefix)
        if hook_prefix:
            parts.append(hook_prefix)
        parts.append(content)
        if hook_suffix:
            parts.append(hook_suffix)
        content = "".join(parts)

        if span:
            span.set_attribute("success", success)
            span.finish()

        _exec_ms = (time.monotonic() - _exec_start) * 1000
        logger.info(
            "react.execute_action tool=%s success=%s duration=%.1fms result_len=%d",
            action.tool_name, success, _exec_ms, len(content),
        )

        return Observation(
            content=content,
            tool_name=action.tool_name,
            tool_use_id=action.tool_use_id,
            success=success,
            step_index=iteration,
        )

    # -- helpers -------------------------------------------------------------

    async def _try_recover(
        self,
        error: ToolError,
        action: Action,
    ) -> Any:
        """Attempt recovery via the recovery chain. Returns RecoveryTrace or None."""
        try:
            from open_agent.recovery import execute_recovery_chain
        except ImportError:
            return None

        context: dict[str, Any] = {
            "tool_registry": self._registry,
            "tool_name": action.tool_name,
            "args": action.args,
        }
        tool = self._registry.get(action.tool_name)
        if tool is not None:
            context["tool_handler"] = tool.execute

        return await execute_recovery_chain(error, context)

    def _check_staleness(self) -> str:
        """Return staleness reminder if todo hasn't been updated recently."""
        if self._runtime_memory is None or self._todo_manager is None:
            return ""
        ts = self._runtime_memory.task_state
        if ts.rounds_since_todo_update >= self._staleness_rounds and self._todo_manager.has_unfinished():
            return "<reminder>Refresh your plan before continuing.</reminder>\n"
        return ""

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

    def _legacy_tool_schema(self) -> dict[str, Any]:
        """Fallback schema for providers without complete_with_tools."""
        available = []
        for tool in self._registry.list_tools():
            schema = tool.parameters
            available.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": schema.get("properties", {}),
            })

        return {
            "thought": "string — your reasoning about what to do next",
            "tool_name": "string — name of the tool to call. Use 'direct_answer' if you can answer directly.",
            "args": "object — arguments for the tool.",
            "_available_tools": available,
        }

    async def _build_messages(
        self,
        user_input: str,
        state: AgentState,
    ) -> list[dict[str, Any]]:
        """Build the message list for the LLM call."""
        # System prompt
        prompt_context: dict[str, Any] = {
            "matched_skills": self._matched_skills,
        }

        # Inject todo plan
        if self._todo_manager is not None:
            plan_text = self._todo_manager.render()
            if plan_text:
                prompt_context["todo_plan"] = plan_text

        # Inject missing slots hint
        if self._missing_slots_hint:
            prompt_context["missing_slots_hint"] = self._missing_slots_hint

        if self._prompt_builder is not None:
            system_content = self._prompt_builder.build(context=prompt_context)
            # Inject domain system prompt from routing if available
            if self._domain_system_prompt:
                system_content = self._domain_system_prompt + "\n\n" + system_content
            # Inject session welcome text from hooks
            if self._session_welcome:
                system_content = system_content + "\n\n" + self._session_welcome
            # Inject resumed-from marker
            if self._resumed_from_step is not None:
                system_content += f"\n\n<resumed_from_step={self._resumed_from_step}>"
        else:
            system_content = "You are a helpful agent using the ReAct framework."

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
        ]

        # Short-term memory: use RuntimeMemory or fallback to internal list
        if self._runtime_memory is not None:
            history = await self._runtime_memory.get_context()
            for turn in history:
                messages.append(turn)
        else:
            for turn in self._conversation_history:
                messages.append(turn)

        # Current user input
        messages.append({"role": "user", "content": user_input})

        # Append tool_use/tool_result messages from this loop run
        for msg in self._tool_messages:
            messages.append(msg)

        return messages

    @staticmethod
    def _rule_based_think_and_act(
        user_input: str,
        state: AgentState,
        iteration: int,
    ) -> tuple[str, str, dict[str, Any]]:
        """Fallback for when no LLM provider is configured."""
        if state.steps:
            return "Task already addressed.", "direct_answer", {"answer": ""}
        if iteration == 0:
            thought = f"I need to address the user's request: {user_input}"
        else:
            thought = f"Continuing to work on the request (step {iteration + 1})"
        return thought, "direct_answer", {"answer": user_input}

    @staticmethod
    def _compose_final_answer(user_input: str, state: AgentState) -> str:
        # Check for direct answer (tool_name is empty)
        for step in reversed(state.steps):
            if (
                step.observation
                and step.observation.success
                and step.action
                and not step.action.tool_name
            ):
                return step.observation.content or step.action.args.get("answer", "")

        # Check for any successful step
        successful_steps = [
            s for s in state.steps
            if s.observation and s.observation.success and s.action and s.action.tool_name
        ]
        failed_steps = [
            s for s in state.steps
            if s.observation and not s.observation.success and s.action and s.action.tool_name
        ]

        if successful_steps:
            return successful_steps[-1].observation.content

        # All steps failed — return structured failure message
        if failed_steps:
            error_lines: list[str] = []
            seen_tools: set[str] = set()
            for s in failed_steps:
                tool_name = s.action.tool_name
                if tool_name not in seen_tools:
                    seen_tools.add(tool_name)
                    reason = s.observation.content[:200]
                    if len(s.observation.content) > 200:
                        reason += "..."
                    error_lines.append(f"- {tool_name}: {reason}")
            failure_summary = "\n".join(error_lines)
            return (
                f"Failed to complete the task. The following tools encountered issues "
                f"during execution:\n{failure_summary}\n"
                f"It is recommended to check tool configuration or use an alternative approach."
            )

        return f"Processed: {user_input}"
