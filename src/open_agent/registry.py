"""ToolRegistry v2 — backed by Tool ABC instances.

Supports:
- register/unregister/get/has/snapshot/restore (preserved from v1)
- execute(name, params): async pipeline via middleware chain (cast → validate → safety → permission → execute → truncate)
- get_definitions(): Anthropic tool_use format output for all registered tools
- scan_builtin_tools(): auto-discover and register built-in tools
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from open_agent.middleware import (
    MiddlewareContext, default_chain, build_middleware_chain,
)
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
        self._chain = default_chain(
            safety_manager=safety_manager,
            permission_guard=permission_guard,
            max_tool_result_tokens=max_tool_result_tokens,
        )

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
        """Execute a tool through the middleware chain: cast → validate → safety → permission → truncate → execute."""
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

        # Stage 3+: middleware chain (safety → permission → truncate → execute)
        ctx = MiddlewareContext(
            tool=tool,
            params=params,
            tool_name=name,
            safety_manager=self._safety_manager,
            permission_guard=self._permission_guard,
            max_tool_result_tokens=self._max_tool_result_tokens,
        )
        return await self._chain(ctx)

    # ── Schema export ──

    def get_definitions(self) -> list[dict[str, Any]]:
        """Return all registered tools' to_schema() output (Anthropic tool_use format)."""
        return [tool.to_schema() for tool in self._tools.values()]


def scan_builtin_tools(registry: ToolRegistry, config: Any, **runtime_kwargs: Any) -> None:
    """Auto-discover and register all built-in tools.

    Imports tool modules from open_agent.tools and registers Tool subclasses.
    Conditional registration based on config (e.g. exec enable, API keys).

    Optional runtime_kwargs for tools that need runtime dependencies:
    - react_loop: ReActLoop instance (for SelfTool)
    - runtime: AgentRuntime instance (for SelfTool)
    - sandbox: Sandbox instance (for SandboxControlTool)
    - mcp_manager: MCPServerManager instance (for MCPClientTool)
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

    # Web tools — conditional search backend registration
    from open_agent.tools.web import BraveSearchTool, DuckDuckGoSearchTool, WebFetchTool
    tools_config = getattr(config, "tools", None)
    api_key = getattr(tools_config, "brave_search_api_key", None)
    backend = getattr(tools_config, "search_backend", "auto")

    search_tool: Tool | None = None
    if backend == "duckduckgo":
        search_tool = DuckDuckGoSearchTool()
    elif backend == "brave":
        if api_key:
            search_tool = BraveSearchTool(api_key=api_key)
        # else: no search tool registered — LLM won't see web_search
    else:  # auto
        if api_key:
            search_tool = BraveSearchTool(api_key=api_key)
        else:
            search_tool = DuckDuckGoSearchTool()

    if search_tool is not None:
        registry.register(search_tool)

    registry.register(WebFetchTool())

    # Todo tool
    from open_agent.tools.todo import TodoTool
    registry.register(TodoTool())

    # Search tool (code search via ripgrep/glob) — always registered with workspace
    from open_agent.tools.search import SearchTool
    registry.register(SearchTool(workspace=workspace))

    # Runtime-dependent tools — registered only when their dependencies are provided
    react_loop = runtime_kwargs.get("react_loop")
    runtime = runtime_kwargs.get("runtime")
    if react_loop is not None or runtime is not None:
        from open_agent.tools.self import SelfTool
        registry.register(SelfTool(react_loop=react_loop, runtime=runtime))

    sandbox = runtime_kwargs.get("sandbox")
    if sandbox is not None:
        from open_agent.tools.sandbox_control import SandboxControlTool
        registry.register(SandboxControlTool(sandbox=sandbox))

    mcp_manager = runtime_kwargs.get("mcp_manager")
    if mcp_manager is not None:
        from open_agent.tools.mcp_client import MCPClientTool
        registry.register(MCPClientTool(mcp_manager=mcp_manager))
