"""Tests for cost tracking — usage extraction, CostTracker aggregation, budget alerts."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent.types import ToolCallResponse


# ---------------------------------------------------------------------------
# Test 1: ToolCallResponse has usage field
# ---------------------------------------------------------------------------


def test_tool_call_response_has_usage_field() -> None:
    """ToolCallResponse must accept a usage dict with input/output tokens."""
    resp = ToolCallResponse(
        text="hello",
        usage={"input_tokens": 100, "output_tokens": 50},
    )
    assert resp.usage is not None
    assert resp.usage["input_tokens"] == 100
    assert resp.usage["output_tokens"] == 50


def test_tool_call_response_usage_defaults_none() -> None:
    """ToolCallResponse.usage defaults to None when not provided."""
    resp = ToolCallResponse(text="hello")
    assert resp.usage is None


# ---------------------------------------------------------------------------
# Test 2: OpenAI provider extracts usage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_provider_extracts_usage() -> None:
    """OpenAIProvider.complete_with_tools should extract usage from API response."""
    from open_agent.model import OpenAIProvider
    from open_agent.config import ModelConfig

    provider = OpenAIProvider(ModelConfig(provider="openai", name="gpt-4o"))

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "test"
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 150
    mock_response.usage.completion_tokens = 75

    provider._client = MagicMock()
    provider._client.chat = MagicMock()
    provider._client.chat.completions = MagicMock()
    provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
    )
    assert result.usage is not None
    assert result.usage["input_tokens"] == 150
    assert result.usage["output_tokens"] == 75


# ---------------------------------------------------------------------------
# Test 3: Anthropic provider extracts usage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_provider_extracts_usage() -> None:
    """AnthropicProvider.complete_with_tools should extract usage from API response."""
    from open_agent.model import AnthropicProvider
    from open_agent.config import ModelConfig

    provider = AnthropicProvider(ModelConfig(provider="anthropic", name="claude-3-opus"))

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="hello")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 200
    mock_response.usage.output_tokens = 100

    provider._client = MagicMock()
    provider._client.messages = MagicMock()
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    result = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
    )
    assert result.usage is not None
    assert result.usage["input_tokens"] == 200
    assert result.usage["output_tokens"] == 100


# ---------------------------------------------------------------------------
# Test 4: CostTracker accumulates usage
# ---------------------------------------------------------------------------


def test_cost_tracker_accumulates_usage() -> None:
    """CostTracker should accumulate token usage across multiple requests."""
    from open_agent.cost import CostTracker

    tracker = CostTracker()
    tracker.record("gpt-4o", input_tokens=100, output_tokens=50)
    tracker.record("gpt-4o", input_tokens=200, output_tokens=80)
    tracker.record("claude-3-opus", input_tokens=300, output_tokens=120)

    summary = tracker.get_daily_summary()
    assert "gpt-4o" in summary
    assert summary["gpt-4o"]["input_tokens"] == 300
    assert summary["gpt-4o"]["output_tokens"] == 130
    assert "claude-3-opus" in summary
    assert summary["claude-3-opus"]["input_tokens"] == 300


# ---------------------------------------------------------------------------
# Test 5: CostTracker budget check
# ---------------------------------------------------------------------------


def test_cost_tracker_budget_check() -> None:
    """CostTracker.check_budget should alert when over limit."""
    from open_agent.cost import CostTracker

    tracker = CostTracker(pricing={"gpt-4o": {"input": 5.0, "output": 15.0}})
    tracker.record("gpt-4o", input_tokens=1_000_000, output_tokens=500_000)

    # cost = 1M * 5.0/1M + 500K * 15.0/1M = 5.0 + 7.5 = 12.5 USD
    result = tracker.check_budget(limit=10.0)
    assert result["over_budget"] is True
    assert result["total_cost"] > 10.0

    result = tracker.check_budget(limit=20.0)
    assert result["over_budget"] is False


# ---------------------------------------------------------------------------
# Test 6: CostTracker.get_weekly_summary
# ---------------------------------------------------------------------------


def test_cost_tracker_weekly_summary() -> None:
    """CostTracker.get_weekly_summary should aggregate 7 days."""
    from open_agent.cost import CostTracker

    tracker = CostTracker()
    tracker.record("gpt-4o", input_tokens=100, output_tokens=50)
    tracker.record("gpt-4o", input_tokens=200, output_tokens=80)

    summary = tracker.get_weekly_summary()
    assert "gpt-4o" in summary
    assert summary["gpt-4o"]["input_tokens"] == 300
    assert summary["gpt-4o"]["output_tokens"] == 130


# ---------------------------------------------------------------------------
# Test 7: CostTrackingConfig in AgentConfig
# ---------------------------------------------------------------------------


def test_cost_tracking_config_defaults() -> None:
    """AgentConfig should have cost_tracking sub-config with defaults."""
    from open_agent.config import AgentConfig

    cfg = AgentConfig()
    assert cfg.cost_tracking.enabled is False
    assert cfg.cost_tracking.budget_daily is None


def test_cost_tracking_config_with_budget() -> None:
    """CostTrackingConfig should accept budget_daily."""
    from open_agent.config import AgentConfig

    cfg = AgentConfig(cost_tracking={"enabled": True, "budget_daily": 5.0})
    assert cfg.cost_tracking.enabled is True
    assert cfg.cost_tracking.budget_daily == 5.0
