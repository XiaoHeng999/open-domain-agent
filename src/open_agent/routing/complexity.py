"""Complexity Judge — rule-based + optional LLM for simple/complex classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent

# Keywords suggesting complex multi-step tasks
_COMPLEX_KEYWORDS = {
    "分析", "对比", "调研", "搜索", "整理", "汇总", "比较", "生成报告",
    "analyze", "compare", "research", "search", "summarize", "investigate",
    "build", "create", "implement", "refactor", "multi-step",
    "然后", "接着", "之后", "最后", "and then", "after that", "finally",
}


@dataclass
class ComplexityResult:
    """Output of complexity judgment."""

    complexity: str  # "simple" | "complex"
    confidence: float
    method: str  # "rule" | "llm"
    reason: str | None = None


class RuleBasedComplexityJudge(BaseComponent):
    """Rule-based complexity judge — keyword + length heuristics."""

    def judge(self, user_input: str) -> ComplexityResult:
        input_lower = user_input.lower()
        input_len = len(user_input.strip())

        # Short inputs with no complex keywords → simple
        matched_keywords = [kw for kw in _COMPLEX_KEYWORDS if kw in input_lower]

        if not matched_keywords and input_len < 50:
            return ComplexityResult(
                complexity="simple",
                confidence=0.95,
                method="rule",
                reason="Short input, no complex keywords",
            )

        if matched_keywords:
            return ComplexityResult(
                complexity="complex",
                confidence=0.7 + min(len(matched_keywords) * 0.1, 0.25),
                method="rule",
                reason=f"Complex keywords found: {matched_keywords}",
            )

        # Long input without complex keywords
        if input_len > 200:
            return ComplexityResult(
                complexity="complex",
                confidence=0.6,
                method="rule",
                reason="Long input suggests complexity",
            )

        return ComplexityResult(
            complexity="simple",
            confidence=0.7,
            method="rule",
            reason="No complex indicators found",
        )


class LLMComplexityJudge(BaseComponent):
    """LLM-based complexity judge — uses lightweight model for classification."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def judge(self, user_input: str) -> ComplexityResult:
        messages = [
            {"role": "system", "content": (
                "Classify the following task as 'simple' or 'complex'. "
                "Respond with JSON: {\"complexity\": \"simple\"|\"complex\", \"confidence\": 0.0-1.0, \"reason\": \"...\"}"
            )},
            {"role": "user", "content": user_input},
        ]
        try:
            result = await self._provider.complete_structured(
                messages,
                schema={"complexity": "string", "confidence": "number", "reason": "string"},
            )
            return ComplexityResult(
                complexity=result.get("complexity", "simple"),
                confidence=float(result.get("confidence", 0.5)),
                method="llm",
                reason=result.get("reason"),
            )
        except Exception:
            # Fallback to rule-based
            return RuleBasedComplexityJudge().judge(user_input)
