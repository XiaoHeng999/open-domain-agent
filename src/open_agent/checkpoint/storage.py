"""Storage backends for checkpoint persistence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class CheckpointStorage(ABC):
    """Abstract base for checkpoint storage backends."""

    @abstractmethod
    def save(self, checkpoint_id: str, data: dict[str, Any]) -> None:
        """Persist a checkpoint dictionary under the given id."""
        ...

    @abstractmethod
    def load(self, checkpoint_id: str) -> dict[str, Any] | None:
        """Load a checkpoint by id.  Returns *None* when not found."""
        ...

    @abstractmethod
    def list_checkpoints(self) -> list[str]:
        """Return all stored checkpoint ids, sorted newest-first when possible."""
        ...

    @abstractmethod
    def delete(self, checkpoint_id: str) -> bool:
        """Remove a checkpoint.  Returns *True* if it existed and was deleted."""
        ...


class JSONStorage(CheckpointStorage):
    """File-system storage using one JSON file per checkpoint."""

    def __init__(self, storage_path: str | Path) -> None:
        self._root = Path(storage_path)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, checkpoint_id: str) -> Path:
        return self._root / f"{checkpoint_id}.json"

    def save(self, checkpoint_id: str, data: dict[str, Any]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        tmp = self._path_for(f"{checkpoint_id}.tmp")
        final = self._path_for(checkpoint_id)
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(final)

    def load(self, checkpoint_id: str) -> dict[str, Any] | None:
        p = self._path_for(checkpoint_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def list_checkpoints(self) -> list[str]:
        files = sorted(
            self._root.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        return [f.stem for f in files]

    def delete(self, checkpoint_id: str) -> bool:
        p = self._path_for(checkpoint_id)
        if p.exists():
            p.unlink()
            return True
        return False


class SQLiteStorage(CheckpointStorage):
    """SQLite-backed checkpoint storage."""

    def __init__(self, storage_path: str | Path) -> None:
        self._db_path = Path(storage_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS checkpoints ("
            "  id TEXT PRIMARY KEY,"
            "  data TEXT NOT NULL,"
            "  created_at REAL NOT NULL"
            ")"
        )
        self._conn.commit()

    def save(self, checkpoint_id: str, data: dict[str, Any]) -> None:
        import time

        payload = json.dumps(data, indent=2, ensure_ascii=False)
        self._conn.execute(
            "INSERT OR REPLACE INTO checkpoints (id, data, created_at) VALUES (?, ?, ?)",
            (checkpoint_id, payload, time.time()),
        )
        self._conn.commit()

    def load(self, checkpoint_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT data FROM checkpoints WHERE id = ?", (checkpoint_id,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def list_checkpoints(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT id FROM checkpoints ORDER BY created_at DESC"
        ).fetchall()
        return [r[0] for r in rows]

    def delete(self, checkpoint_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM checkpoints WHERE id = ?", (checkpoint_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        self._conn.close()
