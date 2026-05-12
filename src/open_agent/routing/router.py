"""Routing pipeline — Complexity Judge → Domain Router → Intent Parser."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent
from open_agent.routing.complexity import ComplexityResult, RuleBasedComplexityJudge, LLMComplexityJudge
from open_agent.routing.domain import DomainRouteResult, DomainRouter, _DOMAINS
from open_agent.routing.intent import IntentResult, IntentParser
from open_agent.routing.unified import UnifiedLLMRouter
from open_agent.trace import SpanKind, Trace

logger = logging.getLogger("open_agent")


def _filter_domains(domain_names: list[str]) -> dict[str, dict[str, Any]]:
    """Filter the default _DOMAINS dict to only include named domains."""
    return {name: _DOMAINS[name] for name in domain_names if name in _DOMAINS}


@dataclass
class RoutingDecision:
    """Complete routing decision from all three stages."""

    complexity: ComplexityResult
    domain: DomainRouteResult
    intent: IntentResult
    skip_planning: bool = False
    fast_path_confidence: float = 0.9
    method: str = "rule"  # "llm" | "rule_fallback" | "rule"


@dataclass
class RoutingTraceData:
    """Three-stage routing trace data."""

    complexity_judge: dict[str, Any] = field(default_factory=dict)
    domain_router: dict[str, Any] = field(default_factory=dict)
    intent_parser: dict[str, Any] = field(default_factory=dict)
    method: str = "rule"


class RoutingPipeline(BaseComponent):
    """Three-stage routing pipeline: Complexity → Domain → Intent.

    When a *routing_provider* is supplied, the unified LLM router is used
    as the primary path.  On failure, the rule-based keyword pipeline serves
    as fallback.  Without a provider the keyword pipeline runs directly.
    """

    def __init__(
        self,
        complexity_method: str = "rule",
        provider: Any = None,
        fast_path_confidence: float = 0.9,
        domains: list[str] | None = None,
        routing_provider: Any = None,
    ) -> None:
        super().__init__()
        if complexity_method == "llm" and provider:
            self._complexity_judge = LLMComplexityJudge(provider)
        else:
            self._complexity_judge = RuleBasedComplexityJudge()

        filtered = _filter_domains(domains) if domains else None
        self._domain_router = DomainRouter(domains=filtered)
        self._intent_parser = IntentParser(provider)
        self._fast_path_confidence = fast_path_confidence
        self._domains_dict = filtered

        # Unified LLM router (primary path when available)
        self._unified_router: UnifiedLLMRouter | None = None
        if routing_provider is not None:
            self._unified_router = UnifiedLLMRouter(
                provider=routing_provider,
                domains=self._domain_router._domains,
            )

    async def route(self, user_input: str, trace: Trace | None = None) -> RoutingDecision:
        """Execute routing — unified LLM path or keyword fallback."""
        routing_span = None
        if trace:
            routing_span = trace.create_span("routing_pipeline", kind=SpanKind.ROUTING)

        if self._unified_router is not None:
            decision = await self._route_unified(user_input, routing_span)
        else:
            decision = await self._route_keyword(user_input, routing_span)
            decision.method = "rule"

        if routing_span:
            routing_span.set_attribute("complexity", decision.complexity.complexity)
            routing_span.set_attribute("domain", decision.domain.domain)
            routing_span.set_attribute("intent", decision.intent.intent)
            routing_span.set_attribute("skip_planning", decision.skip_planning)
            routing_span.set_attribute("method", decision.method)
            routing_span.finish()

        return decision

    # -- unified LLM path ----------------------------------------------------

    async def _route_unified(
        self, user_input: str, routing_span: Any,
    ) -> RoutingDecision:
        try:
            result = await self._unified_router.route(user_input)
        except Exception:
            logger.warning("Unified LLM router failed, falling back to keyword pipeline")
            decision = await self._route_keyword(user_input, routing_span)
            decision.method = "rule_fallback"
            return decision

        complexity = ComplexityResult(
            complexity=result.complexity,
            confidence=result.confidence,
            method="llm",
            reason=result.reason,
        )

        domain_config = self._domain_router._domains.get(result.domain, {})
        domain = DomainRouteResult(
            domain=result.domain,
            candidates=result.domain_candidates,
            routed_as_fallback=result.domain == "general",
            system_prompt=domain_config.get("system_prompt", ""),
        )

        intent = IntentResult(
            intent=result.intent,
            slots=result.slots,
            missing_slots=result.missing_slots,
        )

        skip_planning = (
            result.complexity == "simple"
            and result.confidence >= self._fast_path_confidence
        )

        return RoutingDecision(
            complexity=complexity,
            domain=domain,
            intent=intent,
            skip_planning=skip_planning,
            fast_path_confidence=self._fast_path_confidence,
            method="llm",
        )

    # -- keyword pipeline path -----------------------------------------------

    async def _route_keyword(
        self, user_input: str, routing_span: Any,
    ) -> RoutingDecision:
        if isinstance(self._complexity_judge, LLMComplexityJudge):
            complexity = await self._complexity_judge.judge(user_input)
        else:
            complexity = self._complexity_judge.judge(user_input)

        domain = self._domain_router.route(user_input)
        intent = await self._intent_parser.parse(user_input, domain.domain)

        skip_planning = (
            complexity.complexity == "simple"
            and complexity.confidence >= self._fast_path_confidence
        )

        return RoutingDecision(
            complexity=complexity,
            domain=domain,
            intent=intent,
            skip_planning=skip_planning,
            fast_path_confidence=self._fast_path_confidence,
        )

    # -- trace / eval --------------------------------------------------------

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
            method=decision.method,
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
