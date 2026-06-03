"""Tests for prompt caching — cache_control markers on Anthropic requests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test 1: AgentConfig has caching field
# ---------------------------------------------------------------------------


def test_agent_config_has_caching_field() -> None:
    """AgentConfig.model should have a caching field defaulting to True."""
    from open_agent.config import AgentConfig

    cfg = AgentConfig()
    assert cfg.model.caching is True


def test_agent_config_caching_can_be_disabled() -> None:
    """AgentConfig.model.caching can be set to False."""
    from open_agent.config import AgentConfig

    cfg = AgentConfig(model={"caching": False})
    assert cfg.model.caching is False


# ---------------------------------------------------------------------------
# Test 2: Anthropic requests include cache_control when enabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_includes_cache_control_when_enabled() -> None:
    """Anthropic provider adds cache_control markers when caching=True."""
    from open_agent.config import ModelConfig
    from open_agent.model import AnthropicProvider

    provider = AnthropicProvider(ModelConfig(provider="anthropic", name="claude-3-opus", caching=True))

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="hello")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5

    captured_kwargs: dict = {}

    async def capture_create(**kwargs):
        captured_kwargs.update(kwargs)
        return mock_response

    provider._client = MagicMock()
    provider._client.messages = MagicMock()
    provider._client.messages.create = capture_create

    await provider.complete_with_tools(
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ],
        tool_definitions=[
            {"name": "test_tool", "description": "A test", "input_schema": {"type": "object"}},
        ],
    )

    # System message should have cache_control
    system = captured_kwargs.get("system")
    assert system is not None
    # system can be a string or a list with cache_control
    if isinstance(system, list):
        cache_markers = [b for b in system if isinstance(b, dict) and "cache_control" in b]
        assert len(cache_markers) > 0, "System message should have cache_control marker"
    else:
        # system as string — check tools have cache_control
        pass

    # Tools should have cache_control
    tools = captured_kwargs.get("tools", [])
    assert len(tools) > 0
    last_tool = tools[-1]
    assert "cache_control" in last_tool, "Last tool should have cache_control marker"
    assert last_tool["cache_control"] == {"type": "ephemeral"}


# ---------------------------------------------------------------------------
# Test 3: No cache_control when caching disabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_cache_control_when_disabled() -> None:
    """No cache_control markers when caching=False."""
    from open_agent.config import ModelConfig
    from open_agent.model import AnthropicProvider

    provider = AnthropicProvider(ModelConfig(provider="anthropic", name="claude-3-opus", caching=False))

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="hello")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5

    captured_kwargs: dict = {}

    async def capture_create(**kwargs):
        captured_kwargs.update(kwargs)
        return mock_response

    provider._client = MagicMock()
    provider._client.messages = MagicMock()
    provider._client.messages.create = capture_create

    await provider.complete_with_tools(
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ],
        tool_definitions=[
            {"name": "test_tool", "description": "A test", "input_schema": {"type": "object"}},
        ],
    )

    tools = captured_kwargs.get("tools", [])
    for tool in tools:
        assert "cache_control" not in tool, "No cache_control when caching=False"

    system = captured_kwargs.get("system")
    if isinstance(system, list):
        for block in system:
            if isinstance(block, dict):
                assert "cache_control" not in block, "No cache_control in system when caching=False"


# ---------------------------------------------------------------------------
# Test 4: No cache_control for non-Anthropic providers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_cache_control_for_openai() -> None:
    """OpenAI provider never adds cache_control markers."""
    from open_agent.config import ModelConfig
    from open_agent.model import OpenAIProvider

    provider = OpenAIProvider(ModelConfig(provider="openai", name="gpt-4o", caching=True))

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "hello"
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5

    captured_kwargs: dict = {}

    async def capture_create(**kwargs):
        captured_kwargs.update(kwargs)
        return mock_response

    provider._client = MagicMock()
    provider._client.chat = MagicMock()
    provider._client.chat.completions = MagicMock()
    provider._client.chat.completions.create = capture_create

    await provider.complete_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
    )

    tools = captured_kwargs.get("tools", [])
    for tool in tools:
        assert "cache_control" not in tool, "OpenAI tools should not have cache_control"
