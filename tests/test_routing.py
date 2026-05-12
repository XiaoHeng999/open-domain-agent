"""Tests for the three-stage routing pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from open_agent.routing.complexity import RuleBasedComplexityJudge, ComplexityResult
from open_agent.routing.domain import DomainRouter, DomainRouteResult
from open_agent.routing.intent import IntentParser, IntentResult
from open_agent.routing.router import RoutingPipeline, RoutingDecision
from open_agent.routing.unified import UnifiedLLMRouter, UnifiedRoutingResult


class TestComplexityJudge:
    def test_simple_short_input(self):
        judge = RuleBasedComplexityJudge()
        result = judge.judge("hello")
        assert result.complexity == "simple"
        assert result.confidence > 0.9
        assert result.method == "rule"

    def test_complex_keywords(self):
        judge = RuleBasedComplexityJudge()
        result = judge.judge("搜索并分析竞品数据，然后生成报告")
        assert result.complexity == "complex"
        assert result.confidence > 0.7

    def test_english_complex(self):
        judge = RuleBasedComplexityJudge()
        result = judge.judge("Research and compare multiple frameworks, then summarize findings")
        assert result.complexity == "complex"

    def test_long_input(self):
        judge = RuleBasedComplexityJudge()
        long_input = "a" * 300
        result = judge.judge(long_input)
        assert result.complexity == "complex"

    def test_medium_simple(self):
        judge = RuleBasedComplexityJudge()
        result = judge.judge("What is Python?")
        assert result.complexity == "simple"


class TestDomainRouter:
    def test_coding_domain(self):
        router = DomainRouter()
        result = router.route("debug this python code error")
        assert result.domain == "coding"
        assert not result.routed_as_fallback

    def test_search_domain(self):
        router = DomainRouter()
        result = router.route("search for recent AI papers")
        assert result.domain == "search"

    def test_web_domain(self):
        router = DomainRouter()
        result = router.route("scrape website data with HTTP")
        assert result.domain == "web"

    def test_general_fallback(self):
        router = DomainRouter()
        result = router.route("hello how are you")
        assert result.domain == "general"
        assert result.routed_as_fallback

    def test_custom_domain(self):
        router = DomainRouter()
        router.register_domain("finance", "You are a finance expert.", keywords=["stock", "market", "投资"])
        result = router.route("analyze stock market trends")
        assert result.domain == "finance"

    def test_list_domains(self):
        router = DomainRouter()
        domains = router.list_domains()
        assert "coding" in domains
        assert "general" in domains


class TestIntentParser:
    @pytest.mark.asyncio
    async def test_coding_debug_intent(self):
        parser = IntentParser()
        result = await parser.parse("debug the error in my code", "coding")
        assert result.intent == "debug_code"

    @pytest.mark.asyncio
    async def test_coding_write_intent(self):
        parser = IntentParser()
        result = await parser.parse("implement a binary search tree", "coding")
        assert result.intent == "write_code"

    @pytest.mark.asyncio
    async def test_search_intent(self):
        parser = IntentParser()
        result = await parser.parse("search for recent papers on LLM", "search")
        assert result.intent == "search_query"

    @pytest.mark.asyncio
    async def test_general_intent(self):
        parser = IntentParser()
        result = await parser.parse("what is the weather", "general")
        assert result.intent == "general_query"

    def test_clarification(self):
        parser = IntentParser()
        q = parser.generate_clarification(["target_language", "framework"])
        assert "target_language" in q
        assert "framework" in q


class TestRoutingPipeline:
    @pytest.mark.asyncio
    async def test_simple_task_fast_path(self):
        pipeline = RoutingPipeline(fast_path_confidence=0.9)
        decision = await pipeline.route("hello")
        assert decision.skip_planning
        assert decision.complexity.complexity == "simple"

    @pytest.mark.asyncio
    async def test_complex_task_needs_planning(self):
        pipeline = RoutingPipeline()
        decision = await pipeline.route("搜索竞品数据并分析对比，生成报告")
        assert not decision.skip_planning
        assert decision.complexity.complexity == "complex"

    @pytest.mark.asyncio
    async def test_routing_trace(self):
        pipeline = RoutingPipeline()
        decision = await pipeline.route("debug my python code")
        trace_data = pipeline.get_routing_trace(decision)
        assert trace_data.complexity_judge["complexity"] in ("simple", "complex")
        assert trace_data.domain_router["domain"] == "coding"
        assert trace_data.intent_parser["intent"] == "debug_code"

    @pytest.mark.asyncio
    async def test_evaluate(self):
        pipeline = RoutingPipeline()
        test_set = [
            {"input": "hello", "expected_complexity": "simple", "expected_domain": "general"},
            {"input": "debug python code", "expected_complexity": "simple", "expected_domain": "coding"},
            {"input": "search and analyze data then summarize", "expected_complexity": "complex", "expected_domain": "search"},
        ]
        results = await pipeline.evaluate(test_set)
        assert "complexity_accuracy" in results
        assert "domain_accuracy" in results
        assert 0.0 <= results["complexity_accuracy"] <= 1.0


class TestUnifiedLLMRouterHistory:
    """Task 4.1: Test UnifiedLLMRouter.route() with history parameter."""

    def _make_router(self):
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(return_value={
            "complexity": "simple",
            "confidence": 0.9,
            "domain": "general",
            "domain_candidates": ["general"],
            "intent": "math",
            "slots": {"base_number": 4, "increment": 100},
            "missing_slots": [],
            "reason": "User wants to add 100 to the previous result of 4",
        })
        router = UnifiedLLMRouter(provider=provider, domains={})
        return router, provider

    @pytest.mark.asyncio
    async def test_history_injected_into_messages(self):
        router, provider = self._make_router()
        history = [
            {"role": "user", "content": "2+2等于几？"},
            {"role": "assistant", "content": "2+2=4"},
        ]
        await router.route("再加100等于几？", history=history)

        call_args = provider.complete_structured.call_args
        messages = call_args[0][0]
        # system, history[0], history[1], user_input
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1] == history[0]
        assert messages[2] == history[1]
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "再加100等于几？"

    @pytest.mark.asyncio
    async def test_no_history_backward_compatible(self):
        router, provider = self._make_router()
        await router.route("hello")

        call_args = provider.complete_structured.call_args
        messages = call_args[0][0]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_empty_history_backward_compatible(self):
        router, provider = self._make_router()
        await router.route("hello", history=[])

        call_args = provider.complete_structured.call_args
        messages = call_args[0][0]
        assert len(messages) == 2


class TestRoutingPipelineHistoryPassthrough:
    """Task 4.2: Test RoutingPipeline.route() history passthrough."""

    @pytest.mark.asyncio
    async def test_unified_path_receives_history(self):
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(return_value={
            "complexity": "simple",
            "confidence": 0.9,
            "domain": "general",
            "domain_candidates": ["general"],
            "intent": "math",
            "slots": {},
            "missing_slots": [],
            "reason": "test",
        })
        pipeline = RoutingPipeline(routing_provider=provider)

        history = [
            {"role": "user", "content": "2+2等于几？"},
            {"role": "assistant", "content": "2+2=4"},
        ]
        decision = await pipeline.route("再加100等于几？", history=history)
        assert decision.method == "llm"

        # Verify the provider received the history in messages
        call_args = provider.complete_structured.call_args
        messages = call_args[0][0]
        assert len(messages) == 4  # system + 2 history + user
        assert messages[1]["content"] == "2+2等于几？"

    @pytest.mark.asyncio
    async def test_keyword_fallback_no_history(self):
        pipeline = RoutingPipeline()  # no routing_provider → keyword path
        history = [{"role": "user", "content": "past"}]

        decision = await pipeline.route("hello", history=history)
        assert decision.method == "rule"

    @pytest.mark.asyncio
    async def test_no_history_default(self):
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(return_value={
            "complexity": "simple",
            "confidence": 0.95,
            "domain": "general",
            "domain_candidates": ["general"],
            "intent": "greet",
            "slots": {},
            "missing_slots": [],
            "reason": "greeting",
        })
        pipeline = RoutingPipeline(routing_provider=provider)

        decision = await pipeline.route("hello")
        assert decision.method == "llm"

        call_args = provider.complete_structured.call_args
        messages = call_args[0][0]
        assert len(messages) == 2  # system + user only


class TestMultiTurnRoutingIntegration:
    """Task 4.3: Multi-turn dialogue integration test."""

    @pytest.mark.asyncio
    async def test_follow_up_with_coreference(self):
        """First turn: '2+2等于几？' → Second turn: '再加100等于几？'
        With history, routing should infer base_number from context."""
        provider = AsyncMock()
        # First call: simple math question
        # Second call: follow-up with context
        provider.complete_structured = AsyncMock(return_value={
            "complexity": "simple",
            "confidence": 0.92,
            "domain": "general",
            "domain_candidates": ["general"],
            "intent": "math_add",
            "slots": {"base_number": 4, "increment": 100},
            "missing_slots": [],
            "reason": "User wants to add 100 to previous result of 4, inferred from history",
        })
        pipeline = RoutingPipeline(routing_provider=provider)

        history = [
            {"role": "user", "content": "2+2等于几？"},
            {"role": "assistant", "content": "2+2=4"},
        ]
        decision = await pipeline.route("再加100等于几？", history=history)

        # Should NOT have missing_slots — history provided context
        assert decision.intent.missing_slots == []
        assert decision.intent.slots.get("base_number") == 4
        assert decision.intent.slots.get("increment") == 100
        assert decision.method == "llm"

    @pytest.mark.asyncio
    async def test_no_history_triggers_missing_slots(self):
        """Same follow-up without history should report missing_slots."""
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(return_value={
            "complexity": "simple",
            "confidence": 0.85,
            "domain": "general",
            "domain_candidates": ["general"],
            "intent": "math_add",
            "slots": {},
            "missing_slots": ["base_number"],
            "reason": "No context, base_number is unknown",
        })
        pipeline = RoutingPipeline(routing_provider=provider)

        decision = await pipeline.route("再加100等于几？")
        assert "base_number" in decision.intent.missing_slots
