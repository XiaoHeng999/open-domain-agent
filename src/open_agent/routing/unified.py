"""UnifiedLLMRouter — single LLM call replacing the three-stage keyword pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent

logger = logging.getLogger("open_agent")

_SYSTEM_PROMPT_TEMPLATE = """\
You are a request classifier for a multi-domain AI agent. Given a user message, output a JSON object with:

- "complexity": "simple" | "medium" | "complex"
- "confidence": 0.0-1.0
- "domain": one of the available domains below
- "domain_candidates": ordered list of plausible domains (best first)
- "intent": short snake_case label describing the intent
- "slots": extracted parameters as key-value pairs
- "missing_slots": list of required parameter names that are missing or ambiguous
- "reason": brief explanation

## Complexity rules
- simple: greetings, factual questions, single-step tasks
- medium: single-step tasks requiring generation or transformation (e.g. write a function)
- complex: multi-step tasks, research, analysis, comparisons, reports

## Missing slots inferability rules
- Only mark a slot as missing when the parameter is completely uninferrable AND the task cannot proceed without it.
- If a parameter can be reasonably determined by the downstream agent via tools or common sense (e.g. file name, programming language, output format), treat it as inferrable and do NOT include it in missing_slots.
- When conversation history provides enough context to fill a slot, do NOT mark it as missing.

## Available domains
{domains_description}

## Output JSON schema
{{
  "complexity": "simple" | "medium" | "complex",
  "confidence": 0.0-1.0,
  "domain": "<domain_name>",
  "domain_candidates": ["<domain1>", ...],
  "intent": "<intent_name>",
  "slots": {{}},
  "missing_slots": [],
  "reason": "<brief explanation>"
}}

## Examples

Example 1 (Chinese):
User: "帮我看看这段代码哪有毛病"
Output: {{"complexity": "simple", "confidence": 0.92, "domain": "coding", "domain_candidates": ["coding", "general"], "intent": "debug_code", "slots": {{"query": "帮我看看这段代码哪有毛病"}}, "missing_slots": [], "reason": "Debugging request in coding domain"}}

Example 2 (English):
User: "Research competing frameworks and write a comparison report"
Output: {{"complexity": "complex", "confidence": 0.88, "domain": "search", "domain_candidates": ["search", "coding", "general"], "intent": "research_compare", "slots": {{"targets": "competing frameworks", "output": "comparison report"}}, "missing_slots": [], "reason": "Multi-step research and comparison task"}}

Example 3 (Chinese, missing info):
User: "帮我搜索数据"
Output: {{"complexity": "medium", "confidence": 0.85, "domain": "search", "domain_candidates": ["search", "general"], "intent": "search_data", "slots": {{}}, "missing_slots": ["data_source", "time_range"], "reason": "Search request but target data not specified"}}

Example 4 (Chinese, inferrable params — no file name given):
User: "帮我创建一个等差数列求和公式的代码"
Output: {{"complexity": "medium", "confidence": 0.90, "domain": "coding", "domain_candidates": ["coding", "general"], "intent": "create_code", "slots": {{"task": "等差数列求和公式"}}, "missing_slots": [], "reason": "File name and language are inferrable by agent via tools"}}
"""


@dataclass
class UnifiedRoutingResult:
    """Structured output from UnifiedLLMRouter."""

    complexity: str
    confidence: float
    domain: str
    domain_candidates: list[str] = field(default_factory=list)
    intent: str = ""
    slots: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    reason: str = ""


class UnifiedLLMRouter(BaseComponent):
    """Single-LLM-call router replacing the three-stage keyword pipeline."""

    def __init__(self, provider: Any, domains: dict[str, dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._provider = provider
        self._domains = domains or {}
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        lines: list[str] = []
        for name, cfg in self._domains.items():
            kw = cfg.get("keywords", [])
            kw_str = ", ".join(kw[:10]) if kw else "(keyword-based matching)"
            lines.append(f"- **{name}**: {cfg.get('system_prompt', '')} — keywords: {kw_str}")
        domains_description = "\n".join(lines) if lines else "- general: General-purpose assistant"
        return _SYSTEM_PROMPT_TEMPLATE.format(domains_description=domains_description)

    async def route(
        self,
        user_input: str,
        history: list[dict[str, str]] | None = None,
    ) -> UnifiedRoutingResult:
        """Route user input via a single LLM call. Raises on failure (caller handles fallback)."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_input})
        result = await self._provider.complete_structured(
            messages,
            schema={
                "complexity": "string",
                "confidence": "number",
                "domain": "string",
                "domain_candidates": "array",
                "intent": "string",
                "slots": "object",
                "missing_slots": "array",
                "reason": "string",
            },
        )
        return self._parse_result(result)

    @staticmethod
    def _parse_result(raw: dict[str, Any]) -> UnifiedRoutingResult:
        complexity = raw.get("complexity", "simple")
        if complexity not in ("simple", "medium", "complex"):
            complexity = "simple"

        confidence = float(raw.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return UnifiedRoutingResult(
            complexity=complexity,
            confidence=confidence,
            domain=raw.get("domain", "general"),
            domain_candidates=raw.get("domain_candidates", []),
            intent=raw.get("intent", "unknown"),
            slots=raw.get("slots", {}),
            missing_slots=raw.get("missing_slots", []),
            reason=raw.get("reason", ""),
        )
