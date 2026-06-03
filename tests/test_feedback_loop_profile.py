"""Test feedback loop: avoidance hints from ProfileMemory injected into system prompt."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from open_agent.agent.react import ReActLoop, AgentState, Action, Observation
from open_agent.config import MemoryConfig
from open_agent.memory.profile import ProfileMemory
from open_agent.registry import ToolRegistry


@pytest.fixture
def profile_memory(tmp_path):
    """Create a ProfileMemory with a temp DB."""
    cfg = MemoryConfig(profile_db_path=str(tmp_path / "profile.sqlite"))
    pm = ProfileMemory(config=cfg)
    yield pm
    pm.close()


def _make_react_loop(profile_memory: ProfileMemory | None = None) -> ReActLoop:
    """Build a minimal ReActLoop with optional profile_memory."""
    loop = ReActLoop(
        tool_registry=ToolRegistry(),
        provider=None,
        prompt_builder=None,
    )
    loop._profile_memory = profile_memory
    return loop


# ---------------------------------------------------------------------------
# Test 1: avoidance hints appear in constructed messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_avoidance_hints_in_system_prompt(profile_memory):
    """ProfileMemory hints should appear in the system prompt built by _build_messages."""
    await profile_memory.add_avoidance_hint(
        "web_search: tool unreliable for code queries — use read_file instead"
    )
    await profile_memory.add_avoidance_hint(
        "execute: timeout error on large inputs — break into smaller chunks"
    )

    loop = _make_react_loop(profile_memory=profile_memory)
    state = AgentState()
    messages = await loop._build_messages("test input", state)

    system_msg = messages[0]
    assert system_msg["role"] == "system"
    content = system_msg["content"]

    # Both hints should appear
    assert "web_search" in content
    assert "read_file" in content
    assert "timeout error" in content
    assert "smaller chunks" in content


# ---------------------------------------------------------------------------
# Test 2: no profile_memory → no hints injection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_profile_memory_no_hints():
    """Without profile_memory, the system prompt should have no user profile section."""
    loop = _make_react_loop(profile_memory=None)
    state = AgentState()
    messages = await loop._build_messages("test input", state)

    system_msg = messages[0]
    assert system_msg["role"] == "system"
    # Should not contain profile injection markers
    assert "User profile" not in system_msg["content"]


# ---------------------------------------------------------------------------
# Test 3: empty avoidance hints → no injection noise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_hints_no_injection(profile_memory):
    """ProfileMemory with no hints should not inject empty sections."""
    loop = _make_react_loop(profile_memory=profile_memory)
    state = AgentState()
    messages = await loop._build_messages("test input", state)

    system_msg = messages[0]
    # Fresh profile has no preferences, constraints, or hints → no injection
    assert "User profile" not in system_msg["content"]


# ---------------------------------------------------------------------------
# Test 4: hints persist across sessions (SQLite round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hints_persist_across_sessions(tmp_path):
    """Avoidance hints written in one session should be read in a new session."""
    db_path = str(tmp_path / "profile.sqlite")
    cfg = MemoryConfig(profile_db_path=db_path)

    # Session 1: write hints
    pm1 = ProfileMemory(config=cfg)
    await pm1.add_avoidance_hint("tool_x: error pattern Y — use tool_z instead")
    pm1.close()

    # Session 2: new ProfileMemory instance, same DB
    pm2 = ProfileMemory(config=cfg)
    loop = _make_react_loop(profile_memory=pm2)
    state = AgentState()
    messages = await loop._build_messages("test", state)

    system_msg = messages[0]["content"]
    assert "tool_x" in system_msg
    assert "tool_z" in system_msg
    pm2.close()
