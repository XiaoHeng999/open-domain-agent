"""Factory helpers for creating memory subsystem instances."""

from __future__ import annotations

from open_agent.config import MemoryConfig

from .episodic import EpisodicStore
from .profile import UserProfileState
from .semantic import InMemorySemanticKB, SemanticKB
from .working import WorkingMemory


class MemoryFactory:
    """Creates configured memory subsystem instances from a MemoryConfig."""

    def __init__(self, config: MemoryConfig | None = None) -> None:
        self._config = config or MemoryConfig()

    def create_working_memory(self) -> WorkingMemory:
        """Create a new WorkingMemory with the stored config."""
        return WorkingMemory(config=self._config)

    def create_episodic_store(self) -> EpisodicStore:
        """Create a new EpisodicStore."""
        return EpisodicStore(config=self._config)

    def create_user_profile(self) -> UserProfileState:
        """Create a new UserProfileState."""
        return UserProfileState(config=self._config)

    def create_semantic_kb(self) -> SemanticKB:
        """Create the default semantic KB (in-memory stub for now)."""
        return InMemorySemanticKB()
