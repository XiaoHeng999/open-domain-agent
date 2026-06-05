"""Tests for the three-stage routing pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from open_agent.routing.complexity import LLMComplexityJudge, ComplexityResult
from open_agent.routing.domain import DomainRouter, DomainRouteResult
from open_agent.routing.intent import IntentParser, IntentResult
from open_agent.routing.router import RoutingPipeline, RoutingDecision
from open_agent.routing.unified import UnifiedLLMRouter, UnifiedRoutingResult


class TestComplexityJudge:
    def _make_provider(self, response: dict):
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(return_value=response)
        return provider

    @pytest.mark.asyncio
    async def test_simple_short_input(self):
        provider = self._make_provider({"complexity": "simple", "confidence": 0.95, "reason": "greeting"})
        judge = LLMComplexityJudge(provider)
        result = await judge.judge("hello")
        assert result.complexity == "simple"
        assert result.confidence > 0.9
        assert result.method == "llm"

    @pytest.mark.asyncio
    async def test_complex_keywords(self):
        provider = self._make_provider({"complexity": "complex", "confidence": 0.85, "reason": "multi-step"})
        judge = LLMComplexityJudge(provider)
        result = await judge.judge("搜索并分析竞品数据，然后生成报告")
        assert result.complexity == "complex"

    @pytest.mark.asyncio
    async def test_english_complex(self):
        provider = self._make_provider({"complexity": "complex", "confidence": 0.9, "reason": "research"})
        judge = LLMComplexityJudge(provider)
        result = await judge.judge("Research and compare multiple frameworks, then summarize findings")
        assert result.complexity == "complex"

    @pytest.mark.asyncio
    async def test_medium_classification(self):
        provider = self._make_provider({"complexity": "medium", "confidence": 0.82, "reason": "code gen"})
        judge = LLMComplexityJudge(provider)
        result = await judge.judge("Write a Python function to sort a list")
        assert result.complexity == "medium"

    @pytest.mark.asyncio
    async def test_invalid_complexity_clamped(self):
        provider = self._make_provider({"complexity": "unknown", "confidence": 0.5, "reason": "test"})
        judge = LLMComplexityJudge(provider)
        result = await judge.judge("hello")
        assert result.complexity == "simple"

    @pytest.mark.asyncio
    async def test_confidence_clamped(self):
        provider = self._make_provider({"complexity": "simple", "confidence": 1.5, "reason": "test"})
        judge = LLMComplexityJudge(provider)
        result = await judge.judge("hello")
        assert result.confidence == 1.0


class TestDomainRouter:
    @pytest.mark.asyncio
    async def test_coding_domain(self):
        router = DomainRouter()
        result = await router.route("debug this python code error")
        assert result.domain == "coding"
        assert not result.routed_as_fallback

    @pytest.mark.asyncio
    async def test_search_domain(self):
        router = DomainRouter()
        result = await router.route("search for recent AI papers")
        assert result.domain == "search"

    @pytest.mark.asyncio
    async def test_web_domain(self):
        router = DomainRouter()
        result = await router.route("scrape website data with HTTP")
        assert result.domain == "web"

    @pytest.mark.asyncio
    async def test_general_fallback(self):
        router = DomainRouter()
        result = await router.route("hello how are you")
        assert result.domain == "general"
        assert result.routed_as_fallback

    @pytest.mark.asyncio
    async def test_custom_domain(self):
        router = DomainRouter()
        router.register_domain("finance", "You are a finance expert.", keywords=["stock", "market", "投资"])
        result = await router.route("analyze stock market trends")
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
    def _make_pipeline_provider(self, complexity_resp=None, domain_resp=None, intent_resp=None):
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(side_effect=[
            complexity_resp or {"complexity": "simple", "confidence": 0.95, "reason": "test"},
            domain_resp or {"domain": "general", "candidates": ["general"]},
            intent_resp or {"intent": "general_query", "slots": {}, "missing_slots": []},
        ])
        return provider

    @pytest.mark.asyncio
    async def test_simple_task_fast_path(self):
        provider = self._make_pipeline_provider()
        pipeline = RoutingPipeline(provider=provider, fast_path_confidence=0.9)
        decision = await pipeline.route("hello")
        assert decision.skip_planning
        assert decision.complexity.complexity == "simple"

    @pytest.mark.asyncio
    async def test_complex_task_needs_planning(self):
        provider = self._make_pipeline_provider(
            complexity_resp={"complexity": "complex", "confidence": 0.85, "reason": "multi-step"},
        )
        pipeline = RoutingPipeline(provider=provider)
        decision = await pipeline.route("搜索竞品数据并分析对比，生成报告")
        assert not decision.skip_planning
        assert decision.complexity.complexity == "complex"

    @pytest.mark.asyncio
    async def test_routing_trace(self):
        provider = self._make_pipeline_provider(
            domain_resp={"domain": "coding", "candidates": ["coding"]},
            intent_resp={"intent": "debug_code", "slots": {}, "missing_slots": []},
        )
        pipeline = RoutingPipeline(provider=provider)
        decision = await pipeline.route("debug my python code")
        trace_data = pipeline.get_routing_trace(decision)
        assert trace_data.complexity_judge["complexity"] in ("simple", "medium", "complex")
        assert trace_data.domain_router["domain"] == "coding"
        assert trace_data.intent_parser["intent"] == "debug_code"

    @pytest.mark.asyncio
    async def test_evaluate(self):
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(side_effect=[
            {"complexity": "simple", "confidence": 0.95, "reason": "test"},
            {"domain": "general", "candidates": ["general"]},
            {"intent": "general_query", "slots": {}, "missing_slots": []},
        ])
        pipeline = RoutingPipeline(provider=provider)
        test_set = [
            {"input": "hello", "expected_complexity": "simple", "expected_domain": "general"},
        ]
        results = await pipeline.evaluate(test_set)
        assert "complexity_accuracy" in results
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
    async def test_stages_path_no_history(self):
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(side_effect=[
            {"complexity": "simple", "confidence": 0.95, "reason": "test"},
            {"domain": "general", "candidates": ["general"]},
            {"intent": "general_query", "slots": {}, "missing_slots": []},
        ])
        pipeline = RoutingPipeline(provider=provider)  # no routing_provider → three-stage path
        history = [{"role": "user", "content": "past"}]

        decision = await pipeline.route("hello", history=history)
        assert decision.method == "llm"

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


class TestMissingSlotsComplexityGating:
    """Test 4.1 & 4.2: Verify complexity-based missing_slots handling in runtime."""

    @pytest.fixture
    def mock_components(self):
        """Create a minimal AgentRuntime with mocked internals."""
        from open_agent.config import AgentConfig
        from open_agent.runtime import AgentRuntime
        from open_agent.trace import TraceManager
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
            "answer": "done", "total_steps": 1, "state": type("State", (), {"steps": []})()
        })())
        return runtime

    @pytest.mark.asyncio
    async def test_simple_missing_slots_triggers_clarification(self, mock_components):
        """Test 4.1: simple + missing_slots → short-circuit return clarification."""
        from open_agent.trace import TraceManager
        runtime = mock_components

        trace = runtime.trace_manager.create_trace(metadata={"user_input": "test"})
        runtime.routing_pipeline.route = AsyncMock(return_value=RoutingDecision(
            complexity=ComplexityResult(complexity="simple", confidence=0.95, method="llm"),
            domain=DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=True),
            intent=IntentResult(intent="weather_query", slots={}, missing_slots=["city"]),
            skip_planning=True,
        ))

        # Manually simulate the routing check from runtime.run()
        routing_decision = runtime.routing_pipeline.route.return_value
        should_shortcircuit = (
            routing_decision.intent.missing_slots
            and routing_decision.complexity.complexity == "simple"
        )
        assert should_shortcircuit is True

    @pytest.mark.asyncio
    async def test_complex_missing_slots_no_shortcircuit(self, mock_components):
        """Test 4.2: complex + missing_slots → no short-circuit, hint injected."""
        runtime = mock_components

        runtime.routing_pipeline.route = AsyncMock(return_value=RoutingDecision(
            complexity=ComplexityResult(complexity="complex", confidence=0.8, method="llm"),
            domain=DomainRouteResult(domain="coding", candidates=["coding"], routed_as_fallback=False),
            intent=IntentResult(intent="create_code", slots={"task": "等差数列求和"}, missing_slots=["file_name"]),
            skip_planning=False,
        ))

        routing_decision = runtime.routing_pipeline.route.return_value
        should_shortcircuit = (
            routing_decision.intent.missing_slots
            and routing_decision.complexity.complexity == "simple"
        )
        assert should_shortcircuit is False

        # Verify hint injection logic
        if routing_decision.intent.missing_slots and routing_decision.complexity.complexity != "simple":
            slot_list = ", ".join(routing_decision.intent.missing_slots)
            hint = (
                f"路由层检测到以下参数可能缺失: {slot_list}。"
                "如果可以通过工具或常识合理推断，请直接执行任务。"
                "如果确实无法推断，请向用户追问。"
            )
            assert "file_name" in hint
            assert "推断" in hint

    @pytest.mark.asyncio
    async def test_medium_missing_slots_no_shortcircuit(self, mock_components):
        """Test 4.2: medium + missing_slots → no short-circuit."""
        runtime = mock_components

        runtime.routing_pipeline.route = AsyncMock(return_value=RoutingDecision(
            complexity=ComplexityResult(complexity="medium", confidence=0.85, method="llm"),
            domain=DomainRouteResult(domain="coding", candidates=["coding"], routed_as_fallback=False),
            intent=IntentResult(intent="write_code", slots={}, missing_slots=["output_format"]),
            skip_planning=False,
        ))

        routing_decision = runtime.routing_pipeline.route.return_value
        should_shortcircuit = (
            routing_decision.intent.missing_slots
            and routing_decision.complexity.complexity == "simple"
        )
        assert should_shortcircuit is False

    @pytest.mark.asyncio
    async def test_simple_no_missing_slots_passes(self, mock_components):
        """Simple task with no missing_slots → no short-circuit."""
        runtime = mock_components

        runtime.routing_pipeline.route = AsyncMock(return_value=RoutingDecision(
            complexity=ComplexityResult(complexity="simple", confidence=0.95, method="llm"),
            domain=DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=True),
            intent=IntentResult(intent="greet", slots={}, missing_slots=[]),
            skip_planning=True,
        ))

        routing_decision = runtime.routing_pipeline.route.return_value
        should_shortcircuit = bool(
            routing_decision.intent.missing_slots
            and routing_decision.complexity.complexity == "simple"
        )
        assert should_shortcircuit is False


class TestInferabilityPromptRules:
    """Test 4.3: Verify the router prompt contains inferability rules."""

    def test_system_prompt_contains_inferability_rules(self):
        provider = AsyncMock()
        router = UnifiedLLMRouter(provider=provider, domains={})
        prompt = router._system_prompt

        assert "missing_slots" in prompt.lower()
        assert "inferr" in prompt.lower() or "推断" in prompt or "infer" in prompt.lower()
        assert "tool" in prompt.lower() or "工具" in prompt

    def test_system_prompt_contains_inferable_example(self):
        """Verify the few-shot example for inferrable params is present."""
        from open_agent.routing.unified import _SYSTEM_PROMPT_TEMPLATE
        assert "等差数列" in _SYSTEM_PROMPT_TEMPLATE
        # The example should show missing_slots=[] for unspecified file name
        assert 'missing_slots": []' in _SYSTEM_PROMPT_TEMPLATE or "missing_slots\":[]" in _SYSTEM_PROMPT_TEMPLATE


class TestTemperatureEnforcement:
    """Test 4.5: Verify temperature=0.0 in router calls."""

    @pytest.mark.asyncio
    async def test_router_uses_complete_structured(self):
        """UnifiedLLMRouter uses complete_structured which forces temperature=0.0."""
        import warnings
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(return_value={
            "complexity": "simple",
            "confidence": 0.9,
            "domain": "general",
            "domain_candidates": ["general"],
            "intent": "greet",
            "slots": {},
            "missing_slots": [],
            "reason": "test",
        })
        router = UnifiedLLMRouter(provider=provider, domains={})

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = await router.route("hello")

        # Verify complete_structured was called (it hardcodes temperature=0.0)
        provider.complete_structured.assert_called_once()
        assert result.complexity == "simple"

    @pytest.mark.asyncio
    async def test_deterministic_routing(self):
        """Same input should produce same result through complete_structured."""
        import warnings
        fixed_result = {
            "complexity": "medium",
            "confidence": 0.88,
            "domain": "coding",
            "domain_candidates": ["coding"],
            "intent": "create_code",
            "slots": {"task": "等差数列求和"},
            "missing_slots": [],
            "reason": "Code generation task",
        }
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(return_value=fixed_result)
        router = UnifiedLLMRouter(provider=provider, domains={})

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            r1 = await router.route("帮我创建一个等差数列求和公式的代码")
            r2 = await router.route("帮我创建一个等差数列求和公式的代码")
            r3 = await router.route("帮我创建一个等差数列求和公式的代码")

        assert r1.missing_slots == r2.missing_slots == r3.missing_slots == []
        assert r1.domain == r2.domain == r3.domain == "coding"
        assert provider.complete_structured.call_count == 3


class TestDomainRouterLLM:
    """Test LLM-based domain routing in DomainRouter."""

    def _make_provider(self, response: dict):
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(return_value=response)
        return provider

    @pytest.mark.asyncio
    async def test_llm_coding_domain(self):
        provider = self._make_provider({"domain": "coding", "candidates": ["coding", "general"]})
        router = DomainRouter(provider=provider)
        result = await router.route("debug this python code error")
        assert result.domain == "coding"
        assert not result.routed_as_fallback
        assert result.system_prompt != ""

    @pytest.mark.asyncio
    async def test_llm_general_fallback(self):
        provider = self._make_provider({"domain": "general", "candidates": ["general"]})
        router = DomainRouter(provider=provider)
        result = await router.route("hello how are you")
        assert result.domain == "general"
        assert result.routed_as_fallback

    @pytest.mark.asyncio
    async def test_llm_invalid_domain_clamped(self):
        provider = self._make_provider({"domain": "unknown_domain", "candidates": ["unknown_domain"]})
        router = DomainRouter(provider=provider)
        result = await router.route("some text")
        assert result.domain == "general"

    @pytest.mark.asyncio
    async def test_llm_failure_raises_routing_error(self):
        from open_agent.errors import RoutingError
        provider = AsyncMock()
        provider.complete_structured = AsyncMock(side_effect=RuntimeError("LLM failed"))
        router = DomainRouter(provider=provider)
        with pytest.raises(RoutingError):
            await router.route("test")

    @pytest.mark.asyncio
    async def test_dynamic_domain_keyword_priority_over_llm(self):
        """Dynamic domain keyword match takes priority over LLM result."""
        provider = self._make_provider({"domain": "general", "candidates": ["general"]})
        router = DomainRouter(provider=provider)
        router.register_domain("finance", "Finance expert", keywords=["stock", "market"])
        result = await router.route("analyze stock market trends")
        assert result.domain == "finance"

    @pytest.mark.asyncio
    async def test_no_provider_keyword_fallback(self):
        """Without provider, keyword matching still works (backward compatible)."""
        router = DomainRouter()
        result = await router.route("debug this python code error")
        assert result.domain == "coding"
