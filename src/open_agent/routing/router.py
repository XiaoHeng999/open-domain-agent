"""Routing pipeline — Complexity Judge → Domain Router → Intent Parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent
from open_agent.routing.complexity import ComplexityResult, RuleBasedComplexityJudge, LLMComplexityJudge
from open_agent.routing.domain import DomainRouteResult, DomainRouter
from open_agent.routing.intent import IntentResult, IntentParser
from open_agent.trace import SpanKind, Trace


@dataclass
class RoutingDecision:
    """Complete routing decision from all three stages."""

    complexity: ComplexityResult
    domain: DomainRouteResult
    intent: IntentResult
    skip_planning: bool = False
    fast_path_confidence: float = 0.9


@dataclass
class RoutingTraceData:
    """Three-stage routing trace data."""

    complexity_judge: dict[str, Any] = field(default_factory=dict)
    domain_router: dict[str, Any] = field(default_factory=dict)
    intent_parser: dict[str, Any] = field(default_factory=dict)


class RoutingPipeline(BaseComponent):
    """Three-stage routing pipeline: Complexity → Domain → Intent."""

    def __init__(
        self,
        complexity_method: str = "rule",
        provider: Any = None,
        fast_path_confidence: float = 0.9,
        domains: list[str] | None = None,
    ) -> None:
        if complexity_method == "llm" and provider:
            self._complexity_judge = LLMComplexityJudge(provider)
        else:
            self._complexity_judge = RuleBasedComplexityJudge()
        self._domain_router = DomainRouter()
        self._intent_parser = IntentParser(provider)
        self._fast_path_confidence = fast_path_confidence

    async def route(self, user_input: str, trace: Trace | None = None) -> RoutingDecision:
        """Execute three-stage routing pipeline."""
        routing_span = None
        if trace:
            routing_span = trace.create_span("routing_pipeline", kind=SpanKind.ROUTING)

        # Stage 1: Complexity Judge
        if isinstance(self._complexity_judge, LLMComplexityJudge):
            complexity = await self._complexity_judge.judge(user_input)
        else:
            complexity = self._complexity_judge.judge(user_input)

        # Stage 2: Domain Router
        domain = self._domain_router.route(user_input)

        # Stage 3: Intent Parser
        intent = await self._intent_parser.parse(user_input, domain.domain)

        # Determine if planning should be skipped
        skip_planning = (
            complexity.complexity == "simple"
            and complexity.confidence >= self._fast_path_confidence
        )

        decision = RoutingDecision(
            complexity=complexity,
            domain=domain,
            intent=intent,
            skip_planning=skip_planning,
            fast_path_confidence=self._fast_path_confidence,
        )

        if routing_span:
            routing_span.set_attribute("complexity", complexity.complexity)
            routing_span.set_attribute("domain", domain.domain)
            routing_span.set_attribute("intent", intent.intent)
            routing_span.set_attribute("skip_planning", skip_planning)
            routing_span.finish()

        return decision

    def get_routing_trace(self, decision: RoutingDecision) -> RoutingTraceData:
        """Extract trace data from a routing decision."""
        return RoutingTraceData(
            complexity_judge={
                "complexity": decision.complexity.complexity,
                "confidence": decision.complexity.confidence,
                "method": decision.complexity.method,
                "reason": decision.complexity.reason,
            },
            domain_router={
                "domain": decision.domain.domain,
                "candidates": decision.domain.candidates,
                "routed_as_fallback": decision.domain.routed_as_fallback,
            },
            intent_parser={
                "intent": decision.intent.intent,
                "slots": decision.intent.slots,
                "missing_slots": decision.intent.missing_slots,
            },
        )

    async def evaluate(self, test_set: list[dict[str, Any]]) -> dict[str, float]:
        """Evaluate routing accuracy on a test set."""
        results = {
            "complexity_accuracy": 0.0,
            "domain_accuracy": 0.0,
            "intent_accuracy": 0.0,
        }
        if not test_set:
            return results

        correct = {"complexity": 0, "domain": 0, "intent": 0}
        total = len(test_set)

        for case in test_set:
            decision = await self.route(case["input"])
            if decision.complexity.complexity == case.get("expected_complexity"):
                correct["complexity"] += 1
            if decision.domain.domain == case.get("expected_domain"):
                correct["domain"] += 1
            if decision.intent.intent == case.get("expected_intent"):
                correct["intent"] += 1

        results["complexity_accuracy"] = correct["complexity"] / total
        results["domain_accuracy"] = correct["domain"] / total
        results["intent_accuracy"] = correct["intent"] / total
        return results
