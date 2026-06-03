"""Tests for CLI eval wiring to AgentRuntime."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


@pytest.fixture
def tmp_scenarios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary evals directory with smoke scenarios."""
    monkeypatch.chdir(tmp_path)
    smoke = tmp_path / "smoke"
    smoke.mkdir()
    (smoke / "test_scenario.yaml").write_text(yaml.dump({
        "name": "test_scenario",
        "input": "What is 1+1?",
        "expected_outcome": "2",
    }))
    (smoke / "tool_scenario.yaml").write_text(yaml.dump({
        "name": "tool_scenario",
        "input": "Read /etc/hostname",
        "expected_tools": ["read_file"],
    }))
    return tmp_path


def _make_mock_runtime(response) -> MagicMock:
    """Create a mock runtime with proper config for JSON serialization."""
    mock_runtime = MagicMock()
    mock_runtime.run = AsyncMock(return_value=response)
    mock_runtime.on_start = AsyncMock()
    mock_runtime.on_stop = AsyncMock()
    mock_runtime.config = MagicMock()
    mock_runtime.config.model = MagicMock()
    mock_runtime.config.model.provider = "mock"
    mock_runtime.config.model.name = "mock-model"
    return mock_runtime


@pytest.mark.asyncio
async def test_eval_runner_with_mock_runtime(tmp_scenarios: Path) -> None:
    """EvalRunner should execute scenarios through a mock runtime."""
    from open_agent.eval.runner import EvalRunner
    from open_agent.runtime import AgentResponse

    mock_response = AgentResponse(
        output="The answer is 2",
        trace_id="test-trace",
        metadata={
            "steps": [
                {"thought": "Simple math", "action": None, "observation": None},
            ],
        },
    )
    mock_runtime = _make_mock_runtime(mock_response)

    runner = EvalRunner(scenarios_dir=tmp_scenarios, runtime=mock_runtime)
    results = await runner.run_suite("smoke")

    assert len(results) == 2
    test_result = next(r for r in results if r["name"] == "test_scenario")
    assert test_result["status"] == "pass"

    tool_result = next(r for r in results if r["name"] == "tool_scenario")
    assert tool_result["status"] == "fail"


@pytest.mark.asyncio
async def test_eval_runner_with_tool_calls(tmp_scenarios: Path) -> None:
    """EvalRunner should detect tool usage from response steps metadata."""
    from open_agent.eval.runner import EvalRunner
    from open_agent.runtime import AgentResponse

    mock_response = AgentResponse(
        output="Hostname is myhost",
        trace_id="test-trace",
        metadata={
            "steps": [
                {
                    "thought": "Need to read file",
                    "action": "read_file({\"path\": \"/etc/hostname\"})",
                    "observation": "myhost",
                },
            ],
        },
    )
    mock_runtime = _make_mock_runtime(mock_response)

    runner = EvalRunner(scenarios_dir=tmp_scenarios, runtime=mock_runtime)
    results = await runner.run_suite("smoke")

    tool_result = next(r for r in results if r["name"] == "tool_scenario")
    assert tool_result["status"] == "pass"
    tool_checks = [c for c in tool_result["checks"] if c["type"] == "expected_tool"]
    assert len(tool_checks) == 1
    assert tool_checks[0]["tool"] == "read_file"
    assert tool_checks[0]["passed"] is True


@pytest.mark.asyncio
async def test_eval_runner_error_handling(tmp_scenarios: Path) -> None:
    """EvalRunner should handle runtime errors gracefully."""
    from open_agent.eval.runner import EvalRunner

    mock_runtime = MagicMock()
    mock_runtime.run = AsyncMock(side_effect=ConnectionError("API unreachable"))
    mock_runtime.on_start = AsyncMock()
    mock_runtime.on_stop = AsyncMock()
    mock_runtime.config = MagicMock()
    mock_runtime.config.model = MagicMock()
    mock_runtime.config.model.provider = "mock"
    mock_runtime.config.model.name = "mock-model"

    runner = EvalRunner(scenarios_dir=tmp_scenarios, runtime=mock_runtime)
    results = await runner.run_suite("smoke")

    for r in results:
        assert r["status"] == "error"
        assert "API unreachable" in r["error"]


def test_eval_load_suite_returns_all_scenarios(tmp_scenarios: Path) -> None:
    """load_suite should return all valid YAML files."""
    from open_agent.eval.runner import EvalRunner

    runner = EvalRunner(scenarios_dir=tmp_scenarios)
    scenarios = runner.load_suite("smoke")

    assert len(scenarios) == 2
    names = {s["name"] for s in scenarios}
    assert names == {"test_scenario", "tool_scenario"}
