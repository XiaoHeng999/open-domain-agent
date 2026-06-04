"""Tests for eval runner — YAML scenario loading and execution."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Test 1: YAML scenario loads and parses correctly
# ---------------------------------------------------------------------------


def test_yaml_scenario_loads_correctly(tmp_path: Path) -> None:
    """EvalRunner should load and parse YAML scenario files."""
    from open_agent.eval.runner import EvalRunner

    suite_dir = tmp_path / "smoke"
    suite_dir.mkdir()
    scenario = {
        "name": "greeting",
        "input": "Say hello",
        "expected_tools": ["direct_answer"],
        "expected_outcome": "contains greeting",
    }
    (suite_dir / "greeting.yaml").write_text(yaml.dump(scenario))

    runner = EvalRunner(scenarios_dir=tmp_path)
    scenarios = runner.load_suite("smoke")
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "greeting"
    assert scenarios[0]["input"] == "Say hello"


# ---------------------------------------------------------------------------
# Test 2: EvalRunner reports pass for matching scenario
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_runner_reports_pass(tmp_path: Path) -> None:
    """EvalRunner should report pass when tools match expected."""
    from open_agent.eval.runner import EvalRunner

    suite_dir = tmp_path / "smoke"
    suite_dir.mkdir()
    scenario = {
        "name": "simple_search",
        "input": "Search for Python",
        "expected_tools": ["web_search"],
    }
    (suite_dir / "simple_search.yaml").write_text(yaml.dump(scenario))

    runner = EvalRunner(scenarios_dir=tmp_path)

    mock_response = MagicMock()
    mock_response.output = "Python is a programming language"
    mock_response.trace_id = "test-trace-001"
    mock_response.metadata = {
        "steps": [{"action": "web_search({})"}],
    }

    with patch.object(runner, "_execute_scenario", new_callable=AsyncMock, return_value=mock_response):
        results = await runner.run_suite("smoke")
        assert len(results) == 1
        assert results[0]["status"] == "pass"


# ---------------------------------------------------------------------------
# Test 3: EvalRunner reports fail for mismatched scenario
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_runner_reports_fail(tmp_path: Path) -> None:
    """EvalRunner should report fail when tools don't match expected."""
    from open_agent.eval.runner import EvalRunner

    suite_dir = tmp_path / "smoke"
    suite_dir.mkdir()
    scenario = {
        "name": "should_search",
        "input": "Find latest news",
        "expected_tools": ["web_search"],
    }
    (suite_dir / "should_search.yaml").write_text(yaml.dump(scenario))

    runner = EvalRunner(scenarios_dir=tmp_path)

    mock_response = MagicMock()
    mock_response.output = "I don't know"
    mock_response.trace_id = "test-trace-002"
    mock_response.metadata = {
        "steps": [],
    }

    with patch.object(runner, "_execute_scenario", new_callable=AsyncMock, return_value=mock_response):
        results = await runner.run_suite("smoke")
        assert len(results) == 1
        assert results[0]["status"] == "fail"


# ---------------------------------------------------------------------------
# Test 4: Empty suite returns no results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_runner_empty_suite(tmp_path: Path) -> None:
    """EvalRunner returns empty list for non-existent or empty suite."""
    from open_agent.eval.runner import EvalRunner

    runner = EvalRunner(scenarios_dir=tmp_path)
    results = await runner.run_suite("nonexistent")
    assert results == []


# ---------------------------------------------------------------------------
# Test 5: Scenario with expected_outcome checks output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_runner_checks_outcome(tmp_path: Path) -> None:
    """EvalRunner should check expected_outcome against output text."""
    from open_agent.eval.runner import EvalRunner

    suite_dir = tmp_path / "smoke"
    suite_dir.mkdir()
    scenario = {
        "name": "math_test",
        "input": "What is 2+2?",
        "expected_outcome": "4",
    }
    (suite_dir / "math_test.yaml").write_text(yaml.dump(scenario))

    runner = EvalRunner(scenarios_dir=tmp_path)

    mock_response = MagicMock()
    mock_response.output = "The answer is 4"
    mock_response.trace_id = "test-trace-003"
    mock_response.metadata = {"steps": []}

    with patch.object(runner, "_execute_scenario", new_callable=AsyncMock, return_value=mock_response):
        results = await runner.run_suite("smoke")
        assert results[0]["status"] == "pass"


@pytest.mark.asyncio
async def test_eval_runner_outcome_mismatch(tmp_path: Path) -> None:
    """EvalRunner should fail when expected_outcome not in output."""
    from open_agent.eval.runner import EvalRunner

    suite_dir = tmp_path / "smoke"
    suite_dir.mkdir()
    scenario = {
        "name": "math_fail",
        "input": "What is 2+2?",
        "expected_outcome": "42",
    }
    (suite_dir / "math_fail.yaml").write_text(yaml.dump(scenario))

    runner = EvalRunner(scenarios_dir=tmp_path)

    mock_response = MagicMock()
    mock_response.output = "The answer is 4"
    mock_response.trace_id = "test-trace-004"
    mock_response.metadata = {"steps": []}

    with patch.object(runner, "_execute_scenario", new_callable=AsyncMock, return_value=mock_response):
        results = await runner.run_suite("smoke")
        assert results[0]["status"] == "fail"
