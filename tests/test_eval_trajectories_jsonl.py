"""Tests for eval trajectories JSONL storage (Issue 04)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_agent.eval.runner import EvalRunner, _enforce_retention
from open_agent.eval.trend import load_eval_results


class TestTrajectoryJSONL:
    def test_save_trajectories_appends_to_jsonl(self, tmp_path: Path, monkeypatch):
        """_save_trajectories should append to {suite}_trajectories.jsonl."""
        monkeypatch.chdir(tmp_path)
        runner = EvalRunner()
        output_dir = tmp_path / ".open_agent" / "eval_results"
        output_dir.mkdir(parents=True)

        results = [
            {
                "name": "test1",
                "trace_id": "abc123",
                "trace_json": {"trace_id": "abc123", "spans": []},
            },
            {
                "name": "test2",
                "trace_id": "def456",
                "trace_json": {"trace_id": "def456", "spans": []},
            },
        ]
        runner._save_trajectories(output_dir, results, suite_name="smoke")

        jsonl = output_dir / "smoke_trajectories.jsonl"
        assert jsonl.exists()
        lines = jsonl.read_text().strip().splitlines()
        assert len(lines) == 2
        d1 = json.loads(lines[0])
        assert d1["name"] == "test1"
        assert d1["trace_id"] == "abc123"

    def test_trajectory_retention(self, tmp_path: Path, monkeypatch):
        """Writing > retention limit should truncate."""
        monkeypatch.chdir(tmp_path)
        jsonl = tmp_path / "smoke_trajectories.jsonl"
        for i in range(250):
            line = json.dumps({"name": f"t{i}", "trace_id": f"id{i}"})
            jsonl.write_text(
                jsonl.read_text() + line + "\n" if jsonl.exists() else line + "\n"
            )
        _enforce_retention(jsonl, 200)
        lines = jsonl.read_text().strip().splitlines()
        assert len(lines) == 200


class TestExtractTrajectory:
    def test_extract_by_trace_id(self, tmp_path: Path):
        """extract_trajectory_from_jsonl should find by trace_id."""
        from open_agent.eval.runner import extract_trajectory_from_jsonl

        jsonl = tmp_path / "smoke_trajectories.jsonl"
        entries = [
            {"name": "t1", "trace_id": "aaa", "trace": {"spans": [{"op": "a"}]}},
            {"name": "t2", "trace_id": "bbb", "trace": {"spans": [{"op": "b"}]}},
        ]
        for e in entries:
            jsonl.write_text(
                jsonl.read_text() + json.dumps(e) + "\n" if jsonl.exists() else json.dumps(e) + "\n"
            )

        result = extract_trajectory_from_jsonl(jsonl, "bbb")
        assert result is not None
        assert result["trace_id"] == "bbb"
        assert result["trace"]["spans"][0]["op"] == "b"

    def test_extract_not_found(self, tmp_path: Path):
        """extract_trajectory_from_jsonl returns None for missing trace_id."""
        from open_agent.eval.runner import extract_trajectory_from_jsonl

        jsonl = tmp_path / "smoke_trajectories.jsonl"
        jsonl.write_text('{"trace_id": "aaa"}\n')
        result = extract_trajectory_from_jsonl(jsonl, "zzz")
        assert result is None
