"""ABC base classes and lifecycle hooks for all core components."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class BaseComponent(ABC):
    """Base for all core components with lifecycle hooks."""

    _registered: bool = False
    _started: bool = False

    async def on_register(self) -> None:
        self._registered = True

    async def on_start(self) -> None:
        self._started = True

    async def on_stop(self) -> None:
        self._started = False

    async def on_error(self, error: Exception) -> None:
        pass


class MemoryManager(BaseComponent, ABC):
    """Abstract interface for memory backends."""

    @abstractmethod
    async def read(self, query: str, **kwargs: Any) -> Any:
        ...

    @abstractmethod
    async def write(self, data: Any, **kwargs: Any) -> None:
        ...


class ToolExecutor(BaseComponent, ABC):
    """Abstract interface for tool execution."""

    @abstractmethod
    async def execute(self, tool_name: str, args: dict[str, Any]) -> Any:
        ...


class IntentRecognizer(BaseComponent, ABC):
    """Abstract interface for intent recognition."""

    @abstractmethod
    async def recognize(self, user_input: str) -> Any:
        ...


class Router(BaseComponent, ABC):
    """Abstract interface for request routing."""

    @abstractmethod
    async def route(self, user_input: str) -> Any:
        ...


class ModelProvider(BaseComponent, ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        ...

    @abstractmethod
    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        ...


@dataclass
class LifecycleState:
    """Track lifecycle state of a component."""

    registered: bool = False
    started: bool = False
    errors: list[str] = field(default_factory=list)
