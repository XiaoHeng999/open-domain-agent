"""Execution middleware chain — composable tool execution pipeline.

Middleware protocol and built-in implementations for safety, permission,
execution, and truncation. Each middleware is independently testable.

Chain order: SafetyMiddleware → PermissionMiddleware → TruncateMiddleware → ExecuteMiddleware
- Safety and Permission are outer layers that short-circuit on violations
- Truncate wraps Execute to truncate results
- Execute is the terminal middleware that calls the tool
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from open_agent.tools.base import Tool


@dataclass
class MiddlewareContext:
    """Context passed through the middleware chain."""

    tool: Tool
    params: dict[str, Any]
    tool_name: str
    safety_manager: Any = None
    permission_guard: Any = None
    max_tool_result_tokens: int = 2000


# Type aliases
NextMiddleware = Callable[[], Awaitable[str]]


class ExecutionMiddleware:
    """Base class for execution middleware.

    Subclass and override ``process`` to implement custom middleware.
    Call ``await next()`` to continue the chain.
    """

    async def process(
        self,
        context: MiddlewareContext,
        next: NextMiddleware,
    ) -> str:
        return await next()


class SafetyMiddleware(ExecutionMiddleware):
    """Run safety checks before execution."""

    async def process(
        self,
        context: MiddlewareContext,
        next: NextMiddleware,
    ) -> str:
        if context.safety_manager is not None:
            for check_type in context.tool.safety_checks:
                if check_type == "command":
                    command = context.params.get("command", "")
                    result = context.safety_manager.check_command(command)
                    if not result.safe:
                        return f"Error: Command blocked by safety policy: {result.reason}"
                elif check_type == "url":
                    url = context.params.get("url", "")
                    result = context.safety_manager.check_url(url)
                    if not result.safe:
                        return f"Error: URL blocked by safety policy: {result.reason}"
                elif check_type == "path":
                    path = context.params.get("path", "")
                    allow_write = not context.tool.read_only
                    result = context.safety_manager.check_path(path, allow_write=allow_write)
                    if not result.safe:
                        return f"Error: Path blocked by safety policy: {result.reason}"
        return await next()


class PermissionMiddleware(ExecutionMiddleware):
    """Check permissions before execution."""

    async def process(
        self,
        context: MiddlewareContext,
        next: NextMiddleware,
    ) -> str:
        if context.permission_guard is not None:
            from open_agent.safety.permission import PermissionDecision
            tool_meta = {"read_only": context.tool.read_only}
            perm_result = context.permission_guard.check(
                context.tool_name, context.params, tool_meta,
            )
            if perm_result.decision == PermissionDecision.DENY:
                return f"Error: Permission denied: {perm_result.reason}"
        return await next()


class TruncateMiddleware(ExecutionMiddleware):
    """Truncate result to configured token limit. Wraps the inner execute middleware."""

    async def process(
        self,
        context: MiddlewareContext,
        next: NextMiddleware,
    ) -> str:
        result = await next()
        max_chars = context.max_tool_result_tokens * 4
        if len(result) > max_chars:
            return result[:max_chars] + f"\n...[truncated, {len(result)} chars total]"
        return result


class ExecuteMiddleware(ExecutionMiddleware):
    """Execute the actual tool call. Terminal middleware."""

    async def process(
        self,
        context: MiddlewareContext,
        next: NextMiddleware,
    ) -> str:
        try:
            result = context.tool.execute(**context.params)
            if hasattr(result, "__await__"):
                result = await result
            return str(result)
        except Exception as exc:
            return f"Error: {exc}"


def build_middleware_chain(
    middlewares: list[ExecutionMiddleware],
) -> Callable[[MiddlewareContext], Awaitable[str]]:
    """Build a chain from a list of middlewares.

    Returns an async callable that takes a MiddlewareContext and returns
    the final result string.
    """
    async def chain(context: MiddlewareContext) -> str:
        async def dispatch(index: int) -> str:
            if index >= len(middlewares):
                return ""
            mw = middlewares[index]
            return await mw.process(context, lambda: dispatch(index + 1))
        return await dispatch(0)

    return chain


def default_chain(
    safety_manager: Any = None,
    permission_guard: Any = None,
    max_tool_result_tokens: int = 2000,
) -> Callable[[MiddlewareContext], Awaitable[str]]:
    """Build the default middleware chain: Safety → Permission → Truncate → Execute."""
    return build_middleware_chain([
        SafetyMiddleware(),
        PermissionMiddleware(),
        TruncateMiddleware(),
        ExecuteMiddleware(),
    ])
