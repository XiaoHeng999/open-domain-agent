"""Tests for CLI --verbose/--debug global flags."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from open_agent.cli import app

runner = CliRunner()


def _make_response():
    return SimpleNamespace(
        output="test answer",
        trace_id="abc123",
        routing=None,
        quality_score=None,
        anomalies=[],
        duration_ms=123.45,
        metadata={"total_steps": 1, "steps": []},
    )


def _mock_runtime():
    """Return a mock AgentRuntime with async lifecycle methods."""
    rt = AsyncMock()
    rt.on_start.return_value = None
    rt.on_stop.return_value = None
    rt.run.return_value = _make_response()
    return rt


class TestVerboseFlag:
    def test_run_no_verbose_hides_trace(self):
        """Without --verbose, trace info should not appear."""
        with patch("open_agent.config_loader.load_config") as mock_cfg, \
             patch("open_agent.runtime.AgentRuntime", side_effect=lambda **kw: _mock_runtime()):
            from open_agent.config import AgentConfig
            mock_cfg.return_value = AgentConfig()

            result = runner.invoke(app, ["run", "hello"])
            # Trace line should NOT appear without --verbose
            assert "Trace:" not in result.output

    def test_run_with_verbose_shows_trace(self):
        """With --verbose, trace info should appear."""
        with patch("open_agent.config_loader.load_config") as mock_cfg, \
             patch("open_agent.runtime.AgentRuntime", side_effect=lambda **kw: _mock_runtime()):
            from open_agent.config import AgentConfig
            mock_cfg.return_value = AgentConfig()

            result = runner.invoke(app, ["--verbose", "run", "hello"])
            assert "Trace:" in result.output

    def test_debug_implies_verbose(self):
        """--debug should imply --verbose."""
        with patch("open_agent.config_loader.load_config") as mock_cfg, \
             patch("open_agent.runtime.AgentRuntime", side_effect=lambda **kw: _mock_runtime()):
            from open_agent.config import AgentConfig
            mock_cfg.return_value = AgentConfig()

            result = runner.invoke(app, ["--debug", "run", "hello"])
            assert "Trace:" in result.output


class TestDebugLogging:
    def test_debug_sets_logging_level(self):
        """--debug should set logging level to DEBUG."""
        with patch("open_agent.config_loader.load_config") as mock_cfg, \
             patch("open_agent.runtime.AgentRuntime", side_effect=lambda **kw: _mock_runtime()), \
             patch("open_agent.cli.setup_structured_logging") as mock_log:
            from open_agent.config import AgentConfig
            mock_cfg.return_value = AgentConfig()

            runner.invoke(app, ["--debug", "run", "hello"])
            mock_log.assert_called_with(level=logging.DEBUG)
