"""ToolRegistry v2 — backed by Tool ABC instances.

Supports:
- register/unregister/get/has/snapshot/restore (preserved from v1)
- execute(name, params): async 3-stage pipeline (cast → validate → safety → execute → truncate)
- get_definitions(): Anthropic tool_use format output for all registered tools
- scan_builtin_tools(): auto-discover and register built-in tools
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from open_agent.tools.base import FunctionTool, Tool

logger = logging.getLogger("open_agent")


class ToolRegistry:
    """Dynamic tool registry — supports runtime register/unregister/list/execute."""

    def __init__(
        self,
        safety_manager: Any = None,
        max_tool_result_tokens: int = 2000,
        permission_guard: Any = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._tags: dict[str, list[str]] = {}
        self._safety_manager = safety_manager
        self._max_tool_result_tokens = max_tool_result_tokens
        self._permission_guard = permission_guard

    def register(self, tool: Tool, tags: list[str] | None = None) -> None:
        """Register a Tool ABC instance."""
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        self._tags[tool.name] = tags or []

    def unregister(self, name: str) -> None:
        """Remove a single tool by name."""
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        del self._tools[name]
        self._tags.pop(name, None)

    def unregister_by_server(self, server_id: str) -> int:
        """Remove all tools from a specific MCP server. Returns count removed."""
        to_remove = [
            n for n, t in self._tools.items()
            if getattr(t, "_server_id", None) == server_id
        ]
        for name in to_remove:
            del self._tools[name]
            self._tags.pop(name, None)
        return len(to_remove)

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def list_by_tag(self, tag: str) -> list[Tool]:
        return [
            t for n, t in self._tools.items()
            if tag in self._tags.get(n, [])
        ]

    def filter_by_tags(self, tags: list[str]) -> list[Tool]:
        """Return tools matching *any* of the given tags."""
        return [
            t for n, t in self._tools.items()
            if any(tag in self._tags.get(n, []) for tag in tags)
        ]

    # ── Snapshot / Restore ──

    def snapshot(self) -> frozenset[str]:
        """Return a snapshot of current tool names."""
        return frozenset(self._tools.keys())

    def restore(self, snapshot: frozenset[str]) -> None:
        """Restore registry to a previous snapshot, removing tools not in it."""
        current = set(self._tools.keys())
        for name in current - snapshot:
            del self._tools[name]
            self._tags.pop(name, None)

    # ── Execution pipeline ──

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """Execute a tool through the full pipeline: cast → validate → safety → execute → truncate."""
        if name not in self._tools:
            return f"Error: Tool not found: {name}"

        tool = self._tools[name]

        # Stage 1: cast_params
        try:
            params = tool.cast_params(params)
        except Exception as exc:
            return f"Error: Parameter cast failed: {exc}"

        # Stage 2: validate_params
        errors = tool.validate_params(params)
        if errors:
            return f"Error: Validation failed: {'; '.join(errors)}"

        # Stage 3: safety checks
        if self._safety_manager is not None:
            safety_error = self._run_safety_checks(tool, params)
            if safety_error:
                return safety_error

        # Stage 3.5: permission guard
        if self._permission_guard is not None:
            from open_agent.safety.permission import PermissionDecision
            tool_meta = {"read_only": tool.read_only}
            perm_result = self._permission_guard.check(name, params, tool_meta)
            if perm_result.decision == PermissionDecision.DENY:
                return f"Error: Permission denied: {perm_result.reason}"

        # Stage 4: execute
        try:
            result = tool.execute(**params)
            if hasattr(result, "__await__"):
                result = await result
            result = str(result)
        except Exception as exc:
            result = f"Error: {exc}"

        # Stage 5: truncate
        result = self._truncate_result(result)

        return result

    def _run_safety_checks(
        self, tool: Tool, params: dict[str, Any],
    ) -> str | None:
        """Run safety checks for the tool. Returns error string or None."""
        for check_type in tool.safety_checks:
            if check_type == "command":
                command = params.get("command", "")
                result = self._safety_manager.check_command(command)
                if not result.safe:
                    return f"Error: Command blocked by safety policy: {result.reason}"
            elif check_type == "url":
                url = params.get("url", "")
                result = self._safety_manager.check_url(url)
                if not result.safe:
                    return f"Error: URL blocked by safety policy: {result.reason}"
            elif check_type == "path":
                path = params.get("path", "")
                allow_write = not tool.read_only
                result = self._safety_manager.check_path(path, allow_write=allow_write)
                if not result.safe:
                    return f"Error: Path blocked by safety policy: {result.reason}"
        return None

    def _truncate_result(self, result: str) -> str:
        """Truncate result based on max_tool_result_tokens config."""
        max_chars = self._max_tool_result_tokens * 4
        if len(result) > max_chars:
            return result[:max_chars] + f"\n...[truncated, {len(result)} chars total]"
        return result

    # ── Schema export ──

    def get_definitions(self) -> list[dict[str, Any]]:
        """Return all registered tools' to_schema() output (Anthropic tool_use format)."""
        return [tool.to_schema() for tool in self._tools.values()]


def scan_builtin_tools(registry: ToolRegistry, config: Any) -> None:
    """Auto-discover and register all built-in tools.

    Imports tool modules from open_agent.tools and registers Tool subclasses.
    Conditional registration based on config (e.g. exec enable, API keys).
    """
    # Filesystem tools
    from open_agent.tools.filesystem import (
        EditFileTool, ListDirTool, ReadFileTool, WriteFileTool,
    )
    workspace = getattr(config, "workspace", ".")
    registry.register(ReadFileTool(workspace=workspace))
    registry.register(WriteFileTool(workspace=workspace))
    registry.register(EditFileTool(workspace=workspace))
    registry.register(ListDirTool(workspace=workspace))

    # Shell tool — conditional on exec_config.enable
    exec_enabled = getattr(
        getattr(config, "tools", None), "exec_enabled", True,
    )
    if exec_enabled:
        from open_agent.tools.shell import ExecTool
        registry.register(ExecTool(workspace=workspace))

    # Web tools
    from open_agent.tools.web import WebFetchTool, WebSearchTool
    api_key = getattr(
        getattr(config, "tools", None), "brave_search_api_key", None,
    )
    registry.register(WebSearchTool(api_key=api_key))
    registry.register(WebFetchTool())

    # Todo tool
    from open_agent.tools.todo import TodoTool
    registry.register(TodoTool())
