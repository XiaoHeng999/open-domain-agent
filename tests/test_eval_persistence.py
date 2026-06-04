"""Tests for eval result persistence."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml


@pytest.fixture
def tmp_scenarios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create temporary evals dir and cd into tmp_path."""
    smoke = tmp_path / "smoke"
    smoke.mkdir()
    (smoke / "test.yaml").write_text(yaml.dump({
        "name": "test",
        "input": "hello",
    }))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _load_jsonl(path: Path) -> list[dict]:
    """Read all lines from a JSONL file."""
    return [json.loads(line) for line in path.read_text().strip().splitlines()]


@pytest.mark.asyncio
async def test_save_results_creates_jsonl(tmp_scenarios: Path) -> None:
    """run_suite should append to .open_agent/eval_results/{suite}.jsonl."""
    from open_agent.eval.runner import EvalRunner

    mock_runtime = MagicMock()
    mock_runtime.run = AsyncMock(return_value=MagicMock(
        output="hi", metadata={}, trace_id="t1",
    ))
    mock_runtime.on_start = AsyncMock()
    mock_runtime.on_stop = AsyncMock()
    mock_runtime.config = MagicMock()
    mock_runtime.config.model = MagicMock()
    mock_runtime.config.model.provider = "openai"
    mock_runtime.config.model.name = "gpt-4o"

    runner = EvalRunner(scenarios_dir=tmp_scenarios, runtime=mock_runtime)
    await runner.run_suite("smoke")

    output_dir = tmp_scenarios / ".open_agent" / "eval_results"
    assert output_dir.exists()
    jsonl = output_dir / "smoke.jsonl"
    assert jsonl.exists()

    entries = _load_jsonl(jsonl)
    assert len(entries) == 1
    data = entries[0]
    assert data["suite"] == "smoke"
    assert "timestamp" in data
    assert "model" in data
    assert "results" in data
    assert "summary" in data


@pytest.mark.asyncio
async def test_save_results_json_structure(tmp_scenarios: Path) -> None:
    """Persisted JSON should have correct structure with all required fields."""
    from open_agent.eval.runner import EvalRunner
    from open_agent.runtime import AgentResponse

    mock_response = AgentResponse(
        output="The answer is 2",
        trace_id="t1",
        metadata={"steps": []},
    )
    mock_runtime = MagicMock()
    mock_runtime.run = AsyncMock(return_value=mock_response)
    mock_runtime.config = MagicMock()
    mock_runtime.config.model = MagicMock()
    mock_runtime.config.model.provider = "openai"
    mock_runtime.config.model.name = "gpt-4o"

    runner = EvalRunner(scenarios_dir=tmp_scenarios, runtime=mock_runtime)
    await runner.run_suite("smoke")

    output_dir = tmp_scenarios / ".open_agent" / "eval_results"
    entries = _load_jsonl(output_dir / "smoke.jsonl")
    data = entries[0]

    assert data["suite"] == "smoke"
    assert data["model"]["provider"] == "openai"
    assert data["model"]["name"] == "gpt-4o"
    assert data["summary"]["total"] == 1
    assert data["summary"]["passed"] == 1
    assert data["summary"]["failed"] == 0
    assert len(data["results"]) == 1
    assert data["results"][0]["status"] == "pass"


@pytest.mark.asyncio
async def test_multiple_runs_append_to_jsonl(tmp_scenarios: Path) -> None:
    """Multiple run_suite calls should append lines to the same JSONL."""
    import time

    from open_agent.eval.runner import EvalRunner

    mock_runtime = MagicMock()
    mock_runtime.run = AsyncMock(return_value=MagicMock(
        output="hi", metadata={}, trace_id="t1",
    ))
    mock_runtime.config = MagicMock()
    mock_runtime.config.model = MagicMock()
    mock_runtime.config.model.provider = "openai"
    mock_runtime.config.model.name = "gpt-4o"

    runner = EvalRunner(scenarios_dir=tmp_scenarios, runtime=mock_runtime)
    await runner.run_suite("smoke")
    time.sleep(1.1)
    await runner.run_suite("smoke")

    output_dir = tmp_scenarios / ".open_agent" / "eval_results"
    entries = _load_jsonl(output_dir / "smoke.jsonl")
    assert len(entries) == 2
    # Different timestamps
    assert entries[0]["timestamp"] != entries[1]["timestamp"]


@pytest.mark.asyncio
async def test_save_results_creates_directory(tmp_scenarios: Path) -> None:
    """_save_results should auto-create the output directory if missing."""
    from open_agent.eval.runner import EvalRunner

    runner = EvalRunner(scenarios_dir=tmp_scenarios)
    runner._save_results("test", [
        {"name": "s1", "status": "pass", "checks": [], "output": "ok"},
    ])

    output_dir = tmp_scenarios / ".open_agent" / "eval_results"
    assert output_dir.exists()
    jsonl = output_dir / "test.jsonl"
    assert jsonl.exists()
    entries = _load_jsonl(jsonl)
    assert len(entries) == 1
