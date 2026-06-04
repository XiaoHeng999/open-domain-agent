"""Tests for fast path — simple requests skip the ReAct loop."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from open_agent.config import AgentConfig
from open_agent.runtime import AgentRuntime, AgentResponse
from open_agent.routing.complexity import ComplexityResult
from open_agent.routing.domain import DomainRouteResult
from open_agent.routing.intent import IntentResult
from open_agent.routing.router import RoutingDecision
from open_agent.trace import TraceManager


def _make_runtime() -> AgentRuntime:
    """Create a minimal AgentRuntime with mocked internals."""
    from open_agent.errors import AgentError

    config = AgentConfig()
    runtime = object.__new__(AgentRuntime)
    runtime.config = config
    runtime.trace_manager = TraceManager.__new__(TraceManager)
    runtime.trace_manager._traces = {}
    runtime.trace_manager._counter = 0
    runtime._runtime_memory = None
    runtime._archive_memory = None
    runtime._profile_memory = None
    runtime._retrieval_memory = None
    runtime._todo_manager = None
    runtime._session_welcome = ""
    runtime.routing_pipeline = AsyncMock()
    runtime.plan_generator = AsyncMock()
    runtime.skill_matcher = MagicMock()
    runtime.skill_matcher.get_skills_for_prompt = MagicMock(return_value=[])
    runtime.react_loop = AsyncMock()
    runtime.react_loop._matched_skills = []
    runtime.react_loop._missing_slots_hint = ""
    runtime.react_loop.run = AsyncMock(return_value=type("Resp", (), {
        "answer": "done", "total_steps": 1, "total_usage": {"input_tokens": 0, "output_tokens": 0},
        "state": type("State", (), {"steps": []})(),
    })())
    # Provider for fast path
    runtime.provider = AsyncMock()
    runtime.provider.complete = AsyncMock(return_value="Hello! How can I help you?")
    # Monitoring
    runtime.anomaly_detector = MagicMock()
    runtime.anomaly_detector.detect = MagicMock(return_value=[])
    runtime.quality_scorer = MagicMock()
    runtime.quality_scorer.score = MagicMock(return_value=type("Q", (), {"score": 0.9})())
    runtime.feedback_loop = MagicMock()
    runtime.feedback_loop.suggest_eval_case = MagicMock(return_value=None)
    runtime._cost_tracker = None
    return runtime


def _fast_path_decision() -> RoutingDecision:
    return RoutingDecision(
        complexity=ComplexityResult(complexity="simple", confidence=0.95, method="rule"),
        domain=DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=True),
        intent=IntentResult(intent="greeting", slots={}, missing_slots=[]),
        skip_planning=True,
    )


class TestFastPathTriggered:
    """Simple request with skip_planning + no slots + no missing_slots → fast path."""

    @pytest.mark.asyncio
    async def test_greeting_hits_fast_path(self):
        runtime = _make_runtime()
        runtime.routing_pipeline.route = AsyncMock(return_value=_fast_path_decision())

        response = await runtime.run("你好")

        assert response.metadata.get("fast_path") is True
        assert response.output == "Hello! How can I help you?"
        assert response.routing is not None
        assert response.duration_ms > 0
        # ReAct loop should NOT be called
        runtime.react_loop.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_fast_path_uses_provider_complete(self):
        runtime = _make_runtime()
        runtime.routing_pipeline.route = AsyncMock(return_value=_fast_path_decision())

        await runtime.run("hello")

        runtime.provider.complete.assert_called_once()
        call_args = runtime.provider.complete.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_fast_path_creates_trace_span(self):
        runtime = _make_runtime()
        runtime.routing_pipeline.route = AsyncMock(return_value=_fast_path_decision())

        response = await runtime.run("你好")

        trace = runtime.trace_manager.get_trace(response.trace_id)
        assert trace is not None
        span_kinds = [s.kind.value for s in trace.spans]
        assert "agent_loop" in span_kinds

    @pytest.mark.asyncio
    async def test_fast_path_span_is_finished(self):
        runtime = _make_runtime()
        runtime.routing_pipeline.route = AsyncMock(return_value=_fast_path_decision())

        response = await runtime.run("你好")

        trace = runtime.trace_manager.get_trace(response.trace_id)
        fast_path_spans = [s for s in trace.spans if s.operation == "fast_path"]
        assert len(fast_path_spans) == 1
        span = fast_path_spans[0]
        assert span.end_time is not None
        assert span.status.value == "ok"

    @pytest.mark.asyncio
    async def test_fast_path_span_records_attributes(self):
        runtime = _make_runtime()
        runtime.routing_pipeline.route = AsyncMock(return_value=_fast_path_decision())

        response = await runtime.run("你好")

        trace = runtime.trace_manager.get_trace(response.trace_id)
        span = [s for s in trace.spans if s.operation == "fast_path"][0]
        assert span.attributes["intent"] == "greeting"
        assert span.attributes["domain"] == "general"
        assert span.attributes["answer_len"] == len("Hello! How can I help you?")


class TestFastPathNotTriggered:
    """Requests with slots or complex routing should NOT hit fast path."""

    @pytest.mark.asyncio
    async def test_with_slots_skips_fast_path(self):
        runtime = _make_runtime()
        decision = RoutingDecision(
            complexity=ComplexityResult(complexity="simple", confidence=0.95, method="rule"),
            domain=DomainRouteResult(domain="weather", candidates=["weather"], routed_as_fallback=False),
            intent=IntentResult(intent="weather_query", slots={"city": "Beijing"}, missing_slots=[]),
            skip_planning=True,
        )
        runtime.routing_pipeline.route = AsyncMock(return_value=decision)

        await runtime.run("Beijing weather")

        runtime.react_loop.run.assert_called_once()
        runtime.provider.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_complex_request_skips_fast_path(self):
        runtime = _make_runtime()
        decision = RoutingDecision(
            complexity=ComplexityResult(complexity="complex", confidence=0.7, method="rule"),
            domain=DomainRouteResult(domain="coding", candidates=["coding"], routed_as_fallback=False),
            intent=IntentResult(intent="create_project", slots={}, missing_slots=[]),
            skip_planning=False,
        )
        runtime.routing_pipeline.route = AsyncMock(return_value=decision)

        await runtime.run("Create a full project")

        runtime.react_loop.run.assert_called_once()
        runtime.provider.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_missing_slots_skips_fast_path(self):
        runtime = _make_runtime()
        decision = RoutingDecision(
            complexity=ComplexityResult(complexity="simple", confidence=0.95, method="rule"),
            domain=DomainRouteResult(domain="weather", candidates=["weather"], routed_as_fallback=False),
            intent=IntentResult(intent="weather_query", slots={}, missing_slots=["city"]),
            skip_planning=True,
        )
        runtime.routing_pipeline.route = AsyncMock(return_value=decision)

        response = await runtime.run("What's the weather?")

        # Should hit the clarification path, not fast path
        assert response.metadata.get("fast_path") is None
        assert response.metadata.get("clarification") is True


class TestFastPathErrorHandling:
    """Fast path LLM failure should propagate."""

    @pytest.mark.asyncio
    async def test_provider_failure_propagates(self):
        from open_agent.errors import AgentError

        runtime = _make_runtime()
        runtime.routing_pipeline.route = AsyncMock(return_value=_fast_path_decision())
        runtime.provider.complete = AsyncMock(side_effect=AgentError("LLM down"))

        with pytest.raises(AgentError, match="LLM down"):
            await runtime.run("你好")


class TestFastPathTraceRobustness:
    """Fast path should handle trace being None gracefully."""

    @pytest.mark.asyncio
    async def test_fast_path_with_none_trace_no_error(self):
        """If trace is somehow None, fast path should still work (skip span creation)."""
        runtime = _make_runtime()
        runtime.routing_pipeline.route = AsyncMock(return_value=_fast_path_decision())
        # Override trace creation to return None
        runtime.trace_manager.create_trace = MagicMock(return_value=None)

        response = await runtime.run("你好")

        assert response.metadata.get("fast_path") is True
        assert response.output == "Hello! How can I help you?"
