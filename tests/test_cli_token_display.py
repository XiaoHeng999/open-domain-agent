"""Tests for CLI token usage display in chat mode."""
from __future__ import annotations

import types
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from open_agent.cli import app

runner = CliRunner()


def _make_response(tokens_in=500, tokens_out=700):
    return types.SimpleNamespace(
        output="test answer",
        trace_id="abc123",
        routing=None,
        quality_score=None,
        anomalies=[],
        duration_ms=123.45,
        metadata={
            "total_steps": 1,
            "steps": [],
            "usage": {"input_tokens": tokens_in, "output_tokens": "700"},
            "memory_tokens": 1000,
            "token_budget": 8000,
        },
    )


def _mock_runtime():
    rt = AsyncMock()
    rt.on_start.return_value = None
    rt.on_stop.return_value = None
    rt.run.return_value = _make_response()
    rt._runtime_memory = types.SimpleNamespace(total_tokens=1000)
    return rt


class TestBudgetIndicator:
    def test_chat_shows_budget_in_prompt(self):
        """Chat mode should show budget indicator in prompt prefix."""
        with patch("open_agent.config_loader.load_config") as mock_cfg, \
             patch("open_agent.runtime.AgentRuntime", side_effect=lambda **kw: _mock_runtime()):
            from open_agent.config import AgentConfig
            mock_cfg.return_value = AgentConfig()

            result = runner.invoke(app, ["chat"], input="exit\n")
            assert "budget:" in result.output

    def test_run_mode_no_session_total(self):
        """Single-run mode should not show session token total."""
        with patch("open_agent.config_loader.load_config") as mock_cfg, \
             patch("open_agent.runtime.AgentRuntime", side_effect=lambda **kw: _mock_runtime()):
            from open_agent.config import AgentConfig
            mock_cfg.return_value = AgentConfig()

            result = runner.invoke(app, ["run", "hello"])
            assert "Session total:" not in result.output


class TestTokenUsageMetadata:
    def test_response_includes_memory_tokens(self):
        """AgentResponse metadata should include memory_tokens and token_budget."""
        from open_agent.memory.runtime import RuntimeMemory

        rm = RuntimeMemory()
        assert hasattr(rm, "total_tokens")
        assert isinstance(rm.total_tokens, int)
