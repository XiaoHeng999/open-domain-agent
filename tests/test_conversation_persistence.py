"""Test conversation persistence with SQLite in RuntimeMemory."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from open_agent.config import MemoryConfig
from open_agent.memory.runtime import RuntimeMemory


@pytest.fixture
def persist_config(tmp_path):
    """MemoryConfig with persistence enabled and temp DB path."""
    return MemoryConfig(
        persistence_enabled=True,
        persistence_db_path=str(tmp_path / "persistence.sqlite"),
        persistence_retention_days=7,
    )


@pytest.fixture
def disabled_config(tmp_path):
    """MemoryConfig with persistence disabled."""
    return MemoryConfig(
        persistence_enabled=False,
        persistence_db_path=str(tmp_path / "persistence.sqlite"),
    )


# ---------------------------------------------------------------------------
# Test 1: message round-trip — add, restart, load from SQLite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_round_trip(persist_config):
    """Messages added in one session should be loaded in a new session."""
    # Session 1: add messages
    rm1 = RuntimeMemory(config=persist_config)
    await rm1.add_message("user", "Hello, agent!")
    await rm1.add_message("assistant", "Hi! How can I help?")
    await rm1.add_message("user", "Write a test")
    rm1.close()

    # Session 2: new RuntimeMemory, same DB — should load last N messages
    rm2 = RuntimeMemory(config=persist_config)
    context = await rm2.get_context()
    roles = [m["role"] for m in context]
    contents = [m["content"] for m in context]

    assert "user" in roles
    assert "assistant" in roles
    assert "Hello, agent!" in contents
    assert "Hi! How can I help?" in contents
    assert "Write a test" in contents
    rm2.close()


# ---------------------------------------------------------------------------
# Test 2: 7-day cleanup deletes old records, keeps recent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retention_cleanup(persist_config):
    """Records older than retention_days should be cleaned on startup."""
    # Session 1: add a message
    rm1 = RuntimeMemory(config=persist_config)
    await rm1.add_message("user", "old message")
    rm1.close()

    # Manually backdate the record by 10 days
    import sqlite3
    db_path = persist_config.persistence_db_path
    conn = sqlite3.connect(db_path)
    old_ts = time.time() - (10 * 86400)
    conn.execute("UPDATE messages SET timestamp = ?", (old_ts,))
    conn.commit()
    conn.close()

    # Session 2: startup cleanup should remove the old record
    rm2 = RuntimeMemory(config=persist_config)
    context = await rm2.get_context()
    contents = [m["content"] for m in context]
    assert "old message" not in contents
    rm2.close()


@pytest.mark.asyncio
async def test_retention_keeps_recent(persist_config):
    """Recent records should survive the cleanup."""
    # Add a fresh message
    rm1 = RuntimeMemory(config=persist_config)
    await rm1.add_message("user", "fresh message")
    rm1.close()

    # New session — recent message should still be there
    rm2 = RuntimeMemory(config=persist_config)
    context = await rm2.get_context()
    contents = [m["content"] for m in context]
    assert "fresh message" in contents
    rm2.close()


# ---------------------------------------------------------------------------
# Test 3: persistence disabled — no SQLite operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persistence_disabled_no_sqlite(disabled_config, tmp_path):
    """When persistence is disabled, no SQLite DB should be created."""
    rm = RuntimeMemory(config=disabled_config)
    await rm.add_message("user", "test")
    rm.close()

    db_path = disabled_config.persistence_db_path
    assert not Path(db_path).exists()


# ---------------------------------------------------------------------------
# Test 4: persistence disabled — messages only in memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persistence_disabled_memory_only(disabled_config):
    """Without persistence, messages are only in memory."""
    rm = RuntimeMemory(config=disabled_config)
    await rm.add_message("user", "ephemeral")
    context = await rm.get_context()
    assert "ephemeral" in [m["content"] for m in context]
    rm.close()
