"""Tests for eval metrics aggregation and trajectory persistence."""

from __future__ import annotations

import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from open_agent.eval.runner import EvalRunner
from open_agent.eval.metrics import compute_metrics, EvalMetrics
from open_agent.eval.replay import ReplayResult
from open_agent.trace import SpanKind, TraceManager


@pytest.fixture
def eval_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def smoke_dir(eval_dir):
    d = Path(eval_dir) / "smoke"
    d.mkdir()
    return d


class TestComputeMetrics:
    def test_empty_results(self):
        metrics = compute_metrics([])
        assert metrics.tool_call_success_rate == 0.0
        assert metrics.task_completion_rate == 0.0

    def test_single_passed_result(self):
        result = ReplayResult(
            scenario_name="test",
            passed=True,
            tool_call_accuracy=1.0,
            assertion_pass_rate=1.0,
        )
        metrics = compute_metrics([result])
        assert metrics.task_completion_rate == 1.0
        assert metrics.tool_call_success_rate == 1.0
        assert "test" in metrics.per_scenario

    def test_mixed_results(self):
        r1 = ReplayResult(scenario_name="pass_test", passed=True, tool_call_accuracy=1.0)
        r2 = ReplayResult(scenario_name="fail_test", passed=False, tool_call_accuracy=0.5)
        metrics = compute_metrics([r1, r2])
        assert metrics.task_completion_rate == 0.5
        assert metrics.tool_call_success_rate == 0.75


class TestTrajectoryPersistence:
    async def test_trajectory_saved(self, smoke_dir, eval_dir, monkeypatch, tmp_path):
        """Trajectory JSON should be saved to {suite}_trajectories.jsonl."""
        monkeypatch.chdir(tmp_path)

        import yaml
        (smoke_dir / "test.yaml").write_text(yaml.dump({
            "name": "test_traj",
            "input": "hello",
            "expected_outcome": "hello",
        }))

        tm = TraceManager()
        trace = tm.create_trace(metadata={"user_input": "hello"})

        mock_response = MagicMock()
        mock_response.output = "hello world"
        mock_response.trace_id = trace.trace_id
        mock_response.metadata = {"steps": [], "total_steps": 1}

        mock_runtime = MagicMock()
        mock_runtime.run = AsyncMock(return_value=mock_response)
        mock_runtime.trace_manager = tm
        mock_runtime.config = MagicMock()
        mock_runtime.config.model = MagicMock()
        mock_runtime.config.model.provider = "mock"
        mock_runtime.config.model.name = "mock"

        runner = EvalRunner(scenarios_dir=Path(eval_dir), runtime=mock_runtime)
        results = await runner.run_suite("smoke")

        # Check trajectory was saved to JSONL
        jsonl_path = tmp_path / ".open_agent" / "eval_results" / "smoke_trajectories.jsonl"
        assert jsonl_path.exists()
        lines = jsonl_path.read_text().strip().splitlines()
        assert len(lines) == 1
        traj_entry = json.loads(lines[0])
        assert traj_entry["name"] == "test_traj"
        assert traj_entry["trace_id"] == trace.trace_id

    async def test_metrics_in_report(self, smoke_dir, eval_dir, monkeypatch, tmp_path):
        """Report JSON should contain metrics field."""
        monkeypatch.chdir(tmp_path)

        import yaml
        (smoke_dir / "test.yaml").write_text(yaml.dump({
            "name": "test_metrics",
            "input": "hello",
            "expected_outcome": "hello",
        }))

        tm = TraceManager()
        trace = tm.create_trace(metadata={"user_input": "hello"})

        mock_response = MagicMock()
        mock_response.output = "hello"
        mock_response.trace_id = trace.trace_id
        mock_response.metadata = {"steps": [], "total_steps": 1}

        mock_runtime = MagicMock()
        mock_runtime.run = AsyncMock(return_value=mock_response)
        mock_runtime.trace_manager = tm
        mock_runtime.config = MagicMock()
        mock_runtime.config.model = MagicMock()
        mock_runtime.config.model.provider = "mock"
        mock_runtime.config.model.name = "mock"

        runner = EvalRunner(scenarios_dir=Path(eval_dir), runtime=mock_runtime)
        await runner.run_suite("smoke")

        # Find the report JSONL
        results_dir = tmp_path / ".open_agent" / "eval_results"
        jsonl = results_dir / "smoke.jsonl"
        assert jsonl.exists()
        lines = jsonl.read_text().strip().splitlines()
        assert len(lines) >= 1
        report = json.loads(lines[0])
        assert "metrics" in report
        assert "tool_call_success_rate" in report["metrics"]
