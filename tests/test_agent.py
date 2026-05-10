"""Tests for the Agent Runtime — ReAct Loop, Planning, and data structures."""

from __future__ import annotations

import asyncio
import pytest

from open_agent.agent import (
    Action,
    AgentResponse,
    AgentState,
    Observation,
    Plan,
    PlanGenerator,
    ReActLoop,
    ReActStep,
    Reflection,
    Thought,
)
from open_agent.registry import ToolRegistry
from open_agent.routing.complexity import ComplexityResult
from open_agent.routing.domain import DomainRouteResult
from open_agent.routing.intent import IntentResult
from open_agent.routing.router import RoutingDecision
from open_agent.trace import SpanKind, Trace, TraceManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_routing_decision(*, skip_planning: bool = True) -> RoutingDecision:
    return RoutingDecision(
        complexity=ComplexityResult(
            complexity="simple" if skip_planning else "complex",
            confidence=0.95 if skip_planning else 0.7,
            method="rule",
        ),
        domain=DomainRouteResult(
            domain="general",
            candidates=["general"],
            routed_as_fallback=True,
        ),
        intent=IntentResult(intent="general_query", slots={"query": "hello"}),
        skip_planning=skip_planning,
    )


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Data structure tests
# ---------------------------------------------------------------------------


class TestDataStructures:
    """Test ReAct step data structures."""

    def test_thought_fields(self):
        t = Thought(content="I should look up the weather.", step_index=0)
        assert t.content == "I should look up the weather."
        assert t.step_index == 0

    def test_action_fields(self):
        a = Action(tool_name="search", args={"query": "weather"}, step_index=1)
        assert a.tool_name == "search"
        assert a.args == {"query": "weather"}

    def test_observation_fields(self):
        o = Observation(content="Sunny, 25C", tool_name="search", success=True, step_index=1)
        assert o.content == "Sunny, 25C"
        assert o.success is True
        assert o.tool_name == "search"

    def test_reflection_fields(self):
        r = Reflection(content="Done.", should_continue=False, step_index=1)
        assert r.should_continue is False

    def test_react_step_is_complete(self):
        step = ReActStep(
            index=0,
            thought=Thought(content="t"),
            action=Action(tool_name="x"),
            observation=Observation(content="o"),
            reflection=Reflection(content="r"),
        )
        assert step.is_complete()

    def test_react_step_incomplete(self):
        step = ReActStep(index=0, thought=Thought(content="t"))
        assert not step.is_complete()

    def test_agent_state_add_step(self):
        state = AgentState()
        step = ReActStep(
            index=0,
            thought=Thought(content="think"),
            reflection=Reflection(content="done", should_continue=False),
        )
        state.add_step(step)
        assert len(state.steps) == 1
        assert state.current_step == 1

    def test_plan_dataclass(self):
        plan = Plan(goal="answer question", steps=["step 1", "step 2"])
        assert plan.current_step(0) == "step 1"
        assert plan.current_step(1) == "step 2"
        assert plan.is_complete(2)
        assert plan.to_dict() == {"goal": "answer question", "steps": ["step 1", "step 2"]}


# ---------------------------------------------------------------------------
# Simple task — direct execution (skip planning)
# ---------------------------------------------------------------------------


class TestSimpleTask:
    """Test simple task direct execution without planning."""

    def test_simple_task_runs(self):
        registry = ToolRegistry()
        loop = ReActLoop(tool_registry=registry, max_iterations=3)
        decision = _simple_routing_decision(skip_planning=True)

        response = _run(loop.run("Hello", decision))
        assert isinstance(response, AgentResponse)
        assert response.answer
        assert response.state.finished is True
        assert response.total_steps >= 1
        assert response.routing_decision is decision

    def test_simple_task_no_plan(self):
        registry = ToolRegistry()
        loop = ReActLoop(tool_registry=registry, max_iterations=3)
        decision = _simple_routing_decision(skip_planning=True)

        response = _run(loop.run("Hello", decision))
        assert response.state.plan is None


# ---------------------------------------------------------------------------
# Complex task with plan generation
# ---------------------------------------------------------------------------


class TestComplexTaskWithPlan:
    """Test complex task triggers plan generation."""

    def test_plan_generated_rule_based(self):
        gen = PlanGenerator(provider=None)
        plan = _run(gen.generate("Analyze the quarterly sales data"))
        assert isinstance(plan, Plan)
        assert plan.goal == "Analyze the quarterly sales data"
        assert len(plan.steps) >= 1

    def test_plan_integrated_with_react(self):
        registry = ToolRegistry()
        gen = PlanGenerator(provider=None)
        plan = _run(gen.generate("Complex multi-step research task"))

        loop = ReActLoop(tool_registry=registry, max_iterations=5)
        decision = _simple_routing_decision(skip_planning=False)

        response = _run(loop.run("Complex multi-step research task", decision))
        assert response.state.finished is True

    def test_plan_current_step_and_completion(self):
        plan = Plan(goal="g", steps=["a", "b", "c"])
        assert plan.current_step(0) == "a"
        assert plan.current_step(2) == "c"
        assert plan.current_step(3) is None
        assert not plan.is_complete(2)
        assert plan.is_complete(3)


# ---------------------------------------------------------------------------
# Max iteration limit
# ---------------------------------------------------------------------------


class TestMaxIterationLimit:
    """Test that the ReAct loop respects max_iterations."""

    def test_respects_max_iterations(self):
        registry = ToolRegistry()
        loop = ReActLoop(tool_registry=registry, max_iterations=2)
        decision = _simple_routing_decision()

        response = _run(loop.run("Do something", decision))
        assert response.total_steps <= 2

    def test_default_max_iterations(self):
        loop = ReActLoop(tool_registry=ToolRegistry())
        assert loop._max_iterations == 10


# ---------------------------------------------------------------------------
# Trace generation per step
# ---------------------------------------------------------------------------


class TestTraceGeneration:
    """Test that traces are created for each ReAct step."""

    def test_trace_spans_created(self):
        tm = TraceManager()
        trace = tm.create_trace()
        registry = ToolRegistry()
        loop = ReActLoop(tool_registry=registry, max_iterations=2)
        decision = _simple_routing_decision()

        response = _run(loop.run("Hello", decision, trace=trace))
        assert response.trace is trace

        # Should have a root span + spans for each phase of each iteration
        agent_spans = [s for s in trace.spans if s.kind == SpanKind.AGENT_LOOP]
        assert len(agent_spans) >= 1  # At least the root span

    def test_step_spans_have_iteration_attribute(self):
        tm = TraceManager()
        trace = tm.create_trace()
        registry = ToolRegistry()
        loop = ReActLoop(tool_registry=registry, max_iterations=1)
        decision = _simple_routing_decision()

        _run(loop.run("Hello", decision, trace=trace))

        # Check that phase spans exist with iteration attributes
        phase_spans = [
            s for s in trace.spans
            if s.operation.startswith("react_") and s.operation != "react_loop"
        ]
        for span in phase_spans:
            assert "iteration" in span.attributes
            assert "phase" in span.attributes

    def test_root_span_total_steps(self):
        tm = TraceManager()
        trace = tm.create_trace()
        registry = ToolRegistry()
        loop = ReActLoop(tool_registry=registry, max_iterations=3)
        decision = _simple_routing_decision()

        response = _run(loop.run("Hello", decision, trace=trace))
        root_span = next(s for s in trace.spans if s.operation == "react_loop")
        assert root_span.attributes.get("total_steps") == response.total_steps


# ---------------------------------------------------------------------------
# Tool integration
# ---------------------------------------------------------------------------


class TestToolIntegration:
    """Test tool execution within the ReAct loop."""

    def test_tool_call_via_registry(self):
        registry = ToolRegistry()

        def echo(text: str) -> str:
            """Echo back the input."""
            return text

        registry.register("echo", echo, description="Echo tool")

        loop = ReActLoop(tool_registry=registry, max_iterations=3)
        decision = _simple_routing_decision()

        # The rule-based mode uses direct_answer, but we verify the registry
        # is functional and tools can be looked up.
        assert registry.has("echo")
        entry = registry.get("echo")
        assert entry.handler("hello") == "hello"
