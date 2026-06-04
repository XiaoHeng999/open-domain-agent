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
        """Multi-signal progressive scoring with 6 levels."""
        stripped = actual.strip()

        # Level 1: Empty or whitespace
        if not stripped:
            return JudgeScore(score=1.0, reasoning="Empty output", criteria="")

        # Level 2: Very short output (< 20 chars)
        if len(stripped) < 20:
            return JudgeScore(score=2.0, reasoning="Output too short (< 20 chars)", criteria="")

        # Check expected content match
        expected_lower = expected.lower().strip()
        actual_lower = stripped.lower()

        if expected_lower:
            # Split expected into keywords
            expected_words = set(expected_lower.split())
            matched = sum(1 for w in expected_words if w in actual_lower)
            match_ratio = matched / max(len(expected_words), 1)

            # Level 2.5: No expected content found
            if match_ratio == 0:
                return JudgeScore(score=2.5, reasoning="Expected content not found in output", criteria="")

            # Level 3: Partial match
            if match_ratio < 1.0:
                return JudgeScore(
                    score=3.0,
                    reasoning=f"Partial match ({match_ratio:.0%} of expected keywords)",
                    criteria="",
                )

            # Level 4: Full match
            # Level 4.5-5.0: Full match + structural quality
            has_structure = any(marker in stripped for marker in ["\n", "1.", "- ", "* ", "```"])
            if has_structure and len(stripped) > 50:
                return JudgeScore(score=4.5, reasoning="Full match with structured output", criteria="")

            return JudgeScore(score=4.0, reasoning="Expected content fully matched", criteria="")

        # No expected content — score based on output quality alone
        if len(stripped) > 50:
            return JudgeScore(score=3.0, reasoning="Substantial output, no expected content to match", criteria="")

        return JudgeScore(score=2.5, reasoning="Short output with no expected content", criteria="")
