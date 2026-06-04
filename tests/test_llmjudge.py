"""Tests for LLMJudge multi-signal scoring."""

from __future__ import annotations

import pytest

from open_agent.eval.judge import LLMJudge, JudgeScore


class TestRuleBasedJudge:
    def test_empty_output_scores_1(self):
        judge = LLMJudge(provider=None)
        score = judge._rule_based_judge("", "anything")
        assert score.score == 1.0

    def test_whitespace_only_scores_1(self):
        judge = LLMJudge(provider=None)
        score = judge._rule_based_judge("   \n\t  ", "anything")
        assert score.score == 1.0

    def test_short_output_scores_2(self):
        judge = LLMJudge(provider=None)
        score = judge._rule_based_judge("hi", "expected content")
        assert score.score == 2.0
        assert score.reasoning

    def test_no_expected_match_scores_25(self):
        judge = LLMJudge(provider=None)
        score = judge._rule_based_judge(
            "This is a long enough output but wrong content",
            "completely different expected",
        )
        assert score.score == 2.5
        assert "偏题" in score.reasoning or "not found" in score.reasoning.lower()

    def test_partial_expected_match_scores_3(self):
        judge = LLMJudge(provider=None)
        score = judge._rule_based_judge(
            "The answer involves Python and other things",
            "Python Java",
        )
        assert score.score == 3.0

    def test_full_expected_match_scores_4(self):
        judge = LLMJudge(provider=None)
        score = judge._rule_based_judge(
            "The answer is Python programming language",
            "Python",
        )
        assert score.score == 4.0

    def test_excellent_output_scores_45_plus(self):
        judge = LLMJudge(provider=None)
        output = "The answer is Python. Here's a detailed explanation:\n1. First point\n2. Second point"
        score = judge._rule_based_judge(output, "Python")
        assert score.score >= 4.5

    def test_each_score_has_reasoning(self):
        judge = LLMJudge(provider=None)
        test_cases = [
            ("", "x"),
            ("hi", "x"),
            ("long output but unrelated", "totally different"),
            ("contains some keywords", "keywords unrelated"),
            ("contains the keyword", "keyword"),
            ("contains keyword with structured list:\n- item1\n- item2", "keyword"),
        ]
        for actual, expected in test_cases:
            score = judge._rule_based_judge(actual, expected)
            assert score.reasoning, f"No reasoning for score {score.score}"
