"""Tests for UnifiedLLMRouter and routing integration."""

from __future__ import annotations

import json

import pytest

from open_agent.routing.unified import UnifiedLLMRouter, UnifiedRoutingResult
from open_agent.routing.router import RoutingPipeline, RoutingDecision, RoutingTraceData
from open_agent.routing.domain import _DOMAINS
from open_agent.types import ToolCallResponse


# ---------------------------------------------------------------------------
# Helpers — lightweight async mock for provider
# ---------------------------------------------------------------------------


class _MockProvider:
    """Minimal async mock that satisfies complete_with_tools."""

    def __init__(
        self,
        response: dict | None = None,
        *,
        should_fail: bool = False,
        fail_count: int = 0,
        side_effect: list[dict] | None = None,
    ):
        self._response = response
        self._should_fail = should_fail
        self._fail_count = fail_count
        self._side_effect = side_effect
        self._call_count = 0
        self.last_messages: list[dict] | None = None

    async def complete_with_tools(self, messages, tools=None, **kw):
        self.last_messages = messages
        self._call_count += 1
        if self._should_fail or (self._fail_count > 0 and self._call_count <= self._fail_count):
            raise RuntimeError("LLM call failed")
        data = None
        if self._side_effect:
            idx = self._call_count - 1
            if idx < len(self._side_effect):
                data = self._side_effect[idx]
        if data is None:
            data = self._response
        return ToolCallResponse(text=json.dumps(data))


# ---------------------------------------------------------------------------
# Task 6.1: UnifiedLLMRouter tests
# ---------------------------------------------------------------------------


class TestUnifiedLLMRouterPromptBuilding:
    def test_system_prompt_contains_domains(self):
        provider = _MockProvider({})
        router = UnifiedLLMRouter(provider=provider, domains=_DOMAINS)
        assert "coding" in router._system_prompt
        assert "search" in router._system_prompt
        assert "web" in router._system_prompt
        assert "general" in router._system_prompt

    def test_system_prompt_contains_complexity_rules(self):
        provider = _MockProvider({})
        router = UnifiedLLMRouter(provider=provider, domains=_DOMAINS)
        assert "simple" in router._system_prompt
        assert "medium" in router._system_prompt
        assert "complex" in router._system_prompt

    def test_system_prompt_contains_examples(self):
        provider = _MockProvider({})
        router = UnifiedLLMRouter(provider=provider, domains=_DOMAINS)
        assert "debug_code" in router._system_prompt
        assert "research_compare" in router._system_prompt


class TestUnifiedLLMRouterParsing:
    def test_parse_valid_result(self):
        raw = {
            "complexity": "medium",
            "confidence": 0.88,
            "domain": "coding",
            "domain_candidates": ["coding", "general"],
            "intent": "write_code",
            "slots": {"language": "python"},
            "missing_slots": [],
            "reason": "Code generation request",
        }
        result = UnifiedLLMRouter._parse_result(raw)
        assert result.complexity == "medium"
        assert result.confidence == 0.88
        assert result.domain == "coding"
        assert result.intent == "write_code"
        assert result.slots == {"language": "python"}

    def test_parse_invalid_complexity_clamped(self):
        raw = {"complexity": "unknown", "confidence": 1.5, "domain": "general"}
        result = UnifiedLLMRouter._parse_result(raw)
        assert result.complexity == "simple"
        assert result.confidence == 1.0

    def test_parse_defaults(self):
        result = UnifiedLLMRouter._parse_result({})
        assert result.complexity == "simple"
        assert result.domain == "general"
        assert result.intent == "unknown"

    @pytest.mark.asyncio
    async def test_route_success(self):
        response = {
            "complexity": "simple",
            "confidence": 0.9,
            "domain": "coding",
            "domain_candidates": ["coding"],
            "intent": "debug_code",
            "slots": {},
            "missing_slots": [],
            "reason": "debug",
        }
        provider = _MockProvider(response)
        router = UnifiedLLMRouter(provider=provider, domains=_DOMAINS)
        result = await router.route("fix this bug")
        assert result.domain == "coding"
        assert result.intent == "debug_code"
        # Verify messages were sent
        assert provider.last_messages is not None
        assert len(provider.last_messages) == 2


class TestUnifiedLLMRouterFallback:
    @pytest.mark.asyncio
    async def test_route_exception_propagates(self):
        provider = _MockProvider(should_fail=True)
        router = UnifiedLLMRouter(provider=provider, domains=_DOMAINS)
        with pytest.raises(RuntimeError, match="LLM call failed"):
            await router.route("test")


class TestRoutingPipelineFallback:
    @pytest.mark.asyncio
    async def test_llm_fallback_to_stages(self):
        """When unified LLM router fails, pipeline falls back to three-stage LLM path."""
        # fail_count=1: first call (unified) fails.
        # side_effect: call 1 is skipped (fails), calls 2-4 are the three-stage responses.
        provider = _MockProvider(
            side_effect=[
                {},  # index 0 — skipped because fail_count=1 makes call 1 raise
                {"complexity": "simple", "confidence": 0.9, "reason": "debug"},
                {"domain": "coding", "candidates": ["coding"]},
                {"intent": "debug_code", "slots": {}, "missing_slots": []},
            ],
            fail_count=1,
        )
        pipeline = RoutingPipeline(provider=provider, routing_provider=provider)
        decision = await pipeline.route("debug python code")
        assert decision.domain.domain == "coding"
        assert decision.method == "llm_fallback"

    @pytest.mark.asyncio
    async def test_llm_success_path(self):
        response = {
            "complexity": "medium",
            "confidence": 0.85,
            "domain": "coding",
            "domain_candidates": ["coding"],
            "intent": "debug_code",
            "slots": {},
            "missing_slots": [],
            "reason": "debug",
        }
        provider = _MockProvider(response)
        pipeline = RoutingPipeline(routing_provider=provider)
        decision = await pipeline.route("fix this code bug")
        assert decision.method == "llm"
        assert decision.complexity.complexity == "medium"
        assert decision.domain.domain == "coding"

    @pytest.mark.asyncio
    async def test_no_routing_provider_uses_stages(self):
        provider = _MockProvider(side_effect=[
            {"complexity": "simple", "confidence": 0.9, "reason": "test"},
            {"domain": "coding", "candidates": ["coding"]},
            {"intent": "debug_code", "slots": {}, "missing_slots": []},
        ])
        pipeline = RoutingPipeline(provider=provider)
        decision = await pipeline.route("debug python code")
        assert decision.method == "llm"
        assert decision.domain.domain == "coding"

    @pytest.mark.asyncio
    async def test_trace_records_method(self):
        provider = _MockProvider(side_effect=[
            {"complexity": "simple", "confidence": 0.9, "reason": "test"},
            {"domain": "general", "candidates": ["general"]},
            {"intent": "general_query", "slots": {}, "missing_slots": []},
        ])
        pipeline = RoutingPipeline(provider=provider)
        decision = await pipeline.route("hello")
        trace_data = pipeline.get_routing_trace(decision)
        assert trace_data.method == "llm"


# ---------------------------------------------------------------------------
# Task 6.2: routing config independent model (mock provider)
# ---------------------------------------------------------------------------


class TestRoutingConfigIndependentModel:
    @pytest.mark.asyncio
    async def test_independent_routing_provider(self):
        """Pipeline uses independent provider for routing."""
        routing_response = {
            "complexity": "complex",
            "confidence": 0.9,
            "domain": "search",
            "domain_candidates": ["search"],
            "intent": "research_compare",
            "slots": {"output": "report"},
            "missing_slots": [],
            "reason": "research task",
        }
        routing_provider = _MockProvider(routing_response)
        pipeline = RoutingPipeline(routing_provider=routing_provider)
        decision = await pipeline.route("research and compare frameworks")
        assert decision.method == "llm"
        assert decision.domain.domain == "search"

    @pytest.mark.asyncio
    async def test_provider_only_uses_stages(self):
        """With provider only (no routing_provider), uses three-stage LLM path."""
        provider = _MockProvider(side_effect=[
            {"complexity": "simple", "confidence": 0.9, "reason": "test"},
            {"domain": "general", "candidates": ["general"]},
            {"intent": "debug_code", "slots": {}, "missing_slots": []},
        ])
        pipeline = RoutingPipeline(provider=provider)
        decision = await pipeline.route("debug my code")
        assert decision.method == "llm"


# ---------------------------------------------------------------------------
# Task 6.3: domain system_prompt injection (checked via ReActLoop)
# ---------------------------------------------------------------------------


class TestDomainSystemPromptInjection:
    @pytest.mark.asyncio
    async def test_domain_system_prompt_passed_to_react(self):
        from open_agent.agent.react import ReActLoop
        from open_agent.routing.domain import DomainRouteResult
        from open_agent.routing.complexity import ComplexityResult
        from open_agent.routing.intent import IntentResult

        loop = ReActLoop(tool_registry=None, provider=None)
        routing_decision = RoutingDecision(
            complexity=ComplexityResult(complexity="simple", confidence=0.95, method="llm"),
            domain=DomainRouteResult(
                domain="coding",
                candidates=["coding"],
                routed_as_fallback=False,
                system_prompt="You are an expert coding assistant.",
            ),
            intent=IntentResult(intent="debug_code"),
        )
        # Simulate what run() does
        loop._domain_system_prompt = (
            routing_decision.domain.system_prompt
            if routing_decision and routing_decision.domain and routing_decision.domain.system_prompt
            else None
        )
        assert loop._domain_system_prompt == "You are an expert coding assistant."


# ---------------------------------------------------------------------------
# Task 6.4: skip_planning controls PlanGenerator
# ---------------------------------------------------------------------------


class TestSkipPlanningControl:
    def test_simple_task_skips_planning(self):
        """Simple tasks with high confidence should skip planning."""
        from open_agent.routing.complexity import ComplexityResult
        from open_agent.routing.domain import DomainRouteResult
        from open_agent.routing.intent import IntentResult
        decision = RoutingDecision(
            complexity=ComplexityResult(complexity="simple", confidence=0.95, method="llm"),
            domain=DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=True),
            intent=IntentResult(intent="general_query"),
            skip_planning=True,
        )
        assert decision.skip_planning is True

    @pytest.mark.asyncio
    async def test_complex_task_needs_planning(self):
        provider = _MockProvider(side_effect=[
            {"complexity": "complex", "confidence": 0.85, "reason": "multi-step"},
            {"domain": "general", "candidates": ["general"]},
            {"intent": "general_query", "slots": {}, "missing_slots": []},
        ])
        pipeline = RoutingPipeline(provider=provider, fast_path_confidence=0.9)
        decision = await pipeline.route("搜索竞品数据并分析对比，生成报告")
        assert decision.skip_planning is False


# ---------------------------------------------------------------------------
# Task 6.5: missing_slots clarification flow
# ---------------------------------------------------------------------------


class TestMissingSlotsClarification:
    @pytest.mark.asyncio
    async def test_missing_slots_triggers_clarification(self):
        """When routing returns missing_slots, clarification should be generated."""
        from open_agent.routing.intent import IntentParser
        parser = IntentParser()
        slots = ["data_source", "time_range"]
        clarification = parser.generate_clarification(slots)
        assert "data_source" in clarification
        assert "time_range" in clarification

    @pytest.mark.asyncio
    async def test_no_missing_slots_no_clarification(self):
        from open_agent.routing.intent import IntentParser
        parser = IntentParser()
        clarification = parser.generate_clarification([])
        assert clarification == ""

    @pytest.mark.asyncio
    async def test_unified_router_with_missing_slots(self):
        response = {
            "complexity": "medium",
            "confidence": 0.85,
            "domain": "search",
            "domain_candidates": ["search"],
            "intent": "search_data",
            "slots": {},
            "missing_slots": ["data_source", "time_range"],
            "reason": "incomplete",
        }
        provider = _MockProvider(response)
        pipeline = RoutingPipeline(routing_provider=provider)
        decision = await pipeline.route("帮我搜索数据")
        assert decision.intent.missing_slots == ["data_source", "time_range"]


# ---------------------------------------------------------------------------
# Task 6.6: medium complexity test cases
# ---------------------------------------------------------------------------


class TestMediumComplexity:
    @pytest.mark.asyncio
    async def test_medium_via_unified_router(self):
        response = {
            "complexity": "medium",
            "confidence": 0.82,
            "domain": "coding",
            "domain_candidates": ["coding"],
            "intent": "write_code",
            "slots": {"language": "python"},
            "missing_slots": [],
            "reason": "single-step code generation",
        }
        provider = _MockProvider(response)
        pipeline = RoutingPipeline(routing_provider=provider)
        decision = await pipeline.route("帮我写一个 Python 排序函数")
        assert decision.complexity.complexity == "medium"
        assert decision.method == "llm"

    @pytest.mark.asyncio
    async def test_medium_complexity_still_plans(self):
        """medium complexity with confidence below threshold should not skip planning."""
        response = {
            "complexity": "medium",
            "confidence": 0.7,
            "domain": "coding",
            "domain_candidates": ["coding"],
            "intent": "write_code",
            "slots": {},
            "missing_slots": [],
            "reason": "code gen",
        }
        provider = _MockProvider(response)
        pipeline = RoutingPipeline(routing_provider=provider, fast_path_confidence=0.9)
        decision = await pipeline.route("write a sort function")
        assert decision.complexity.complexity == "medium"
        assert decision.skip_planning is False  # medium ≠ simple, so skip_planning is False

    @pytest.mark.asyncio
    async def test_routing_trace_includes_method(self):
        response = {
            "complexity": "medium",
            "confidence": 0.88,
            "domain": "coding",
            "domain_candidates": ["coding"],
            "intent": "debug_code",
            "slots": {},
            "missing_slots": [],
            "reason": "debug",
        }
        provider = _MockProvider(response)
        pipeline = RoutingPipeline(routing_provider=provider)
        decision = await pipeline.route("fix bug")
        trace_data = pipeline.get_routing_trace(decision)
        assert trace_data.method == "llm"
        assert trace_data.complexity_judge["complexity"] == "medium"
