"""Complexity Judge — LLM-based simple/medium/complex classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from open_agent.base import BaseComponent
from open_agent.model import parse_json_response

_VALID_COMPLEXITIES = {"simple", "medium", "complex"}


@dataclass
class ComplexityResult:
    """Output of complexity judgment."""

    complexity: str  # "simple" | "medium" | "complex"
    confidence: float
    method: str  # always "llm"
    reason: str | None = None


class LLMComplexityJudge(BaseComponent):
    """LLM-based complexity judge — uses lightweight model for ternary classification."""

    _SYSTEM_PROMPT = (
        "Classify the following task into one of three complexity levels:\n"
        "- simple: greetings, factual questions, single-step tasks that can be answered directly\n"
        "- medium: single-step tasks requiring generation or transformation (e.g. write a function, translate text)\n"
        "- complex: multi-step tasks, research, analysis, comparisons, reports, or tasks requiring planning\n\n"
        'Respond with JSON: {"complexity": "simple"|"medium"|"complex", "confidence": 0.0-1.0, "reason": "..."}'
    )

    def __init__(self, provider: Any) -> None:
        super().__init__()
        self._provider = provider

    async def judge(self, user_input: str) -> ComplexityResult:
        messages = [
            {"role": "system", "content": self._SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]
        response = await self._provider.complete_with_tools(messages, [])
        result = parse_json_response(response.text)
        complexity = result.get("complexity", "simple")
        if complexity not in _VALID_COMPLEXITIES:
            complexity = "simple"
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        return ComplexityResult(
            complexity=complexity,
            confidence=confidence,
            method="llm",
            reason=result.get("reason"),
        )
