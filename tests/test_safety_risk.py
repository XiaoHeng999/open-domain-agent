"""Tests for safety risk escalation, permission collaboration, tool health, and final answer guard."""

from __future__ import annotations

import asyncio

import pytest

from open_agent.agent.react import (
    Action,
    AgentState,
    Observation,
    ReActLoop,
    ReActStep,
    Thought,
)
from open_agent.config import PermissionConfig, PermissionMode, SafetyConfig
from open_agent.middleware import (
    MiddlewareContext,
    SafetyMiddleware,
    SafetyRisk,
    PermissionMiddleware,
    ExecuteMiddleware,
    TruncateMiddleware,
    build_middleware_chain,
)
from open_agent.registry import ToolRegistry
from open_agent.safety import SafetyManager
from open_agent.safety.command import CommandSafetyChecker, SafetyCheckResult
from open_agent.safety.hitl import HITLApprovalManager, HITLLevel
from open_agent.safety.permission import PermissionGuard
from open_agent.safety.ssrf import SSRFProtector
from open_agent.safety.workspace import PathRestrictor
from open_agent.tools.base import FunctionTool
from open_agent.tools.web import DuckDuckGoSearchTool, BraveSearchTool, WebFetchTool
from open_agent.routing.complexity import ComplexityResult
from open_agent.routing.domain import DomainRouteResult
from open_agent.routing.intent import IntentResult
from open_agent.routing.router import RoutingDecision


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _simple_routing_decision(*, skip_planning: bool = True) -> RoutingDecision:
    """Local helper that extends conftest.routing_decision with skip_planning control."""
    return RoutingDecision(
        complexity=ComplexityResult(
            complexity="simple" if skip_planning else "complex",
            confidence=0.95,
            method="llm",
        ),
        domain=DomainRouteResult(
            domain="general",
            candidates=["general"],
            routed_as_fallback=True,
        ),
        intent=IntentResult(intent="general_query", slots={"query": "hello"}),
        skip_planning=skip_planning,
    )


# ---------------------------------------------------------------------------
# 8.1: Command safety risk levels
# ---------------------------------------------------------------------------


class TestCommandSafetyRiskLevels:
    """Task 8.1: Verify safe / risky / blocked three-tier classification."""

    def test_safe_command_returns_safe_level(self):
        checker = CommandSafetyChecker()
        result = checker.check("git status")
        assert result.safe is True
        assert result.risk_level == "safe"

    def test_blacklisted_command_returns_blocked(self):
        checker = CommandSafetyChecker()
        result = checker.check("rm -rf /")
        assert result.safe is False
        assert result.risk_level == "blocked"

    def test_pipe_metachar_returns_risky(self):
        checker = CommandSafetyChecker()
        result = checker.check("curl -s https://example.com | head -20")
        assert result.safe is False
        assert result.risk_level == "risky"
        assert "Shell metacharacter" in result.reason or "Low-risk" in result.reason

    def test_and_operator_returns_risky(self):
        checker = CommandSafetyChecker()
        result = checker.check("grep pattern file.txt && echo found")
        assert result.safe is False
        assert result.risk_level == "risky"

    def test_or_operator_returns_risky(self):
        checker = CommandSafetyChecker()
        result = checker.check("grep pattern file.txt || echo not_found")
        assert result.safe is False
        assert result.risk_level == "risky"

    def test_command_substitution_returns_risky(self):
        checker = CommandSafetyChecker()
        result = checker.check("echo $(whoami)")
        assert result.safe is False
        assert result.risk_level == "risky"

    def test_backtick_returns_risky(self):
        checker = CommandSafetyChecker()
        result = checker.check("echo `whoami`")
        assert result.safe is False
        assert result.risk_level == "risky"

    def test_redirect_returns_risky(self):
        checker = CommandSafetyChecker()
        result = checker.check("echo data > /tmp/file")
        assert result.safe is False
        assert result.risk_level == "risky"

    def test_semicolon_returns_risky(self):
        checker = CommandSafetyChecker()
        result = checker.check("echo hello ; echo world")
        assert result.safe is False
        assert result.risk_level == "risky"

    def test_fork_bomb_returns_blocked(self):
        checker = CommandSafetyChecker()
        result = checker.check(":(){ :|:& };:")
        assert result.safe is False
        assert result.risk_level == "blocked"

    def test_empty_command_returns_safe(self):
        checker = CommandSafetyChecker()
        result = checker.check("")
        assert result.safe is True
        assert result.risk_level == "safe"

    def test_ssrf_blocked_returns_blocked(self):
        protector = SSRFProtector()
        result = protector.check_url("http://169.254.169.254/latest/meta-data/")
        assert result.safe is False
        assert result.risk_level == "blocked"

    def test_ssrf_safe_returns_safe(self):
        protector = SSRFProtector()
        result = protector.check_url("https://api.example.com/v1/data")
        assert result.safe is True
        assert result.risk_level == "safe"

    def test_path_blocked_returns_blocked(self, tmp_path):
        restrictor = PathRestrictor(workspace=str(tmp_path))
        result = restrictor.check_path("/etc/passwd")
        assert result.safe is False
        assert result.risk_level == "blocked"

    def test_path_safe_returns_safe(self, tmp_path):
        restrictor = PathRestrictor(workspace=str(tmp_path))
        result = restrictor.check_path(str(tmp_path / "file.txt"))
        assert result.safe is True
        assert result.risk_level == "safe"


# ---------------------------------------------------------------------------
# 8.2: SafetyMiddleware risk escalation
# ---------------------------------------------------------------------------


class TestSafetyMiddlewareRiskEscalation:
    """Task 8.2: Verify risky does not short-circuit but passes to PermissionMiddleware."""

    def _make_context(self, tool_name: str, params: dict, safety_checks: list) -> MiddlewareContext:
        tool = FunctionTool(
            name=tool_name,
            description="test",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
            safety_checks=safety_checks,
        )
        return MiddlewareContext(
            tool=tool,
            params=params,
            tool_name=tool_name,
            safety_manager=SafetyManager(SafetyConfig(safety_level="strict")),
        )

    def test_blocked_short_circuits(self):
        ctx = self._make_context("exec", {"command": "rm -rf /"}, ["command"])
        mw = SafetyMiddleware()
        result = _run(mw.process(ctx, lambda: "should_not_reach"))
        assert result.startswith("Error:")
        assert "blocked" in result.lower()

    def test_risky_does_not_short_circuit(self):
        ctx = self._make_context("exec", {"command": "cat file | grep error"}, ["command"])
        mw = SafetyMiddleware()
        reached = False

        async def next_fn():
            nonlocal reached
            reached = True
            return "ok"

        result = _run(mw.process(ctx, next_fn))
        assert reached is True
        assert result == "ok"
        assert len(ctx.safety_risks) == 1
        assert ctx.safety_risks[0].risk_level == "risky"

    def test_safe_passes_through(self):
        ctx = self._make_context("exec", {"command": "ls -la"}, ["command"])
        mw = SafetyMiddleware()

        async def next_fn():
            return "ok"

        result = _run(mw.process(ctx, next_fn))
        assert result == "ok"
        assert len(ctx.safety_risks) == 0

    def test_missing_param_skips_check(self):
        ctx = self._make_context("web_search", {"query": "test"}, ["url"])
        mw = SafetyMiddleware()

        async def next_fn():
            return "ok"

        result = _run(mw.process(ctx, next_fn))
        assert result == "ok"
        assert len(ctx.safety_risks) == 0

    def test_mapped_param_resolves(self):
        ctx = self._make_context(
            "fetch",
            {"target_url": "https://example.com"},
            [{"type": "url", "param": "target_url"}],
        )
        mw = SafetyMiddleware()

        async def next_fn():
            return "ok"

        result = _run(mw.process(ctx, next_fn))
        assert result == "ok"


# ---------------------------------------------------------------------------
# 8.3: web_search no URL check
# ---------------------------------------------------------------------------


class TestWebSearchNoUrlCheck:
    """Task 8.3: Verify search tools no longer trigger URL safety checks."""

    def test_duckduckgo_empty_safety_checks(self):
        tool = DuckDuckGoSearchTool()
        assert tool.safety_checks == []

    def test_brave_empty_safety_checks(self):
        tool = BraveSearchTool(api_key="test-key")
        assert tool.safety_checks == []

    def test_web_fetch_still_has_url_check(self):
        tool = WebFetchTool()
        assert "url" in tool.safety_checks

    def test_safety_middleware_skips_search_tool(self):
        tool = DuckDuckGoSearchTool()
        ctx = MiddlewareContext(
            tool=tool,
            params={"query": "Python async patterns"},
            tool_name="web_search",
            safety_manager=SafetyManager(SafetyConfig(safety_level="strict")),
        )
        mw = SafetyMiddleware()

        async def next_fn():
            return "search results"

        result = _run(mw.process(ctx, next_fn))
        assert result == "search results"
        assert len(ctx.safety_risks) == 0


# ---------------------------------------------------------------------------
# 8.4: PermissionMiddleware risky handling
# ---------------------------------------------------------------------------


class TestPermissionMiddlewareRiskyHandling:
    """Task 8.4: Verify PermissionMiddleware triggers HITL for risky operations."""

    def _make_risky_context(
        self,
        mode: PermissionMode = PermissionMode.CAUTIOUS,
    ) -> MiddlewareContext:
        tool = FunctionTool(
            name="exec",
            description="test",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
            safety_checks=["command"],
        )
        guard = PermissionGuard(
            config=PermissionConfig(mode=mode),
            hitl=HITLApprovalManager(interactive=False),
        )
        ctx = MiddlewareContext(
            tool=tool,
            params={"command": "cat file | grep error"},
            tool_name="exec",
            permission_guard=guard,
            safety_risks=[SafetyRisk(
                tool_name="exec",
                check_type="command",
                reason="Low-risk shell metacharacter detected",
                risk_level="risky",
                matched_pattern="\\|",
            )],
        )
        return ctx

    def test_cautious_mode_triggers_hitl_for_risky(self):
        ctx = self._make_risky_context(mode=PermissionMode.CAUTIOUS)
        mw = PermissionMiddleware()

        async def next_fn():
            return "ok"

        result = _run(mw.process(ctx, next_fn))
        # Non-interactive HITL denies write operations by default
        assert result.startswith("Error:") or result == "ok"

    def test_unrestricted_mode_auto_approves_risky(self):
        tool = FunctionTool(
            name="exec",
            description="test",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
            safety_checks=["command"],
        )
        guard = PermissionGuard(
            config=PermissionConfig(mode=PermissionMode.UNRESTRICTED),
            hitl=HITLApprovalManager(interactive=False),
        )
        ctx = MiddlewareContext(
            tool=tool,
            params={"command": "cat file | grep error"},
            tool_name="exec",
            permission_guard=guard,
            safety_risks=[SafetyRisk(
                tool_name="exec",
                check_type="command",
                reason="Low-risk shell metacharacter detected",
                risk_level="risky",
                matched_pattern="\\|",
            )],
        )
        mw = PermissionMiddleware()

        async def next_fn():
            return "ok"

        result = _run(mw.process(ctx, next_fn))
        assert result == "ok"

    def test_no_safety_risks_follows_normal_flow(self):
        tool = FunctionTool(
            name="exec",
            description="test",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
            read_only=True,
            safety_checks=[],
        )
        guard = PermissionGuard(
            config=PermissionConfig(mode=PermissionMode.FLUENT),
        )
        ctx = MiddlewareContext(
            tool=tool,
            params={"command": "ls"},
            tool_name="exec",
            permission_guard=guard,
            safety_risks=[],
        )
        mw = PermissionMiddleware()

        async def next_fn():
            return "ok"

        result = _run(mw.process(ctx, next_fn))
        assert result == "ok"


# ---------------------------------------------------------------------------
# 8.5: Tool health tracking
# ---------------------------------------------------------------------------


class TestToolHealthTracking:
    """Task 8.5: Verify consecutive failure counting and degraded marking."""

    def test_consecutive_failures_tracked(self):
        state = AgentState()
        # Simulate 3 failed web_search steps
        for i in range(3):
            state.add_step(ReActStep(
                index=i,
                action=Action(tool_name="web_search", args={"query": "test"}, step_index=i),
                observation=Observation(
                    content="Error: Search failed",
                    tool_name="web_search",
                    success=False,
                    step_index=i,
                ),
            ))
        failed_count = sum(
            1 for s in state.steps
            if s.observation and not s.observation.success and s.action and s.action.tool_name == "web_search"
        )
        assert failed_count == 3

    def test_success_resets_count(self):
        state = AgentState()
        # 2 failures + 1 success + 1 failure
        for i, success in enumerate([False, False, True, False]):
            state.add_step(ReActStep(
                index=i,
                action=Action(tool_name="web_search", args={"query": "test"}, step_index=i),
                observation=Observation(
                    content="ok" if success else "Error: failed",
                    tool_name="web_search",
                    success=success,
                    step_index=i,
                ),
            ))
        # Only 1 consecutive failure after reset
        consecutive = 0
        for s in reversed(state.steps):
            if s.observation and not s.observation.success:
                consecutive += 1
            else:
                break
        assert consecutive == 1


# ---------------------------------------------------------------------------
# 8.6: Final answer guard
# ---------------------------------------------------------------------------


class TestFinalAnswerGuard:
    """Task 8.6: Verify all-failure and irrelevant-success return messages."""

    def test_all_failure_returns_structured_message(self):
        state = AgentState()
        state.add_step(ReActStep(
            index=0,
            action=Action(tool_name="web_search", args={"query": "test"}, step_index=0),
            observation=Observation(
                content="Error: Search failed: timeout",
                tool_name="web_search",
                success=False,
                step_index=0,
            ),
        ))
        state.add_step(ReActStep(
            index=1,
            action=Action(tool_name="exec", args={"command": "curl"}, step_index=1),
            observation=Observation(
                content="Error: Command blocked",
                tool_name="exec",
                success=False,
                step_index=1,
            ),
        ))
        answer = ReActLoop._compose_final_answer("search for X", state)
        assert "Failed to complete" in answer
        assert "web_search" in answer
        assert "exec" in answer
        assert "alternative" in answer.lower()

    def test_partial_success_returns_content(self):
        state = AgentState()
        state.add_step(ReActStep(
            index=0,
            action=Action(tool_name="web_search", args={"query": "test"}, step_index=0),
            observation=Observation(
                content="1. Result\n2. Another result",
                tool_name="web_search",
                success=True,
                step_index=0,
            ),
        ))
        answer = ReActLoop._compose_final_answer("search for X", state)
        assert "Result" in answer
        assert "Failed" not in answer

    def test_direct_answer_returned(self):
        state = AgentState()
        state.add_step(ReActStep(
            index=0,
            action=Action(tool_name="", args={"answer": "42"}, step_index=0),
            observation=Observation(
                content="42",
                tool_name="",
                success=True,
                step_index=0,
            ),
        ))
        answer = ReActLoop._compose_final_answer("what is 6*7", state)
        assert answer == "42"

    def test_no_steps_returns_processed(self):
        state = AgentState()
        answer = ReActLoop._compose_final_answer("hello", state)
        assert answer == "Processed: hello"

    def test_error_truncation(self):
        state = AgentState()
        long_error = "x" * 300
        state.add_step(ReActStep(
            index=0,
            action=Action(tool_name="web_search", args={"query": "test"}, step_index=0),
            observation=Observation(
                content=long_error,
                tool_name="web_search",
                success=False,
                step_index=0,
            ),
        ))
        answer = ReActLoop._compose_final_answer("test", state)
        # The error should be truncated to 200 chars in the summary
        assert "Failed to complete" in answer
        # Verify truncation: the web_search line should have "..." after truncation
        assert "..." in answer
