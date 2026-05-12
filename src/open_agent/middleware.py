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
class SafetyRisk:
    """Safety risk information passed between SafetyMiddleware and PermissionMiddleware."""

    tool_name: str
    check_type: str
    reason: str
    risk_level: str  # "risky"
    matched_pattern: str | None = None


@dataclass
class MiddlewareContext:
    """Context passed through the middleware chain."""

    tool: Tool
    params: dict[str, Any]
    tool_name: str
    safety_manager: Any = None
    permission_guard: Any = None
    max_tool_result_tokens: int = 2000
    safety_risks: list[SafetyRisk] = field(default_factory=list)


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
    """Run safety checks before execution.

    Supports two safety_checks declaration formats:
    - Pure string "url" → equivalent to {"type": "url", "param": "url"}
    - Explicit mapping {"type": "url", "param": "target_url"}
    """

    @staticmethod
    def _resolve_check(check: str | dict[str, str]) -> tuple[str, str]:
        """Resolve a safety check declaration to (check_type, param_name)."""
        if isinstance(check, str):
            return check, check
        return check["type"], check.get("param", check["type"])

    async def process(
        self,
        context: MiddlewareContext,
        next: NextMiddleware,
    ) -> str:
        # Pass-through for subagent tool — sub-agents have their own safety chain
        if context.tool_name == "task":
            return await next()

        if context.safety_manager is not None:
            for check_decl in context.tool.safety_checks:
                check_type, param_name = self._resolve_check(check_decl)

                # Skip check if param not present in request
                if param_name not in context.params:
                    continue

                value = context.params[param_name]

                if check_type == "command":
                    result = context.safety_manager.check_command(value)
                elif check_type == "url":
                    result = context.safety_manager.check_url(value)
                elif check_type == "path":
                    allow_write = not context.tool.read_only
                    result = context.safety_manager.check_path(value, allow_write=allow_write)
                else:
                    continue

                if result.risk_level == "blocked":
                    return f"Error: {check_type.capitalize()} blocked by safety policy: {result.reason}"

                if result.risk_level == "risky":
                    context.safety_risks.append(SafetyRisk(
                        tool_name=context.tool_name,
                        check_type=check_type,
                        reason=result.reason,
                        risk_level="risky",
                        matched_pattern=result.matched_pattern,
                    ))
                # "safe" → continue without action

        return await next()


class PermissionMiddleware(ExecutionMiddleware):
    """Check permissions before execution.

    Also checks context.safety_risks from SafetyMiddleware — risky-level
    safety risks trigger HITL confirmation when not in unrestricted mode.
    """

    async def process(
        self,
        context: MiddlewareContext,
        next: NextMiddleware,
    ) -> str:
        # Pass-through for subagent tool — sub-agents have independent permission control
        if context.tool_name == "task":
            return await next()

        # Handle safety risk escalation
        if context.safety_risks and context.permission_guard is not None:
            from open_agent.safety.permission import PermissionMode

            risky_risks = [r for r in context.safety_risks if r.risk_level == "risky"]
            if risky_risks:
                # In unrestricted mode, auto-approve risky operations
                if context.permission_guard._mode != PermissionMode.UNRESTRICTED:
                    from open_agent.safety.permission import PermissionDecision
                    perm_result = context.permission_guard.check_with_safety(
                        context.tool_name, context.params,
                        {"read_only": context.tool.read_only},
                        risky_risks,
                    )
                    if perm_result.decision == PermissionDecision.DENY:
                        return f"Error: Permission denied: {perm_result.reason}"

        # Standard permission check
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
