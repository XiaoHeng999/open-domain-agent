"""Tests for middleware chain (tasks 4.1-4.7)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from open_agent.middleware import (
    ExecuteMiddleware,
    ExecutionMiddleware,
    MiddlewareContext,
    OutputValidationMiddleware,
    PermissionMiddleware,
    SafetyMiddleware,
    TruncateMiddleware,
    build_middleware_chain,
    default_chain,
)
from open_agent.tools.base import FunctionTool, Tool


async def _ok():
    return "ok"


def _make_tool(**kwargs) -> FunctionTool:
    defaults = {
        "name": "test_tool",
        "description": "test",
        "parameters": {"type": "object", "properties": {}},
        "handler": lambda: "ok",
    }
    defaults.update(kwargs)
    return FunctionTool(**defaults)


def _make_context(**overrides) -> MiddlewareContext:
    defaults = {
        "tool": _make_tool(),
        "params": {},
        "tool_name": "test_tool",
    }
    defaults.update(overrides)
    return MiddlewareContext(**defaults)


# ── 4.1 ExecutionMiddleware base ──


class TestExecutionMiddlewareBase:
    async def test_base_passes_through(self):
        mw = ExecutionMiddleware()
        ctx = _make_context()
        result = await mw.process(ctx, _ok)
        assert result == "ok"


# ── 4.2 SafetyMiddleware ──


class TestSafetyMiddleware:
    async def test_passes_when_no_safety_manager(self):
        mw = SafetyMiddleware()
        ctx = _make_context()
        result = await mw.process(ctx, _ok)
        assert result == "ok"

    async def test_blocks_dangerous_command(self):
        mw = SafetyMiddleware()
        safety = MagicMock()
        safety.check_command = MagicMock(return_value=MagicMock(safe=False, reason="dangerous"))
        tool = _make_tool(safety_checks=["command"])
        ctx = _make_context(
            tool=tool,
            params={"command": "rm -rf /"},
            safety_manager=safety,
        )
        result = await mw.process(ctx, _ok)
        assert "blocked" in result.lower()

    async def test_allows_safe_command(self):
        mw = SafetyMiddleware()
        safety = MagicMock()
        safety.check_command = MagicMock(return_value=MagicMock(safe=True))
        tool = _make_tool(safety_checks=["command"])
        ctx = _make_context(
            tool=tool,
            params={"command": "ls"},
            safety_manager=safety,
        )
        result = await mw.process(ctx, _ok)
        assert result == "ok"


# ── 4.3 PermissionMiddleware ──


class TestPermissionMiddleware:
    async def test_passes_when_no_guard(self):
        mw = PermissionMiddleware()
        ctx = _make_context()
        result = await mw.process(ctx, _ok)
        assert result == "ok"

    async def test_blocks_when_denied(self):
        mw = PermissionMiddleware()
        from open_agent.safety.permission import PermissionDecision
        guard = MagicMock()
        guard.check = MagicMock(return_value=MagicMock(
            decision=PermissionDecision.DENY,
            reason="not allowed",
        ))
        ctx = _make_context(permission_guard=guard)
        result = await mw.process(ctx, _ok)
        assert "Permission denied" in result

    async def test_allows_when_approved(self):
        mw = PermissionMiddleware()
        from open_agent.safety.permission import PermissionDecision
        guard = MagicMock()
        guard.check = MagicMock(return_value=MagicMock(
            decision=PermissionDecision.ALLOW,
        ))
        ctx = _make_context(permission_guard=guard)
        result = await mw.process(ctx, _ok)
        assert result == "ok"


# ── 4.4 ExecuteMiddleware ──


class TestExecuteMiddleware:
    async def test_executes_tool(self):
        mw = ExecuteMiddleware()
        tool = _make_tool(handler=lambda: "hello")
        ctx = _make_context(tool=tool)
        result = await mw.process(ctx, _ok)
        assert result == "hello"

    async def test_handles_exception(self):
        mw = ExecuteMiddleware()

        def _fail():
            raise ValueError("tool error")

        tool = _make_tool(handler=_fail)
        ctx = _make_context(tool=tool)
        result = await mw.process(ctx, _ok)
        assert "Error" in result

    async def test_handles_async_tool(self):
        mw = ExecuteMiddleware()

        async def _async_handler():
            return "async_result"

        tool = _make_tool(handler=_async_handler)
        ctx = _make_context(tool=tool)
        result = await mw.process(ctx, _ok)
        assert result == "async_result"


# ── 4.5 TruncateMiddleware ──


class TestTruncateMiddleware:
    async def test_short_result_unchanged(self):
        mw = TruncateMiddleware()
        ctx = _make_context(max_tool_result_tokens=2000)
        result = await mw.process(ctx, _ok)
        assert result == "ok"

    async def test_long_result_truncated(self):
        mw = TruncateMiddleware()
        ctx = _make_context(max_tool_result_tokens=1)  # 1 token = 4 chars budget

        async def _long():
            return "a" * 100

        result = await mw.process(ctx, _long)
        assert "truncated" in result
        assert len(result) < 100


# ── 4.6 Full chain via ToolRegistry ──


class TestFullChain:
    async def test_full_chain_safety_blocks(self):
        registry = __import__("open_agent.registry", fromlist=["ToolRegistry"]).ToolRegistry()
        safety = MagicMock()
        safety.check_command = MagicMock(return_value=MagicMock(safe=False, reason="dangerous"))
        registry._safety_manager = safety
        registry._chain = default_chain(
            safety_manager=safety,
            max_tool_result_tokens=2000,
        )
        tool = _make_tool(
            name="exec",
            safety_checks=["command"],
            handler=lambda command: "executed",
        )
        registry.register(tool)
        result = await registry.execute("exec", {"command": "rm -rf /"})
        assert "blocked" in result.lower()


# ── 4.7 Recovery through pipeline ──


class TestRecoveryThroughPipeline:
    async def test_recovery_uses_registry_execute(self):
        """Recovery strategies should use tool_registry.execute() not tool_handler directly."""
        from open_agent.recovery.strategies import ParameterRecoveryStrategy
        from open_agent.errors import ParameterError

        strategy = ParameterRecoveryStrategy()
        registry = MagicMock()
        registry.execute = AsyncMock(return_value="recovered result")

        context = {
            "tool_registry": registry,
            "tool_name": "test_tool",
            "args": {"key": "value"},
            "fixed_args": {"key": "fixed"},
        }
        result = await strategy.execute(ParameterError("bad param"), context)
        assert result.status.value == "success"
        registry.execute.assert_called_once_with("test_tool", {"key": "fixed"})


# -- OutputValidationMiddleware --


class _SchemaTool(Tool):
    """Test tool with an output_schema."""

    output_schema = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array"}}}

    @property
    def name(self) -> str:
        return "schema_tool"

    @property
    def description(self) -> str:
        return "test"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return '{"items": [1, 2, 3]}'


class _SchemaFailTool(Tool):
    """Test tool whose output doesn't match schema."""

    output_schema = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array"}}}

    @property
    def name(self) -> str:
        return "schema_fail_tool"

    @property
    def description(self) -> str:
        return "test"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return '{"data": "something"}'


class _SemanticFailTool(Tool):
    """Test tool whose output fails semantic validation."""

    output_schema = {"type": "object", "required": []}

    @property
    def name(self) -> str:
        return "semantic_fail_tool"

    @property
    def description(self) -> str:
        return "test"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    def validate_output(self, result: str) -> list[str]:
        return ["Search returned no results"]

    async def execute(self, **kwargs):
        return '{"items": []}'


class TestOutputValidationMiddleware:
    async def test_compliant_output_passes(self):
        mw = OutputValidationMiddleware()
        tool = _SchemaTool()
        ctx = _make_context(tool=tool)

        async def _result():
            return '{"items": [1, 2, 3]}'

        result = await mw.process(ctx, _result)
        assert "Error" not in result
        assert "items" in result

    async def test_non_compliant_output_blocked(self):
        mw = OutputValidationMiddleware()
        tool = _SchemaFailTool()
        ctx = _make_context(tool=tool)

        async def _result():
            return '{"data": "something"}'

        result = await mw.process(ctx, _result)
        assert "Error" in result
        assert "Output validation failed" in result

    async def test_no_schema_passes_through(self):
        mw = OutputValidationMiddleware()
        tool = _make_tool(handler=lambda: "plain text")
        ctx = _make_context(tool=tool)

        async def _result():
            return "plain text"

        result = await mw.process(ctx, _result)
        assert result == "plain text"

    async def test_semantic_validation_failure(self):
        mw = OutputValidationMiddleware()
        tool = _SemanticFailTool()
        ctx = _make_context(tool=tool)

        async def _result():
            return '{"items": []}'

        result = await mw.process(ctx, _result)
        assert "Error" in result
        assert "semantic validation failed" in result

    async def test_string_result_skips_schema_validation(self):
        mw = OutputValidationMiddleware()
        tool = _SchemaTool()
        ctx = _make_context(tool=tool)

        async def _result():
            return "not json"

        result = await mw.process(ctx, _result)
        assert "Error" not in result
