"""Tests for agent evaluation system."""

from __future__ import annotations

import pytest

from open_agent.eval.scenario import Scenario, StepAssertion
from open_agent.eval.assertions import check_assertion, AssertionResult
from open_agent.eval.replay import TraceReplayEngine
from open_agent.eval.metrics import compute_metrics, EvalMetrics
from open_agent.eval.judge import LLMJudge, JudgeScore
from open_agent.eval.dataset import EvalDataset, trace_to_eval_case
from open_agent.trace import SpanKind, SpanStatus, Trace


def _make_simple_trace() -> Trace:
    trace = Trace(metadata={"user_input": "search for AI papers"})
    s1 = trace.create_span("routing", kind=SpanKind.ROUTING)
    s1.finish()
    s2 = trace.create_span("tool_call:search", kind=SpanKind.TOOL_CALL)
    s2.set_attribute("tool_name", "search")
    s2.set_attribute("arguments", {"query": "AI papers"})
    s2.finish()
    s3 = trace.create_span("agent_loop", kind=SpanKind.AGENT_LOOP)
    s3.set_attribute("output", "Found 10 AI papers")
    s3.finish()
    return trace


class TestScenario:
    def test_create_scenario(self):
        s = Scenario(
            name="test",
            input="hello",
            expected_tool_calls=["greet"],
            expected_output="Hi there",
        )
        assert s.name == "test"
        d = s.to_dict()
        assert d["name"] == "test"
        assert d["expected_tool_calls"] == ["greet"]

    def test_scenario_with_assertions(self):
        a = StepAssertion(step=0, type="tool_called_with", tool="search", params_contain={"query": "AI"})
        s = Scenario(name="assert_test", input="search AI", step_assertions=[a])
        assert len(s.step_assertions) == 1


class TestAssertions:
    def test_tool_called_with_pass(self):
        assertion = StepAssertion(step=0, type="tool_called_with", tool="search")
        actual = {"tool_calls": [{"tool": "search", "arguments": {}}]}
        result = check_assertion(assertion, actual)
        assert result.passed

    def test_tool_called_with_fail(self):
        assertion = StepAssertion(step=0, type="tool_called_with", tool="search")
        actual = {"tool_calls": [{"tool": "read", "arguments": {}}]}
        result = check_assertion(assertion, actual)
        assert not result.passed

    def test_output_contains_pass(self):
        assertion = StepAssertion(step=0, type="output_contains", expected_value="AI papers")
        actual = {"output": "Found 10 AI papers on machine learning"}
        result = check_assertion(assertion, actual)
        assert result.passed

    def test_output_contains_fail(self):
        assertion = StepAssertion(step=0, type="output_contains", expected_value="quantum")
        actual = {"output": "Found 10 AI papers"}
        result = check_assertion(assertion, actual)
        assert not result.passed

    def test_output_matches(self):
        assertion = StepAssertion(step=0, type="output_matches", expected_value="hello")
        result = check_assertion(assertion, {"output": "hello"})
        assert result.passed
        result2 = check_assertion(assertion, {"output": "hello world"})
        assert not result2.passed

    def test_unknown_type(self):
        assertion = StepAssertion(step=0, type="custom_check")
        result = check_assertion(assertion, {})
        assert not result.passed
        assert "Unknown" in result.message


class TestTraceReplay:
    def test_replay_match(self):
        trace = _make_simple_trace()
        scenario = Scenario(
            name="search_test",
            input="search for AI papers",
            expected_tool_calls=["search"],
        )
        engine = TraceReplayEngine()
        result = engine.replay(trace, scenario)
        assert result.tool_call_accuracy > 0

    def test_replay_mismatch(self):
        trace = _make_simple_trace()
        scenario = Scenario(
            name="mismatch_test",
            input="search for AI papers",
            expected_tool_calls=["search", "summarize"],
        )
        engine = TraceReplayEngine()
        result = engine.replay(trace, scenario)
        assert result.tool_call_accuracy < 1.0

    def test_replay_with_assertions(self):
        trace = _make_simple_trace()
        assertion = StepAssertion(step=0, type="output_contains", expected_value="AI papers")
        scenario = Scenario(
            name="assert_replay",
            input="search AI",
            expected_tool_calls=["search"],
            step_assertions=[assertion],
        )
        engine = TraceReplayEngine()
        result = engine.replay(trace, scenario)
        assert result.assertion_pass_rate > 0


class TestMetrics:
    def test_compute_empty(self):
        metrics = compute_metrics([])
        assert metrics.tool_call_success_rate == 0.0

    def test_compute_from_replay(self):
        trace = _make_simple_trace()
        scenario = Scenario(name="test", input="search", expected_tool_calls=["search"])
        engine = TraceReplayEngine()
        replay_result = engine.replay(trace, scenario)
        metrics = compute_metrics([replay_result])
        assert metrics.tool_call_success_rate > 0
        assert "test" in metrics.per_scenario


class TestLLMJudge:
    def test_rule_based_fallback(self):
        judge = LLMJudge()  # no provider
        result = judge._rule_based_judge("This is a good response about AI papers", "AI papers")
        assert isinstance(result.score, float)
        assert 1 <= result.score <= 5

    def test_empty_output_low_score(self):
        judge = LLMJudge()
        result = judge._rule_based_judge("", "something")
        assert result.score <= 2


class TestEvalDataset:
    def test_save_and_load(self, tmp_path):
        ds = EvalDataset(tmp_path / "datasets")
        scenarios = [Scenario(name="s1", input="hello", domain="general")]
        ds.save_version("1.0", scenarios)

        loaded = ds.load_version("1.0")
        assert loaded is not None
        assert len(loaded.scenarios) == 1

    def test_list_versions(self, tmp_path):
        ds = EvalDataset(tmp_path / "datasets")
        ds.save_version("1.0", [])
        ds.save_version("2.0", [])
        versions = ds.list_versions()
        assert "1.0" in versions
        assert "2.0" in versions

    def test_filter_by_domain(self, tmp_path):
        ds = EvalDataset(tmp_path / "datasets")
        scenarios = [
            Scenario(name="s1", input="code", domain="coding"),
            Scenario(name="s2", input="search", domain="search"),
            Scenario(name="s3", input="more code", domain="coding"),
        ]
        ds.save_version("1.0", scenarios)
        filtered = ds.filter_scenarios("1.0", domain="coding")
        assert len(filtered) == 2

    def test_sample(self, tmp_path):
        ds = EvalDataset(tmp_path / "datasets")
        scenarios = [Scenario(name=f"s{i}", input=f"q{i}") for i in range(10)]
        ds.save_version("1.0", scenarios)
        sample = ds.sample("1.0", 3)
        assert len(sample) == 3

    def test_compare_versions(self, tmp_path):
        ds = EvalDataset(tmp_path / "datasets")
        ds.save_version("1.0", [Scenario(name="s1", input="a")])
        ds.save_version("2.0", [Scenario(name="s1", input="a"), Scenario(name="s2", input="b")])
        comparison = ds.compare_versions("1.0", "2.0")
        assert comparison["diff"] == 1


class TestTraceToEvalCase:
    def test_convert(self):
        trace = _make_simple_trace()
        scenario = trace_to_eval_case(trace)
        assert "search" in scenario.expected_tool_calls
        assert scenario.input == "search for AI papers"
