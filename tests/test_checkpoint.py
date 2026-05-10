"""Tests for the checkpoint & resume module."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from open_agent.checkpoint.manager import Checkpoint, CheckpointManager, ExecutionState
from open_agent.checkpoint.storage import CheckpointStorage, JSONStorage, SQLiteStorage
from open_agent.config import CheckpointConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(step: int = 1) -> dict:
    return {"query": f"step-{step}", "metadata": {"iteration": step}}


def _make_tool_calls(n: int) -> list[dict]:
    return [{"tool": f"tool_{i}", "args": {"x": i}, "result": i * 2} for i in range(n)]


def _make_memory(keys: list[str]) -> dict:
    return {k: f"value_{k}" for k in keys}


# ---------------------------------------------------------------------------
# Storage backends
# ---------------------------------------------------------------------------

class TestJSONStorage:
    def test_save_and_load(self, tmp_path: Path):
        storage = JSONStorage(tmp_path / "cps")
        data = {"step_number": 3, "idempotency_key": "abc"}
        storage.save("abc", data)
        loaded = storage.load("abc")
        assert loaded == data

    def test_load_missing_returns_none(self, tmp_path: Path):
        storage = JSONStorage(tmp_path / "cps")
        assert storage.load("nope") is None

    def test_list_checkpoints(self, tmp_path: Path):
        storage = JSONStorage(tmp_path / "cps")
        storage.save("c1", {"step": 1})
        storage.save("c2", {"step": 2})
        ids = storage.list_checkpoints()
        assert set(ids) == {"c1", "c2"}

    def test_delete(self, tmp_path: Path):
        storage = JSONStorage(tmp_path / "cps")
        storage.save("to-delete", {"step": 1})
        assert storage.delete("to-delete") is True
        assert storage.load("to-delete") is None
        assert storage.delete("to-delete") is False

    def test_creates_directory(self, tmp_path: Path):
        deep = tmp_path / "a" / "b" / "c"
        storage = JSONStorage(deep)
        storage.save("x", {"ok": True})
        assert deep.is_dir()

    def test_overwrite(self, tmp_path: Path):
        storage = JSONStorage(tmp_path / "cps")
        storage.save("key", {"v": 1})
        storage.save("key", {"v": 2})
        assert storage.load("key") == {"v": 2}


class TestSQLiteStorage:
    def test_save_and_load(self, tmp_path: Path):
        storage = SQLiteStorage(tmp_path / "cps.db")
        data = {"step_number": 5, "payload": "hello"}
        storage.save("s1", data)
        loaded = storage.load("s1")
        assert loaded == data
        storage.close()

    def test_load_missing_returns_none(self, tmp_path: Path):
        storage = SQLiteStorage(tmp_path / "cps.db")
        assert storage.load("missing") is None
        storage.close()

    def test_list_and_delete(self, tmp_path: Path):
        storage = SQLiteStorage(tmp_path / "cps.db")
        storage.save("a", {"s": 1})
        storage.save("b", {"s": 2})
        assert set(storage.list_checkpoints()) == {"a", "b"}
        assert storage.delete("a") is True
        assert storage.delete("a") is False
        assert storage.load("a") is None
        storage.close()

    def test_creates_directory(self, tmp_path: Path):
        deep = tmp_path / "nested" / "dir"
        storage = SQLiteStorage(deep / "cps.db")
        storage.save("z", {"ok": True})
        storage.close()
        assert (deep / "cps.db").exists()

    def test_overwrite(self, tmp_path: Path):
        storage = SQLiteStorage(tmp_path / "cps.db")
        storage.save("k", {"v": 1})
        storage.save("k", {"v": 2})
        assert storage.load("k") == {"v": 2}
        storage.close()


# ---------------------------------------------------------------------------
# CheckpointManager — save / restore
# ---------------------------------------------------------------------------

class TestCheckpointManagerSaveRestore:
    def test_save_returns_checkpoint(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        cp = mgr.save_checkpoint(
            step_number=1,
            context=_make_context(),
            tool_calls=_make_tool_calls(2),
            memory_state=_make_memory(["k1"]),
        )
        assert isinstance(cp, Checkpoint)
        assert cp.step_number == 1
        assert len(cp.tool_calls_so_far) == 2

    def test_restore_roundtrip(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        cp = mgr.save_checkpoint(
            step_number=3,
            context=_make_context(3),
            tool_calls=_make_tool_calls(3),
            memory_state=_make_memory(["a", "b"]),
            idempotency_key="my-key",
        )
        restored = mgr.restore_checkpoint("my-key")
        assert restored is not None
        assert restored.step_number == 3
        assert restored.context_snapshot["query"] == "step-3"
        assert len(restored.tool_calls_so_far) == 3
        assert "a" in restored.memory_state

    def test_restore_missing_returns_none(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        assert mgr.restore_checkpoint("nope") is None


# ---------------------------------------------------------------------------
# Idempotency key handling
# ---------------------------------------------------------------------------

class TestIdempotencyKey:
    def test_duplicate_key_raises(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        mgr.save_checkpoint(1, {}, [], {}, idempotency_key="dup")
        with pytest.raises(ValueError, match="Duplicate idempotency key"):
            mgr.save_checkpoint(2, {}, [], {}, idempotency_key="dup")

    def test_unique_keys_ok(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        mgr.save_checkpoint(1, {}, [], {}, idempotency_key="k1")
        mgr.save_checkpoint(2, {}, [], {}, idempotency_key="k2")
        assert len(mgr.list_checkpoints()) == 2


# ---------------------------------------------------------------------------
# Checkpoint granularity (interval)
# ---------------------------------------------------------------------------

class TestCheckpointInterval:
    def test_every_step(self, tmp_path: Path):
        cfg = CheckpointConfig(interval=1, storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        assert mgr.should_checkpoint(1) is True
        assert mgr.should_checkpoint(2) is True
        assert mgr.should_checkpoint(100) is True

    def test_every_n_steps(self, tmp_path: Path):
        cfg = CheckpointConfig(interval=3, storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        assert mgr.should_checkpoint(1) is False
        assert mgr.should_checkpoint(2) is False
        assert mgr.should_checkpoint(3) is True
        assert mgr.should_checkpoint(6) is True
        assert mgr.should_checkpoint(7) is False

    def test_step_zero_never_checkpoints(self, tmp_path: Path):
        cfg = CheckpointConfig(interval=1, storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        assert mgr.should_checkpoint(0) is False

    def test_disabled_never_checkpoints(self, tmp_path: Path):
        cfg = CheckpointConfig(enabled=False, storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        assert mgr.should_checkpoint(1) is False
        assert mgr.should_checkpoint(100) is False


# ---------------------------------------------------------------------------
# resume_from_checkpoint
# ---------------------------------------------------------------------------

class TestResumeFromCheckpoint:
    def test_resume_returns_execution_state(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        mgr.save_checkpoint(
            step_number=4,
            context=_make_context(4),
            tool_calls=_make_tool_calls(4),
            memory_state=_make_memory(["x"]),
            idempotency_key="resume-key",
        )
        state = mgr.resume_from_checkpoint("resume-key")
        assert isinstance(state, ExecutionState)
        assert state.next_step == 5
        assert state.restored_context["query"] == "step-4"
        assert len(state.tool_calls_completed) == 4
        assert "x" in state.restored_memory
        assert state.checkpoint is not None
        assert state.checkpoint.step_number == 4

    def test_resume_missing_returns_none(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        assert mgr.resume_from_checkpoint("ghost") is None

    def test_resume_restores_independent_copies(self, tmp_path: Path):
        """Mutating the returned ExecutionState must not affect storage."""
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        mgr.save_checkpoint(
            step_number=1,
            context={"k": "v"},
            tool_calls=[],
            memory_state={},
            idempotency_key="copy-key",
        )
        state1 = mgr.resume_from_checkpoint("copy-key")
        assert state1 is not None
        state1.restored_context["k"] = "modified"
        state2 = mgr.resume_from_checkpoint("copy-key")
        assert state2 is not None
        assert state2.restored_context["k"] == "v"


# ---------------------------------------------------------------------------
# Storage backend creation from config
# ---------------------------------------------------------------------------

class TestStorageBackendCreation:
    def test_default_creates_json(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_backend="json", storage_path=str(tmp_path / "json"))
        mgr = CheckpointManager(config=cfg)
        assert isinstance(mgr._storage, JSONStorage)

    def test_sqlite_backend(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_backend="sqlite", storage_path=str(tmp_path / "cp.db"))
        mgr = CheckpointManager(config=cfg)
        assert isinstance(mgr._storage, SQLiteStorage)

    def test_custom_storage_injected(self, tmp_path: Path):
        storage = JSONStorage(tmp_path / "custom")
        mgr = CheckpointManager(storage=storage)
        assert mgr._storage is storage


# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------

class TestLifecycleHooks:
    @pytest.mark.asyncio
    async def test_on_register(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        assert not mgr._registered
        await mgr.on_register()
        assert mgr._registered

    @pytest.mark.asyncio
    async def test_on_start_stop(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        await mgr.on_start()
        assert mgr._started
        await mgr.on_stop()
        assert not mgr._started

    @pytest.mark.asyncio
    async def test_on_error_does_not_raise(self, tmp_path: Path):
        cfg = CheckpointConfig(storage_path=str(tmp_path / "cps"))
        mgr = CheckpointManager(config=cfg)
        await mgr.on_error(RuntimeError("boom"))  # should not raise


# ---------------------------------------------------------------------------
# Checkpoint dataclass
# ---------------------------------------------------------------------------

class TestCheckpointDataclass:
    def test_to_dict_roundtrip(self):
        cp = Checkpoint(
            step_number=7,
            context_snapshot={"q": "test"},
            tool_calls_so_far=[{"tool": "t1"}],
            memory_state={"k": "v"},
            idempotency_key="abc",
        )
        d = cp.to_dict()
        cp2 = Checkpoint.from_dict(d)
        assert cp2.step_number == 7
        assert cp2.context_snapshot == {"q": "test"}
        assert cp2.tool_calls_so_far == [{"tool": "t1"}]
        assert cp2.memory_state == {"k": "v"}
        assert cp2.idempotency_key == "abc"

    def test_default_key_generated(self):
        cp1 = Checkpoint(step_number=1)
        cp2 = Checkpoint(step_number=2)
        assert cp1.idempotency_key != cp2.idempotency_key

    def test_from_dict_missing_fields_use_defaults(self):
        cp = Checkpoint.from_dict({"step_number": 1})
        assert cp.context_snapshot == {}
        assert cp.tool_calls_so_far == []
        assert cp.memory_state == {}
