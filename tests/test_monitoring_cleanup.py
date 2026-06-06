"""Tests for monitoring boundary cleanup — FeedbackLoop wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

from open_agent.monitoring.collector import QualityScorer, FeedbackLoop
from open_agent.trace import Trace


class TestQualityScorer:
    def test_docstring_describes_purpose(self):
        assert "quality" in QualityScorer.__doc__.lower()

    def test_score_still_works(self):
        scorer = QualityScorer()
        trace = Trace()
        score = scorer.score(trace)
        assert score.score >= 0


class TestFeedbackLoopSuggestEval:
    def test_suggest_returns_none_below_80(self):
        loop = FeedbackLoop()
        trace = Trace()
        mock_score = MagicMock()
        mock_score.score = 50
        result = loop.suggest_eval_case(trace, mock_score)
        assert result is None

    def test_suggest_returns_dict_at_80_plus(self):
        loop = FeedbackLoop()
        trace = Trace()
        mock_score = MagicMock()
        mock_score.score = 85
        result = loop.suggest_eval_case(trace, mock_score)
        assert result is not None
        assert result["trace_id"] == trace.trace_id
        assert result["quality_score"] == 85
