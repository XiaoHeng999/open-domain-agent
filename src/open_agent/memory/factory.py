"""Factory helpers for creating memory subsystem instances."""

from __future__ import annotations

from open_agent.config import MemoryConfig

from .archive import ArchiveMemory
from .episodic import EpisodicStore  # noqa: F401 — backward compat
from .profile import ProfileMemory
from .retrieval import RetrievalMemory
from .runtime import RuntimeMemory
from .semantic import InMemorySemanticKB  # noqa: F401 — backward compat
from .working import WorkingMemory  # noqa: F401 — backward compat


class MemoryFactory:
    """Creates configured memory subsystem instances from a MemoryConfig."""

    def __init__(self, config: MemoryConfig | None = None) -> None:
        self._config = config or MemoryConfig()

    def create_runtime_memory(self) -> RuntimeMemory:
        """Create a new RuntimeMemory with the stored config."""
        return RuntimeMemory(config=self._config)

    def create_profile_memory(self) -> ProfileMemory:
        """Create a new ProfileMemory backed by SQLite."""
        return ProfileMemory(config=self._config)

    def create_retrieval_memory(self) -> RetrievalMemory:
        """Create a new RetrievalMemory with vector store."""
        return RetrievalMemory(config=self._config)

    def create_archive_memory(self, session_id: str = "") -> ArchiveMemory:
        """Create a new ArchiveMemory for a session."""
        return ArchiveMemory(config=self._config, session_id=session_id)

    # Backward compat aliases
    def create_working_memory(self) -> WorkingMemory:
        return WorkingMemory(config=self._config)

    def create_episodic_store(self) -> EpisodicStore:
        return EpisodicStore(config=self._config)

    def create_user_profile(self):
        """Create a new UserProfileState (backward compat)."""
        from open_agent.memory import UserProfileState
        return UserProfileState(config=self._config)

    def create_semantic_kb(self) -> InMemorySemanticKB:
        return InMemorySemanticKB()
