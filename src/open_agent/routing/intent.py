"""Intent Parser — structured intent + slot extraction within a domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent


@dataclass
class IntentResult:
    """Result of intent parsing."""

    intent: str
    slots: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    clarification: str | None = None


class IntentParser(BaseComponent):
    """Parse structured intent + slots from user input within a domain."""

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider

    async def parse(self, user_input: str, domain: str) -> IntentResult:
        """Extract structured intent and slots from user input."""
        if self._provider:
            return await self._llm_parse(user_input, domain)
        return self._rule_parse(user_input, domain)

    def _rule_parse(self, user_input: str, domain: str) -> IntentResult:
        """Rule-based intent parsing."""
        input_lower = user_input.lower().strip()

        # Domain-specific intent patterns
        if domain == "coding":
            return self._parse_coding_intent(input_lower)
        elif domain == "search":
            return self._parse_search_intent(input_lower)
        elif domain == "web":
            return self._parse_web_intent(input_lower)

        return IntentResult(intent="general_query", slots={"query": user_input})

    def _parse_coding_intent(self, text: str) -> IntentResult:
        if any(kw in text for kw in ["debug", "fix", "bug", "修复", "调试"]):
            return IntentResult(intent="debug_code", slots={"query": text})
        if any(kw in text for kw in ["review", "审查"]):
            return IntentResult(intent="review_code", slots={"query": text})
        if any(kw in text for kw in ["implement", "create", "实现", "编写", "写"]):
            return IntentResult(intent="write_code", slots={"query": text})
        if any(kw in text for kw in ["refactor", "重构", "优化"]):
            return IntentResult(intent="refactor_code", slots={"query": text})
        return IntentResult(intent="code_query", slots={"query": text})

    def _parse_search_intent(self, text: str) -> IntentResult:
        return IntentResult(intent="search_query", slots={"query": text})

    def _parse_web_intent(self, text: str) -> IntentResult:
        if any(kw in text for kw in ["scrape", "爬取", "抓取"]):
            return IntentResult(intent="web_scrape", slots={"query": text})
        return IntentResult(intent="web_query", slots={"query": text})

    async def _llm_parse(self, user_input: str, domain: str) -> IntentResult:
        """LLM-based intent parsing with structured output."""
        messages = [
            {"role": "system", "content": (
                f"Parse the following user input in the '{domain}' domain. "
                "Extract the intent and any relevant slots (parameters). "
                "Respond with JSON: {\"intent\": \"...\", \"slots\": {...}, \"missing_slots\": [...]}"
            )},
            {"role": "user", "content": user_input},
        ]
        try:
            result = await self._provider.complete_structured(
                messages,
                schema={"intent": "string", "slots": "object", "missing_slots": "array"},
            )
            return IntentResult(
                intent=result.get("intent", "unknown"),
                slots=result.get("slots", {}),
                missing_slots=result.get("missing_slots", []),
            )
        except Exception:
            return self._rule_parse(user_input, domain)

    def generate_clarification(self, missing_slots: list[str]) -> str:
        """Generate a clarification question for missing slots."""
        if not missing_slots:
            return ""
        slot_list = ", ".join(missing_slots)
        return f"Please provide the following information: {slot_list}"
