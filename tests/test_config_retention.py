"""Tests for EvalConfig retention fields and TraceConfig.trace_retention."""

from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from open_agent.config import AgentConfig, EvalConfig, TraceConfig, load_config


class TestEvalConfig:
    def test_eval_config_defaults(self):
        cfg = EvalConfig()
        assert cfg.results_retention == 100
        assert cfg.trajectories_retention == 200

    def test_eval_config_validation_ge1(self):
        with pytest.raises(Exception):
            EvalConfig(results_retention=0)
        with pytest.raises(Exception):
            EvalConfig(trajectories_retention=0)

    def test_agent_config_has_eval_field(self):
        cfg = AgentConfig()
        assert isinstance(cfg.eval, EvalConfig)
        assert cfg.eval.results_retention == 100
        assert cfg.eval.trajectories_retention == 200

    def test_yaml_eval_config(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump({
            "eval": {
                "results_retention": 500,
                "trajectories_retention": 1000,
            }
        }))
        cfg = load_config(str(yaml_file))
        assert cfg.eval.results_retention == 500
        assert cfg.eval.trajectories_retention == 1000

    def test_env_override_eval_retention(self, monkeypatch):
        monkeypatch.setenv("OPEN_AGENT_EVAL_RESULTS_RETENTION", "50")
        monkeypatch.setenv("OPEN_AGENT_EVAL_TRAJECTORIES_RETENTION", "75")
        cfg = load_config()
        assert cfg.eval.results_retention == 50
        assert cfg.eval.trajectories_retention == 75


class TestTraceRetention:
    def test_trace_config_default(self):
        cfg = TraceConfig()
        assert cfg.trace_retention == 100

    def test_trace_config_validation_ge1(self):
        with pytest.raises(Exception):
            TraceConfig(trace_retention=0)

    def test_agent_config_trace_retention(self):
        cfg = AgentConfig()
        assert cfg.trace.trace_retention == 100

    def test_yaml_trace_retention(self, tmp_path: Path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump({
            "trace": {"trace_retention": 250}
        }))
        cfg = load_config(str(yaml_file))
        assert cfg.trace.trace_retention == 250

    def test_env_override_trace_retention(self, monkeypatch):
        monkeypatch.setenv("OPEN_AGENT_TRACE_RETENTION", "42")
        cfg = load_config()
        assert cfg.trace.trace_retention == 42
