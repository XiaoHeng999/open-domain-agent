"""Dynamic ToolRegistry — runtime register / unregister / list / list_by_tag."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolEntry:
    """A registered tool with its schema, implementation, and metadata."""

    name: str
    schema: dict[str, Any]
    handler: Callable[..., Any]
    tags: list[str] = field(default_factory=list)
    server_id: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "schema": self.schema,
        }


class ToolRegistry:
    """Dynamic tool registry — supports runtime register/unregister/list."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        handler: Callable[..., Any],
        schema: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        server_id: str | None = None,
        description: str = "",
    ) -> ToolEntry:
        """Register a tool. Schema is auto-derived from @tool_schema if available."""
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")

        if schema is None and hasattr(handler, "_tool_schema"):
            schema = handler._tool_schema
        elif schema is None:
            schema = {
                "name": name,
                "description": description or getattr(handler, "__doc__", "") or "",
                "inputSchema": {"type": "object", "properties": {}},
            }

        entry = ToolEntry(
            name=name,
            schema=schema,
            handler=handler,
            tags=tags or [],
            server_id=server_id,
            description=description or schema.get("description", ""),
        )
        self._tools[name] = entry
        return entry

    def unregister(self, name: str) -> None:
        """Remove a single tool by name."""
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        del self._tools[name]

    def unregister_by_server(self, server_id: str) -> int:
        """Remove all tools from a specific MCP server. Returns count removed."""
        to_remove = [n for n, t in self._tools.items() if t.server_id == server_id]
        for name in to_remove:
            del self._tools[name]
        return len(to_remove)

    def get(self, name: str) -> ToolEntry:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def list_tools(self) -> list[ToolEntry]:
        return list(self._tools.values())

    def list_by_tag(self, tag: str) -> list[ToolEntry]:
        return [t for t in self._tools.values() if tag in t.tags]

    def has(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    # ── Snapshot / Restore / Filter ──

    def snapshot(self) -> frozenset[str]:
        """Return a snapshot of current tool names."""
        return frozenset(self._tools.keys())

    def restore(self, snapshot: frozenset[str]) -> None:
        """Restore registry to a previous snapshot, removing tools not in it."""
        current = set(self._tools.keys())
        for name in current - snapshot:
            del self._tools[name]

    def filter_by_tags(self, tags: list[str]) -> list[ToolEntry]:
        """Return tools matching *any* of the given tags."""
        return [t for t in self._tools.values() if any(tag in t.tags for tag in tags)]
