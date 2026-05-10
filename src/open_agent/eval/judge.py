"""LLM-as-Judge — score open-ended outputs (used only for final output eval)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class JudgeScore:
    """Score from LLM-as-Judge."""

    score: float  # 1-5
    reasoning: str = ""
    criteria: str = ""


class LLMJudge:
    """Use LLM to judge output quality. Only for final output evaluation."""

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider

    async def judge_output(
        self, actual_output: str, expected_description: str, criteria: str = ""
    ) -> JudgeScore:
        """Score an output against an expected description."""
        if not self._provider:
            return self._rule_based_judge(actual_output, expected_description)

        messages = [
            {"role": "system", "content": (
                "You are an evaluation judge. Score the output on a scale of 1-5.\n"
                "Consider: relevance, completeness, accuracy, clarity.\n"
                "Respond with JSON: {\"score\": 1-5, \"reasoning\": \"...\"}"
            )},
            {"role": "user", "content": (
                f"Expected: {expected_description}\n\n"
                f"Actual output:\n{actual_output}\n\n"
                f"Criteria: {criteria or 'General quality'}"
            )},
        ]

        try:
            result = await self._provider.complete_structured(
                messages,
                schema={"score": "integer", "reasoning": "string"},
            )
            return JudgeScore(
                score=float(result.get("score", 3)),
                reasoning=result.get("reasoning", ""),
                criteria=criteria,
            )
        except Exception:
            return self._rule_based_judge(actual_output, expected_description)

    def _rule_based_judge(self, actual: str, expected: str) -> JudgeScore:
        """Fallback rule-based scoring."""
        score = 3  # neutral default
        if actual.strip() and len(actual) > 10:
            score = 4
        if expected.lower() in actual.lower():
            score = 5
        if not actual.strip():
            score = 1
        return JudgeScore(score=float(score), reasoning="Rule-based scoring", criteria="")
