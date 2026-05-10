"""User profile memory — preferences, habits, and avoidance hints."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import MemoryManager
from open_agent.config import MemoryConfig


@dataclass
class UserProfile:
    """Represents a user's accumulated profile."""

    preferences: dict[str, Any] = field(default_factory=dict)
    habits: list[str] = field(default_factory=list)
    avoidance_hints: list[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)


class UserProfileState(MemoryManager):
    """Manages a user profile in memory.

    Supports loading / updating preferences, habits, and avoidance hints.
    Avoidance hints record error patterns and user corrections so the agent
    can avoid repeating the same mistakes.
    """

    def __init__(self, config: MemoryConfig | None = None) -> None:
        super().__init__()
        self._config = config or MemoryConfig()
        self._profile: UserProfile = UserProfile()

    # ------------------------------------------------------------------
    # MemoryManager ABC
    # ------------------------------------------------------------------

    async def read(self, query: str = "", **kwargs: Any) -> UserProfile:
        """Return the current user profile."""
        return self._profile

    async def write(self, data: Any, **kwargs: Any) -> None:
        """Update the profile. Accepts a UserProfile, dict, or avoidance-hint string."""
        if isinstance(data, UserProfile):
            self._profile = data
        elif isinstance(data, dict):
            await self.update_user_profile(**data)
        elif isinstance(data, str):
            await self.add_avoidance_hint(data)
        else:
            raise TypeError(f"Cannot write profile data of type {type(data)}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def load_user_profile(self, profile: UserProfile | dict[str, Any] | None = None) -> UserProfile:
        """Load (or replace) the user profile.

        If *profile* is ``None``, starts with an empty profile.
        """
        if profile is None:
            self._profile = UserProfile()
        elif isinstance(profile, UserProfile):
            self._profile = profile
        elif isinstance(profile, dict):
            self._profile = UserProfile(
                preferences=profile.get("preferences", {}),
                habits=profile.get("habits", []),
                avoidance_hints=profile.get("avoidance_hints", []),
            )
        else:
            raise TypeError(f"Cannot load profile of type {type(profile)}")
        return self._profile

    async def update_user_profile(
        self,
        preferences: dict[str, Any] | None = None,
        habits: list[str] | None = None,
        avoidance_hints: list[str] | None = None,
    ) -> UserProfile:
        """Merge updates into the current profile."""
        if preferences is not None:
            self._profile.preferences.update(preferences)
        if habits is not None:
            # Append new habits without duplicates
            existing = set(self._profile.habits)
            for h in habits:
                if h not in existing:
                    self._profile.habits.append(h)
                    existing.add(h)
        if avoidance_hints is not None:
            existing = set(self._profile.avoidance_hints)
            for h in avoidance_hints:
                if h not in existing:
                    self._profile.avoidance_hints.append(h)
                    existing.add(h)
        self._profile.updated_at = time.time()
        return self._profile

    async def add_avoidance_hint(self, hint: str) -> None:
        """Record a single avoidance hint (error pattern or user correction)."""
        if hint and hint not in self._profile.avoidance_hints:
            self._profile.avoidance_hints.append(hint)
            self._profile.updated_at = time.time()

    async def record_error_pattern(self, error_description: str) -> None:
        """Convenience: record an error pattern as an avoidance hint."""
        await self.add_avoidance_hint(f"Error: {error_description}")

    async def record_user_correction(self, correction: str) -> None:
        """Convenience: record a user correction as an avoidance hint."""
        await self.add_avoidance_hint(f"User correction: {correction}")

    @property
    def profile(self) -> UserProfile:
        """Read-only access to the current profile."""
        return self._profile
