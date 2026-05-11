"""Memory subsystem — 4-layer architecture: Runtime, Profile, Retrieval, Archive."""

from .archive import ArchiveMemory
from .factory import MemoryFactory
from .models import Message, TaskState
from .profile import ProfileMemory
from .retrieval import EmbeddingService, RetrievalMemory, VectorStore
from .runtime import RuntimeMemory
from .token_utils import estimate_tokens

# Backward compat — old names still importable
from .episodic import EpisodicStore, EpisodicSummary  # noqa: F401
from .semantic import InMemorySemanticKB, SemanticKB  # noqa: F401
from .working import WorkingMemory, Message as _OldMessage  # noqa: F401

# Backward compat — UserProfile dataclass and UserProfileState
import dataclasses
import time as _time


@dataclasses.dataclass
class UserProfile:
    """Backward compat — use ProfileMemory instead."""
    preferences: dict = dataclasses.field(default_factory=dict)
    habits: list[str] = dataclasses.field(default_factory=list)
    avoidance_hints: list[str] = dataclasses.field(default_factory=list)
    updated_at: float = 0.0


class UserProfileState(ProfileMemory):
    """Backward compat wrapper providing the old UserProfileState API."""

    def __init__(self, config=None):
        super().__init__(config=config)
        self._compat_profile = UserProfile()

    @property
    def profile(self) -> UserProfile:
        return self._compat_profile

    async def load_user_profile(self, profile=None):
        if profile is None:
            self._compat_profile = UserProfile()
        elif isinstance(profile, UserProfile):
            self._compat_profile = profile
        elif isinstance(profile, dict):
            self._compat_profile = UserProfile(
                preferences=profile.get("preferences", {}),
                habits=profile.get("habits", []),
                avoidance_hints=profile.get("avoidance_hints", []),
            )
        return self._compat_profile

    async def update_user_profile(
        self, preferences=None, habits=None, avoidance_hints=None,
    ):
        if preferences:
            self._compat_profile.preferences.update(preferences)
        if habits:
            existing = set(self._compat_profile.habits)
            for h in habits:
                if h not in existing:
                    self._compat_profile.habits.append(h)
                    existing.add(h)
        if avoidance_hints:
            existing = set(self._compat_profile.avoidance_hints)
            for h in avoidance_hints:
                if h not in existing:
                    self._compat_profile.avoidance_hints.append(h)
                    existing.add(h)
        self._compat_profile.updated_at = _time.time()
        return self._compat_profile

    async def add_avoidance_hint(self, hint: str):
        await super().add_avoidance_hint(hint)
        if hint and hint not in self._compat_profile.avoidance_hints:
            self._compat_profile.avoidance_hints.append(hint)
            self._compat_profile.updated_at = _time.time()

    async def record_error_pattern(self, error_description: str):
        hint = f"Error: {error_description}"
        await self.add_avoidance_hint(hint)

    async def record_user_correction(self, correction: str):
        hint = f"User correction: {correction}"
        await self.add_avoidance_hint(hint)

    async def write(self, data, **kwargs):
        if isinstance(data, dict):
            # Backward compat: handle {"avoidance_hints": [...]} format
            if "avoidance_hints" in data:
                for hint in data["avoidance_hints"]:
                    await self.add_avoidance_hint(hint)
                return
            if "preferences" in data:
                await self.update_user_profile(preferences=data["preferences"])
                return
            await super().write(data, **kwargs)
        elif isinstance(data, str):
            await self.add_avoidance_hint(data)
        else:
            await super().write(data, **kwargs)

    async def read(self, query="", **kwargs):
        """Return UserProfile object for backward compat."""
        return self._compat_profile

__all__ = [
    # New 4-layer
    "ArchiveMemory",
    "EmbeddingService",
    "MemoryFactory",
    "Message",
    "ProfileMemory",
    "RetrievalMemory",
    "RuntimeMemory",
    "TaskState",
    "TokenEstimator",
    "VectorStore",
    "estimate_tokens",
    # Backward compat
    "EpisodicStore",
    "EpisodicSummary",
    "InMemorySemanticKB",
    "SemanticKB",
    "WorkingMemory",
]
