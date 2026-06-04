"""Tests for eval path B — TraceReplayEngine integration in EvalRunner."""

from __future__ import annotations

import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import yaml
import pytest

from open_agent.eval.runner import EvalRunner
from open_agent.eval.scenario import Scenario, StepAssertion
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


class TestYamlToScenario:
    def test_old_format_expected_tools(self, smoke_dir, eval_dir):
        yaml_data = {
            "name": "test_tool",
            "input": "read the file",
            "expected_tools": ["read_file", "shell_exec"],
        }
        (smoke_dir / "test.yaml").write_text(yaml.dump(yaml_data))

        runner = EvalRunner(scenarios_dir=Path(eval_dir))
        raw = runner.load_suite("smoke")
        scenario = runner._yaml_to_scenario(raw[0])

        assert isinstance(scenario, Scenario)
        assert scenario.name == "test_tool"
        assert scenario.input == "read the file"
        assert scenario.expected_tool_calls == ["read_file", "shell_exec"]

    def test_old_format_expected_outcome(self, smoke_dir, eval_dir):
        yaml_data = {
            "name": "test_qa",
            "input": "1+1=?",
            "expected_outcome": "2",
        }
        (smoke_dir / "test.yaml").write_text(yaml.dump(yaml_data))

        runner = EvalRunner(scenarios_dir=Path(eval_dir))
        raw = runner.load_suite("smoke")
        scenario = runner._yaml_to_scenario(raw[0])

        assert isinstance(scenario, Scenario)
        assert len(scenario.step_assertions) == 1
        assert scenario.step_assertions[0].type == "output_contains"
        assert scenario.step_assertions[0].expected_value == "2"

    def test_new_format_with_assertions(self, smoke_dir, eval_dir):
        yaml_data = {
            "name": "test_new",
            "input": "search for X",
            "assertions": [
                {"step": 0, "type": "tool_called_with", "tool": "search", "params_contain": {"query": "X"}},
                {"step": 1, "type": "output_contains", "expected_value": "result"},
            ],
        }
        (smoke_dir / "test.yaml").write_text(yaml.dump(yaml_data))

        runner = EvalRunner(scenarios_dir=Path(eval_dir))
        raw = runner.load_suite("smoke")
        scenario = runner._yaml_to_scenario(raw[0])

        assert len(scenario.step_assertions) == 2
        assert scenario.step_assertions[0].type == "tool_called_with"
        assert scenario.step_assertions[1].type == "output_contains"

    def test_both_old_and_new(self, smoke_dir, eval_dir):
        yaml_data = {
            "name": "test_both",
            "input": "do stuff",
            "expected_tools": ["read_file"],
            "assertions": [
                {"step": 0, "type": "output_contains", "expected_value": "done"},
            ],
        }
        (smoke_dir / "test.yaml").write_text(yaml.dump(yaml_data))

        runner = EvalRunner(scenarios_dir=Path(eval_dir))
        raw = runner.load_suite("smoke")
        scenario = runner._yaml_to_scenario(raw[0])

        assert scenario.expected_tool_calls == ["read_file"]
        assert len(scenario.step_assertions) == 1


class TestRunScenarioWithReplay:
    async def test_run_scenario_uses_trace_replay(self, eval_dir):
        tm = TraceManager()
        trace = tm.create_trace(metadata={"user_input": "hello"})
        span = trace.create_span("tool_call", kind=SpanKind.TOOL_CALL)
        span.set_attribute("tool_name", "read_file")
        span.finish()

        mock_response = MagicMock()
        mock_response.output = "file contents"
        mock_response.trace_id = trace.trace_id
        mock_response.metadata = {"steps": [], "total_steps": 1}

        mock_runtime = MagicMock()
        mock_runtime.run = AsyncMock(return_value=mock_response)
        mock_runtime.trace_manager = tm

        runner = EvalRunner(scenarios_dir=Path(eval_dir), runtime=mock_runtime)

        scenario_dict = {
            "name": "test_replay",
            "input": "read file.txt",
            "expected_tools": ["read_file"],
        }
        result = await runner._run_scenario(scenario_dict)

        assert result["status"] == "pass"
        assert "tool_call_accuracy" in result
        assert result["tool_call_accuracy"] == 1.0

    async def test_run_scenario_no_runtime_raises(self, eval_dir):
        runner = EvalRunner(scenarios_dir=Path(eval_dir), runtime=None)
        scenario_dict = {"name": "test", "input": "hello"}

        result = await runner._run_scenario(scenario_dict)
        assert result["status"] == "error"
