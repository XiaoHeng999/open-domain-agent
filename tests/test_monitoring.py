"""Tests for online monitoring."""

from __future__ import annotations

import pytest

from open_agent.trace import SpanKind, SpanStatus, Trace, TraceManager
from open_agent.monitoring.collector import (
    AnomalyDetector,
    FeedbackLoop,
    QualityScorer,
    TraceCollector,
)


def _make_trace_with_tool_loop() -> Trace:
    trace = Trace()
    for i in range(4):
        span = trace.create_span(f"tool_call:search", kind=SpanKind.TOOL_CALL)
        span.set_attribute("tool_name", "search")
        span.finish()
    return trace


def _make_trace_with_errors() -> Trace:
    trace = Trace()
    s1 = trace.create_span("tool_call", kind=SpanKind.TOOL_CALL)
    s1.finish(status=SpanStatus.ERROR, error="ValueError: bad param")
    s2 = trace.create_span("tool_call", kind=SpanKind.TOOL_CALL)
    s2.finish(status=SpanStatus.ERROR, error="ValueError: bad param")
    return trace


def _make_successful_trace() -> Trace:
    trace = Trace()
    s1 = trace.create_span("routing", kind=SpanKind.ROUTING)
    s1.finish()
    s2 = trace.create_span("tool_call:search", kind=SpanKind.TOOL_CALL)
    s2.set_attribute("tool_name", "search")
    s2.finish()
    s3 = trace.create_span("agent_loop", kind=SpanKind.AGENT_LOOP)
    s3.finish()
    return trace


class TestAnomalyDetector:
    def test_detect_tool_loop(self):
        trace = _make_trace_with_tool_loop()
        detector = AnomalyDetector()
        alerts = detector.detect(trace)
        tool_loop_alerts = [a for a in alerts if a.alert_type == "tool_loop"]
        assert len(tool_loop_alerts) >= 1
        assert "search" in tool_loop_alerts[0].message

    def test_detect_repeated_errors(self):
        trace = _make_trace_with_errors()
        detector = AnomalyDetector()
        alerts = detector.detect(trace)
        error_alerts = [a for a in alerts if a.alert_type == "repeated_error"]
        assert len(error_alerts) >= 1

    def test_no_anomalies(self):
        trace = _make_successful_trace()
        detector = AnomalyDetector()
        alerts = detector.detect(trace)
        assert len(alerts) == 0

    def test_detect_timeout(self):
        trace = Trace()
        span = trace.create_span("slow_op", kind=SpanKind.TOOL_CALL)
        span.start_time = 0
        span.end_time = 120  # 120 seconds
        span.finish()
        detector = AnomalyDetector()
        alerts = detector.detect(trace)
        timeout_alerts = [a for a in alerts if a.alert_type == "timeout"]
        assert len(timeout_alerts) >= 1


class TestQualityScorer:
    def test_successful_execution(self):
        trace = _make_successful_trace()
        scorer = QualityScorer()
        score = scorer.score(trace)
        assert score.score >= 70
        assert score.task_completed == 1.0
        assert score.no_errors == 1.0

    def test_failed_execution(self):
        trace = _make_trace_with_errors()
        scorer = QualityScorer()
        score = scorer.score(trace)
        assert score.task_completed == 0.0
        assert score.no_errors < 1.0

    def test_empty_trace(self):
        trace = Trace()
        scorer = QualityScorer()
        score = scorer.score(trace)
        assert isinstance(score.score, float)
        assert 0 <= score.score <= 100

    def test_score_breakdown(self):
        trace = _make_successful_trace()
        scorer = QualityScorer()
        score = scorer.score(trace)
        assert "task_completed" in score.breakdown
        assert "tool_efficiency" in score.breakdown
        assert "token_efficiency" in score.breakdown
        assert "no_errors" in score.breakdown


class TestTraceCollector:
    def test_collect_trace(self):
        mgr = TraceManager()
        trace = mgr.create_trace()
        collector = TraceCollector(mgr)
        result = collector.collect_trace(trace.trace_id)
        assert result is trace

    def test_query_live_spans(self):
        mgr = TraceManager()
        trace = mgr.create_trace()
        span = trace.create_span("test", kind=SpanKind.TOOL_CALL)
        span.finish()
        collector = TraceCollector(mgr)
        spans = collector.query_live_spans(trace.trace_id, kind=SpanKind.TOOL_CALL)
        assert len(spans) == 1


class TestFeedbackLoop:
    def test_avoidance_hint(self):
        loop = FeedbackLoop()
        hint = loop.generate_avoidance_hint("ValueError", {"tool": "search"})
        assert hint["pattern"] == "ValueError"
        assert "Avoid" in hint["hint"]

    def test_suggest_eval_case_high_quality(self):
        loop = FeedbackLoop()
        trace = _make_successful_trace()
        score = QualityScorer().score(trace)
        suggestion = loop.suggest_eval_case(trace, score)
        if score.score >= 80:
            assert suggestion is not None
            assert suggestion["suggestion_type"] == "eval_case"

    def test_suggest_eval_case_low_quality(self):
        loop = FeedbackLoop()
        trace = _make_trace_with_errors()
        score = QualityScorer().score(trace)
        suggestion = loop.suggest_eval_case(trace, score)
        assert suggestion is None  # low quality, no suggestion
