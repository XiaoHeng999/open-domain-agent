"""Profile memory — SQLite-backed user preferences and avoidance hints."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from open_agent.base import MemoryManager
from open_agent.config import MemoryConfig

logger = logging.getLogger("open_agent.memory.profile")


class ProfileMemory(MemoryManager):
    """Persistent user profile stored in SQLite.

    Schema: single-row table (id=1) with JSON columns for preferences,
    constraints, tech_stack, and avoidance_hints.
    """

    def __init__(self, config: MemoryConfig | None = None) -> None:
        super().__init__()
        self._config = config or MemoryConfig()
        self._db_path = Path(self._config.profile_db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_db()

    # ------------------------------------------------------------------
    # Database lifecycle
    # ------------------------------------------------------------------

    def _ensure_db(self) -> None:
        """Create database and table if they don't exist."""
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                preferences TEXT NOT NULL DEFAULT '{}',
                constraints TEXT NOT NULL DEFAULT '[]',
                tech_stack TEXT NOT NULL DEFAULT '[]',
                risk_tolerance TEXT NOT NULL DEFAULT 'moderate',
                style TEXT NOT NULL DEFAULT 'concise',
                avoidance_hints TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL
            )
        """)
        # Ensure the default row exists
        row = self._conn.execute("SELECT COUNT(*) FROM user_profile").fetchone()
        if row[0] == 0:
            self._conn.execute(
                "INSERT INTO user_profile (id, updated_at) VALUES (1, ?)",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ"),),
            )
            self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # MemoryManager ABC
    # ------------------------------------------------------------------

    async def read(self, query: str = "", **kwargs: Any) -> dict[str, Any]:
        return self.load()

    async def write(self, data: Any, **kwargs: Any) -> None:
        if isinstance(data, dict):
            await self._apply_updates(data)
        elif isinstance(data, str):
            await self.add_avoidance_hint(data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Load profile from SQLite."""
        assert self._conn
        row = self._conn.execute(
            "SELECT preferences, constraints, tech_stack, risk_tolerance, style, avoidance_hints, updated_at "
            "FROM user_profile WHERE id = 1"
        ).fetchone()
        if not row:
            return {}
        return {
            "preferences": json.loads(row[0]),
            "constraints": json.loads(row[1]),
            "tech_stack": json.loads(row[2]),
            "risk_tolerance": row[3],
            "style": row[4],
            "avoidance_hints": json.loads(row[5]),
            "updated_at": row[6],
        }

    def save(self, profile: dict[str, Any]) -> None:
        """Write profile back to SQLite (atomic transaction)."""
        assert self._conn
        self._conn.execute(
            """UPDATE user_profile SET
                preferences = ?, constraints = ?, tech_stack = ?,
                risk_tolerance = ?, style = ?, avoidance_hints = ?, updated_at = ?
               WHERE id = 1""",
            (
                json.dumps(profile.get("preferences", {}), ensure_ascii=False),
                json.dumps(profile.get("constraints", []), ensure_ascii=False),
                json.dumps(profile.get("tech_stack", []), ensure_ascii=False),
                profile.get("risk_tolerance", "moderate"),
                profile.get("style", "concise"),
                json.dumps(profile.get("avoidance_hints", []), ensure_ascii=False),
                time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )
        self._conn.commit()

    async def update_preferences(self, prefs: dict[str, Any]) -> None:
        """Merge new preferences into existing profile."""
        profile = self.load()
        profile["preferences"].update(prefs)
        self.save(profile)

    async def update_constraints(self, constraints: list[str]) -> None:
        profile = self.load()
        existing = set(profile["constraints"])
        for c in constraints:
            if c not in existing:
                profile["constraints"].append(c)
                existing.add(c)
        self.save(profile)

    async def update_tech_stack(self, tech: list[str]) -> None:
        profile = self.load()
        existing = set(profile["tech_stack"])
        for t in tech:
            if t not in existing:
                profile["tech_stack"].append(t)
                existing.add(t)
        self.save(profile)

    async def add_avoidance_hint(self, hint: str) -> None:
        """Add an avoidance hint with deduplication."""
        if not hint:
            return
        profile = self.load()
        hints = profile["avoidance_hints"]
        # Exact match dedup
        if hint in hints:
            return
        # Substring dedup: if new hint contains or is contained by existing
        for existing in hints:
            if hint in existing or existing in hint:
                return
        hints.append(hint)
        self.save(profile)

    def get_injection_text(self) -> str:
        """Return structured profile text for system prompt injection."""
        profile = self.load()
        if not profile:
            return ""

        parts: list[str] = []
        prefs = profile.get("preferences")
        if prefs:
            pref_str = ", ".join(f"{k}: {v}" for k, v in prefs.items())
            parts.append(f"Preferences: {pref_str}")

        constraints = profile.get("constraints")
        if constraints:
            parts.append(f"Constraints: {', '.join(constraints)}")

        tech = profile.get("tech_stack")
        if tech:
            parts.append(f"Tech stack: {', '.join(tech)}")

        risk = profile.get("risk_tolerance")
        if risk and risk != "moderate":
            parts.append(f"Risk tolerance: {risk}")

        style = profile.get("style")
        if style and style != "concise":
            parts.append(f"Communication style: {style}")

        hints = profile.get("avoidance_hints")
        if hints:
            parts.append(f"Avoid: {'; '.join(hints)}")

        if not parts:
            return ""

        return "User profile — " + " | ".join(parts)

    async def _apply_updates(self, data: dict[str, Any]) -> None:
        if "preferences" in data:
            await self.update_preferences(data["preferences"])
        if "constraints" in data:
            await self.update_constraints(data["constraints"])
        if "tech_stack" in data:
            await self.update_tech_stack(data["tech_stack"])
        if "risk_tolerance" in data:
            profile = self.load()
            profile["risk_tolerance"] = data["risk_tolerance"]
            self.save(profile)
        if "style" in data:
            profile = self.load()
            profile["style"] = data["style"]
            self.save(profile)
        if "avoidance_hints" in data:
            for hint in data["avoidance_hints"]:
                await self.add_avoidance_hint(hint)
