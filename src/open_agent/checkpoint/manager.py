"""Checkpoint manager — save, restore, and resume agent execution state."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent
from open_agent.checkpoint.storage import CheckpointStorage, JSONStorage, SQLiteStorage
from open_agent.config import CheckpointConfig


@dataclass
class Checkpoint:
    """Snapshot of execution state at a given step."""

    step_number: int
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    tool_calls_so_far: list[dict[str, Any]] = field(default_factory=list)
    memory_state: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "context_snapshot": self.context_snapshot,
            "tool_calls_so_far": self.tool_calls_so_far,
            "memory_state": self.memory_state,
            "idempotency_key": self.idempotency_key,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        return cls(
            step_number=data["step_number"],
            context_snapshot=data.get("context_snapshot", {}),
            tool_calls_so_far=data.get("tool_calls_so_far", []),
            memory_state=data.get("memory_state", {}),
            idempotency_key=data.get("idempotency_key", uuid.uuid4().hex),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class ExecutionState:
    """Restored execution context returned by *resume_from_checkpoint*."""

    restored_context: dict[str, Any] = field(default_factory=dict)
    restored_memory: dict[str, Any] = field(default_factory=dict)
    tool_calls_completed: list[dict[str, Any]] = field(default_factory=list)
    next_step: int = 0
    checkpoint: Checkpoint | None = None


class CheckpointManager(BaseComponent):
    """Orchestrates checkpoint creation, persistence, and restoration.

    Parameters
    ----------
    config:
        A *CheckpointConfig* controlling interval, backend type, and path.
    storage:
        Optional pre-built storage backend.  When *None* the manager builds
        one from *config*.
    """

    def __init__(
        self,
        config: CheckpointConfig | None = None,
        storage: CheckpointStorage | None = None,
    ) -> None:
        self.config = config or CheckpointConfig()
        self._storage = storage or self._build_storage(self.config)
        # Track idempotency keys we have already persisted in this session.
        self._seen_keys: set[str] = set()
        # Running step counter used for interval decisions.
        self._current_step: int = 0

    # -- BaseComponent lifecycle hooks ----------------------------------------

    async def on_register(self) -> None:
        await super().on_register()

    async def on_start(self) -> None:
        await super().on_start()

    async def on_stop(self) -> None:
        await super().on_stop()

    async def on_error(self, error: Exception) -> None:
        pass

    # -- Public API -----------------------------------------------------------

    def should_checkpoint(self, step_number: int | None = None) -> bool:
        """Return *True* when a checkpoint should be taken at *step_number*."""
        if not self.config.enabled:
            return False
        step = step_number if step_number is not None else self._current_step
        if step == 0:
            return False
        return step % self.config.interval == 0

    def save_checkpoint(
        self,
        step_number: int,
        context: dict[str, Any],
        tool_calls: list[dict[str, Any]],
        memory_state: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Checkpoint:
        """Create and persist a checkpoint.

        Returns the *Checkpoint* object.

        Raises *ValueError* when the *idempotency_key* has already been used.
        """
        key = idempotency_key or uuid.uuid4().hex
        if key in self._seen_keys:
            raise ValueError(f"Duplicate idempotency key: {key}")

        cp = Checkpoint(
            step_number=step_number,
            context_snapshot=dict(context),
            tool_calls_so_far=list(tool_calls),
            memory_state=dict(memory_state),
            idempotency_key=key,
        )
        self._storage.save(key, cp.to_dict())
        self._seen_keys.add(key)
        self._current_step = step_number
        return cp

    def restore_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Load a checkpoint by its idempotency key.

        Returns *None* when the checkpoint does not exist.
        """
        data = self._storage.load(checkpoint_id)
        if data is None:
            return None
        return Checkpoint.from_dict(data)

    def resume_from_checkpoint(self, checkpoint_id: str) -> ExecutionState | None:
        """Restore state and prepare an *ExecutionState* for resumption.

        Returns *None* when the checkpoint does not exist.
        """
        cp = self.restore_checkpoint(checkpoint_id)
        if cp is None:
            return None

        return ExecutionState(
            restored_context=dict(cp.context_snapshot),
            restored_memory=dict(cp.memory_state),
            tool_calls_completed=list(cp.tool_calls_so_far),
            next_step=cp.step_number + 1,
            checkpoint=cp,
        )

    def list_checkpoints(self) -> list[str]:
        """Return all persisted checkpoint ids."""
        return self._storage.list_checkpoints()

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.  Returns *True* if it existed."""
        self._seen_keys.discard(checkpoint_id)
        return self._storage.delete(checkpoint_id)

    # -- Internals ------------------------------------------------------------

    @staticmethod
    def _build_storage(cfg: CheckpointConfig) -> CheckpointStorage:
        if cfg.storage_backend == "sqlite":
            return SQLiteStorage(cfg.storage_path)
        return JSONStorage(cfg.storage_path)
