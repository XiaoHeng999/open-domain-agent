"""Tests for the three-stage routing pipeline."""

from __future__ import annotations

import pytest

from open_agent.routing.complexity import RuleBasedComplexityJudge, ComplexityResult
from open_agent.routing.domain import DomainRouter, DomainRouteResult
from open_agent.routing.intent import IntentParser, IntentResult
from open_agent.routing.router import RoutingPipeline, RoutingDecision


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
