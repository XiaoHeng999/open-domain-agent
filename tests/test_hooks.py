"""Tests for the hook system: HookManager, built-in hooks, and recovery integration."""

from __future__ import annotations

import asyncio
import logging
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent.errors import ParameterError, RetrievalError, ServiceError, ToolError
from open_agent.hooks import HookEvent, HookManager, HookResult
from open_agent.hooks.builtin import (
    _HELLO_LUCKY_ART,
    _WELCOME_TEXT,
    audit_hook,
    pre_check_hook,
    welcome_hook,
)
from open_agent.agent.react import Action, Observation, ReActLoop


# ===========================================================================
# 6.1 — HookManager register / fire / blocked / priority ordering
# ===========================================================================


class TestHookManager:
    """HookManager core behaviour."""

    def test_default_values(self):
        mgr = HookManager()
        assert mgr.enabled is True

    def test_fire_returns_empty_when_disabled(self):
        mgr = HookManager(enabled=False)
        mgr.register(HookEvent.TOOL_BEFORE, lambda ctx: HookResult(content="x"))
        results = asyncio.get_event_loop().run_until_complete(
            mgr.fire(HookEvent.TOOL_BEFORE, {}),
        )
        assert results == []

    def test_fire_returns_empty_when_no_hooks(self):
        mgr = HookManager()
        results = asyncio.get_event_loop().run_until_complete(
            mgr.fire(HookEvent.TOOL_BEFORE, {}),
        )
        assert results == []

    def test_register_and_fire(self):
        mgr = HookManager()
        mgr.register(HookEvent.TOOL_AFTER, lambda ctx: HookResult(content="ok"))
        results = asyncio.get_event_loop().run_until_complete(
            mgr.fire(HookEvent.TOOL_AFTER, {}),
        )
        assert len(results) == 1
        assert results[0].content == "ok"

    def test_priority_ordering(self):
        """Lower priority numbers execute first."""
        order: list[str] = []

        def hook_a(ctx):
            order.append("A")
            return HookResult(content="a")

        def hook_b(ctx):
            order.append("B")
            return HookResult(content="b")

        mgr = HookManager()
        mgr.register(HookEvent.TOOL_BEFORE, hook_a, priority=10)
        mgr.register(HookEvent.TOOL_BEFORE, hook_b, priority=5)

        asyncio.get_event_loop().run_until_complete(
            mgr.fire(HookEvent.TOOL_BEFORE, {}),
        )
        assert order == ["B", "A"]

    def test_same_priority_preserves_registration_order(self):
        order: list[str] = []

        def hook_a(ctx):
            order.append("A")
            return HookResult()

        def hook_b(ctx):
            order.append("B")
            return HookResult()

        mgr = HookManager()
        mgr.register(HookEvent.TOOL_BEFORE, hook_a, priority=10)
        mgr.register(HookEvent.TOOL_BEFORE, hook_b, priority=10)

        asyncio.get_event_loop().run_until_complete(
            mgr.fire(HookEvent.TOOL_BEFORE, {}),
        )
        assert order == ["A", "B"]

    def test_tool_before_blocked_interrupts_chain(self):
        """When a TOOL_BEFORE hook returns blocked=True, subsequent hooks don't run."""
        called: list[str] = []

        def blocker(ctx):
            called.append("blocker")
            return HookResult(blocked=True, content="nope")

        def after(ctx):
            called.append("after")
            return HookResult(content="should not run")

        mgr = HookManager()
        mgr.register(HookEvent.TOOL_BEFORE, blocker, priority=5)
        mgr.register(HookEvent.TOOL_BEFORE, after, priority=10)

        results = asyncio.get_event_loop().run_until_complete(
            mgr.fire(HookEvent.TOOL_BEFORE, {}),
        )
        assert len(results) == 1
        assert results[0].blocked is True
        assert called == ["blocker"]

    def test_fire_returns_all_results(self):
        mgr = HookManager()
        mgr.register(HookEvent.TOOL_AFTER, lambda ctx: HookResult(content="r1"))
        mgr.register(HookEvent.TOOL_AFTER, lambda ctx: HookResult(content="r2"))
        mgr.register(HookEvent.TOOL_AFTER, lambda ctx: HookResult(content="r3"))

        results = asyncio.get_event_loop().run_until_complete(
            mgr.fire(HookEvent.TOOL_AFTER, {}),
        )
        assert len(results) == 3

    def test_async_callback_support(self):
        async def async_hook(ctx):
            return HookResult(content="async_result")

        mgr = HookManager()
        mgr.register(HookEvent.TOOL_AFTER, async_hook)

        results = asyncio.get_event_loop().run_until_complete(
            mgr.fire(HookEvent.TOOL_AFTER, {}),
        )
        assert results[0].content == "async_result"


# ===========================================================================
# 6.2 — welcome_hook
# ===========================================================================


class TestWelcomeHook:
    def test_prints_banner_and_returns_text(self, capsys):
        result = welcome_hook({})
        assert result.content == _WELCOME_TEXT
        assert not result.blocked

        captured = capsys.readouterr()
        # ASCII art uses | and _ chars, not literal "HELLO"
        assert "___" in captured.out or "__" in captured.out
        assert len(captured.out.strip()) > 10

    def test_banner_is_ascii_art(self):
        assert "___" in _HELLO_LUCKY_ART or " _ " in _HELLO_LUCKY_ART


# ===========================================================================
# 6.3 — pre_check_hook
# ===========================================================================


class TestPreCheckHook:
    def test_allows_safe_command(self):
        result = pre_check_hook({"tool_name": "exec", "args": {"command": "ls -la"}})
        assert result.blocked is False

    def test_blocks_rm_rf(self):
        result = pre_check_hook({"tool_name": "exec", "args": {"command": "rm -rf /"}})
        assert result.blocked is True
        assert "dangerous command pattern" in result.content

    def test_ignores_non_exec_tool(self):
        result = pre_check_hook({"tool_name": "read_file", "args": {"command": "rm -rf /"}})
        assert result.blocked is False

    def test_blocks_reboot(self):
        result = pre_check_hook({"tool_name": "exec", "args": {"command": "reboot"}})
        assert result.blocked is True

    def test_blocks_mkfs(self):
        result = pre_check_hook({"tool_name": "exec", "args": {"command": "mkfs /dev/sda1"}})
        assert result.blocked is True


# ===========================================================================
# 6.4 — audit_hook
# ===========================================================================


class TestAuditHook:
    def test_logs_success(self, caplog):
        with caplog.at_level(logging.INFO, logger="open_agent.hooks"):
            result = audit_hook({
                "tool_name": "read_file",
                "success": True,
                "duration_ms": 15.0,
            })
        assert result.content is not None
        assert "read_file" in result.content
        assert "success=True" in result.content
        assert "15.0ms" in result.content
        assert any("[AUDIT]" in r.message for r in caplog.records)

    def test_logs_failure(self, caplog):
        with caplog.at_level(logging.INFO, logger="open_agent.hooks"):
            result = audit_hook({
                "tool_name": "exec",
                "success": False,
                "duration_ms": 42.5,
            })
        assert "success=False" in result.content
        assert any("[AUDIT]" in r.message for r in caplog.records)

    def test_metadata_populated(self):
        result = audit_hook({
            "tool_name": "read_file",
            "success": True,
            "duration_ms": 10.0,
        })
        assert result.metadata["tool_name"] == "read_file"
        assert result.metadata["success"] is True
        assert result.metadata["duration_ms"] == 10.0


# ===========================================================================
# 6.5 — Recovery integration in _execute_action
# ===========================================================================


class TestRecoveryIntegration:
    """Verify that ToolError in _execute_action triggers the recovery chain."""

    @pytest.mark.asyncio
    async def test_tool_error_triggers_recovery(self):
        """When a tool throws ToolError, recovery chain is invoked."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.get.return_value = MagicMock()

        error = ToolError("boom", tool_name="test_tool")
        registry.execute = AsyncMock(side_effect=error)

        loop = ReActLoop(tool_registry=registry)
        action = Action(tool_name="test_tool", args={}, step_index=0)

        # Mock recovery to return failure so we see the error content
        mock_result = MagicMock()
        mock_result.strategy_name = "ParameterRecoveryStrategy"
        mock_result.status.value = "failed"

        mock_trace = MagicMock()
        mock_trace.final_status.value = "escalate"
        mock_trace.attempts = [mock_result]

        with patch(
            "open_agent.recovery.execute_recovery_chain",
            new_callable=AsyncMock,
            return_value=mock_trace,
        ):
            obs = await loop._execute_action(action, 0, None)

        assert isinstance(obs, Observation)
        assert obs.success is False
        assert "Tool error" in obs.content
        assert "Recovery trace:" in obs.content

    @pytest.mark.asyncio
    async def test_non_tool_error_no_recovery(self):
        """Non-ToolError exceptions are handled without recovery chain."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.execute = AsyncMock(side_effect=RuntimeError("unexpected"))

        loop = ReActLoop(tool_registry=registry)
        action = Action(tool_name="test_tool", args={}, step_index=0)

        obs = await loop._execute_action(action, 0, None)
        assert obs.success is False
        assert "Execution error: unexpected" in obs.content

    @pytest.mark.asyncio
    async def test_recovery_success_replaces_error(self):
        """When recovery succeeds, the result replaces the error content."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.get.return_value = MagicMock()

        error = ParameterError("bad params", tool_name="test_tool")
        registry.execute = AsyncMock(side_effect=error)

        loop = ReActLoop(tool_registry=registry)
        action = Action(tool_name="test_tool", args={}, step_index=0)

        # Mock the recovery chain to return success
        mock_result = MagicMock()
        mock_result.status.value = "success"
        mock_result.data = {"result": "recovered!"}
        mock_result.message = "ok"

        mock_trace = MagicMock()
        mock_trace.final_status.value = "success"
        mock_trace.attempts = [mock_result]

        with patch(
            "open_agent.recovery.execute_recovery_chain",
            new_callable=AsyncMock,
            return_value=mock_trace,
        ):
            obs = await loop._execute_action(action, 0, None)

        assert obs.success is True
        assert "recovered!" in obs.content

    @pytest.mark.asyncio
    async def test_recovery_failure_appends_trace(self):
        """When recovery fails, trace summary is appended to error message."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.get.return_value = MagicMock()

        error = RetrievalError("not found", tool_name="search")
        registry.execute = AsyncMock(side_effect=error)

        loop = ReActLoop(tool_registry=registry)
        action = Action(tool_name="search", args={}, step_index=0)

        mock_result = MagicMock()
        mock_result.strategy_name = "RetrievalRecoveryStrategy"
        mock_result.status.value = "failed"

        mock_trace = MagicMock()
        mock_trace.final_status.value = "escalate"
        mock_trace.attempts = [mock_result]

        with patch(
            "open_agent.recovery.execute_recovery_chain",
            new_callable=AsyncMock,
            return_value=mock_trace,
        ):
            obs = await loop._execute_action(action, 0, None)

        assert obs.success is False
        assert "Tool error: not found" in obs.content
        assert "Recovery trace:" in obs.content

    @pytest.mark.asyncio
    async def test_hook_before_blocks_execution(self):
        """TOOL_BEFORE hook returning blocked=True prevents tool execution."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.execute = AsyncMock(return_value="should not run")

        mgr = HookManager()
        mgr.register(
            HookEvent.TOOL_BEFORE,
            lambda ctx: HookResult(blocked=True, content="Blocked!"),
        )

        loop = ReActLoop(tool_registry=registry, hook_manager=mgr)
        action = Action(tool_name="exec", args={"command": "ls"}, step_index=0)

        obs = await loop._execute_action(action, 0, None)
        assert obs.success is False
        assert "Blocked!" in obs.content
        registry.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_hook_after_injects_content(self):
        """TOOL_AFTER hook content is appended to observation."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.execute = AsyncMock(return_value="result data")

        mgr = HookManager()
        mgr.register(
            HookEvent.TOOL_AFTER,
            lambda ctx: HookResult(content="[AUDIT] tool=exec ok"),
        )

        loop = ReActLoop(tool_registry=registry, hook_manager=mgr)
        action = Action(tool_name="exec", args={"command": "ls"}, step_index=0)

        obs = await loop._execute_action(action, 0, None)
        assert obs.success is True
        assert "result data" in obs.content
        assert "[AUDIT] tool=exec ok" in obs.content

    @pytest.mark.asyncio
    async def test_no_hook_manager_behaves_unchanged(self):
        """Without a HookManager, behavior is identical to before."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.execute = AsyncMock(return_value="hello")

        loop = ReActLoop(tool_registry=registry)
        action = Action(tool_name="test_tool", args={}, step_index=0)

        obs = await loop._execute_action(action, 0, None)
        assert obs.success is True
        assert obs.content == "hello"


# ===========================================================================
# HookResult default values
# ===========================================================================


class TestHookResultDefaults:
    def test_defaults(self):
        r = HookResult()
        assert r.content is None
        assert r.blocked is False
        assert r.metadata == {}

    def test_custom_values(self):
        r = HookResult(content="msg", blocked=True, metadata={"k": 1})
        assert r.content == "msg"
        assert r.blocked is True
        assert r.metadata == {"k": 1}


# ===========================================================================
# HookEvent enum
# ===========================================================================


class TestHookEvent:
    def test_has_all_members(self):
        members = set(HookEvent)
        assert members == {
            HookEvent.SESSION_START,
            HookEvent.TOOL_BEFORE,
            HookEvent.TOOL_AFTER,
        }


# ===========================================================================
# TOOL_AFTER blocking — HookManager + ReAct integration
# ===========================================================================


class TestToolAfterBlocked:
    """Tests for TOOL_AFTER blocked=True interrupting the chain."""

    def test_tool_after_blocked_interrupts_chain(self):
        """TOOL_AFTER hook returning blocked=True stops subsequent hooks."""
        called: list[str] = []

        def blocker(ctx):
            called.append("blocker")
            return HookResult(blocked=True, content="quality check failed")

        def should_not_run(ctx):
            called.append("should_not_run")
            return HookResult(content="should not appear")

        mgr = HookManager()
        mgr.register(HookEvent.TOOL_AFTER, blocker, priority=5)
        mgr.register(HookEvent.TOOL_AFTER, should_not_run, priority=10)

        results = asyncio.get_event_loop().run_until_complete(
            mgr.fire(HookEvent.TOOL_AFTER, {}),
        )
        assert len(results) == 1
        assert results[0].blocked is True
        assert called == ["blocker"]

    @pytest.mark.asyncio
    async def test_tool_after_blocked_rejects_result(self):
        """TOOL_AFTER blocked=True in ReAct loop sets success=False."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.get.return_value = MagicMock()
        registry.execute = AsyncMock(return_value="result data")

        mgr = HookManager()
        mgr.register(
            HookEvent.TOOL_AFTER,
            lambda ctx: HookResult(blocked=True, content="Blocked: empty search result"),
        )

        loop = ReActLoop(tool_registry=registry, hook_manager=mgr)
        action = Action(tool_name="web_search", args={"query": "test"}, step_index=0)

        mock_trace = MagicMock()
        mock_trace.final_status.value = "escalate"
        mock_trace.attempts = []

        with patch(
            "open_agent.recovery.execute_recovery_chain",
            new_callable=AsyncMock,
            return_value=mock_trace,
        ):
            obs = await loop._execute_action(action, 0, None)

        assert obs.success is False
        assert "Blocked: empty search result" in obs.content

    @pytest.mark.asyncio
    async def test_tool_after_blocked_triggers_recovery(self):
        """TOOL_AFTER blocked=True triggers recovery and uses recovered result on success."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.get.return_value = MagicMock()
        registry.execute = AsyncMock(return_value="bad result")

        mgr = HookManager()
        mgr.register(
            HookEvent.TOOL_AFTER,
            lambda ctx: HookResult(blocked=True, content="quality check failed"),
        )

        loop = ReActLoop(tool_registry=registry, hook_manager=mgr)
        action = Action(tool_name="search", args={"pattern": "test"}, step_index=0)

        mock_result = MagicMock()
        mock_result.status.value = "success"
        mock_result.data = {"result": "recovered result"}
        mock_result.message = "ok"

        mock_trace = MagicMock()
        mock_trace.final_status.value = "success"
        mock_trace.attempts = [mock_result]

        with patch(
            "open_agent.recovery.execute_recovery_chain",
            new_callable=AsyncMock,
            return_value=mock_trace,
        ):
            obs = await loop._execute_action(action, 0, None)

        assert obs.success is True
        assert "recovered result" in obs.content

    @pytest.mark.asyncio
    async def test_tool_after_not_blocked_passes_through(self):
        """TOOL_AFTER with blocked=False works normally."""
        registry = MagicMock()
        registry.has.return_value = True
        registry.execute = AsyncMock(return_value="result data")

        mgr = HookManager()
        mgr.register(
            HookEvent.TOOL_AFTER,
            lambda ctx: HookResult(content="[AUDIT] ok"),
        )

        loop = ReActLoop(tool_registry=registry, hook_manager=mgr)
        action = Action(tool_name="exec", args={"command": "ls"}, step_index=0)

        obs = await loop._execute_action(action, 0, None)
        assert obs.success is True
        assert "result data" in obs.content
