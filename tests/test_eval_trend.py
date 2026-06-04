"""Tests for eval trend analysis — loading results, comparing runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_agent.eval.trend import TrendComparison, compare_trends, load_eval_results


@pytest.fixture
def results_dir(tmp_path: Path) -> Path:
    """Create a temp results dir with sample eval JSON files."""
    d = tmp_path / "eval_results"
    d.mkdir()

    # Older run (2nd most recent by filename timestamp)
    older = {
        "summary": {"total": 4, "passed": 3, "failed": 1},
        "metrics": {"tool_call_success_rate": 0.75},
        "results": [
            {"name": "search_basic", "status": "pass"},
            {"name": "code_gen", "status": "pass"},
            {"name": "multi_step", "status": "pass"},
            {"name": "error_recovery", "status": "fail"},
        ],
    }
    (d / "smoke_20260601_120000.json").write_text(json.dumps(older))

    # Newer run (most recent)
    newer = {
        "summary": {"total": 4, "passed": 2, "failed": 2},
        "metrics": {"tool_call_success_rate": 0.60},
        "results": [
            {"name": "search_basic", "status": "pass"},
            {"name": "code_gen", "status": "fail"},
            {"name": "multi_step", "status": "pass"},
            {"name": "error_recovery", "status": "fail"},
        ],
    }
    (d / "smoke_20260603_150000.json").write_text(json.dumps(newer))

    return d


class TestLoadEvalResults:
    def test_loads_latest_two(self, results_dir: Path):
        loaded = load_eval_results("smoke", results_dir, latest=2)
        assert len(loaded) == 2

    def test_most_recent_first(self, results_dir: Path):
        loaded = load_eval_results("smoke", results_dir, latest=2)
        assert loaded[0]["summary"]["passed"] == 2  # newer
        assert loaded[1]["summary"]["passed"] == 3  # older

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path):
        loaded = load_eval_results("smoke", tmp_path / "nope")
        assert loaded == []

    def test_no_matching_files_returns_empty(self, results_dir: Path):
        loaded = load_eval_results("other_suite", results_dir)
        assert loaded == []

    def test_corrupt_file_skipped(self, results_dir: Path):
        (results_dir / "smoke_20260602_bad.json").write_text("not json{{{")
        loaded = load_eval_results("smoke", results_dir, latest=3)
        assert len(loaded) == 2  # corrupt file skipped


class TestCompareTrends:
    def test_returns_none_with_one_result(self):
        assert compare_trends([{"summary": {}}]) is None

    def test_returns_none_with_empty(self):
        assert compare_trends([]) is None

    def test_pass_rate_delta(self, results_dir: Path):
        loaded = load_eval_results("smoke", results_dir)
        cmp = compare_trends(loaded)
        assert cmp is not None
        # older: 3/4=0.75, newer: 2/4=0.50 => delta=-0.25
        assert cmp.current_pass_rate == pytest.approx(0.50)
        assert cmp.previous_pass_rate == pytest.approx(0.75)
        assert cmp.pass_rate_delta == pytest.approx(-0.25)

    def test_tool_accuracy_delta(self, results_dir: Path):
        loaded = load_eval_results("smoke", results_dir)
        cmp = compare_trends(loaded)
        assert cmp is not None
        assert cmp.current_tool_accuracy == pytest.approx(0.60)
        assert cmp.previous_tool_accuracy == pytest.approx(0.75)
        assert cmp.tool_accuracy_delta == pytest.approx(-0.15)

    def test_regressions_detected(self, results_dir: Path):
        loaded = load_eval_results("smoke", results_dir)
        cmp = compare_trends(loaded)
        assert cmp is not None
        assert "code_gen" in cmp.regressions  # pass→fail

    def test_no_improvements(self, results_dir: Path):
        loaded = load_eval_results("smoke", results_dir)
        cmp = compare_trends(loaded)
        assert cmp is not None
        assert cmp.improvements == []  # error_recovery stayed fail

    def test_improvement_detected(self, tmp_path: Path):
        d = tmp_path / "res"
        d.mkdir()
        old = {"summary": {"total": 2, "passed": 1}, "metrics": {}, "results": [
            {"name": "a", "status": "fail"},
            {"name": "b", "status": "pass"},
        ]}
        new = {"summary": {"total": 2, "passed": 2}, "metrics": {}, "results": [
            {"name": "a", "status": "pass"},
            {"name": "b", "status": "pass"},
        ]}
        (d / "x_001.json").write_text(json.dumps(old))
        (d / "x_002.json").write_text(json.dumps(new))
        loaded = load_eval_results("x", d)
        cmp = compare_trends(loaded)
        assert "a" in cmp.improvements
        assert cmp.regressions == []
