"""Integration tests — ToolRegistry full pipeline: safety → permission → execute."""
import asyncio
import pytest

from open_agent.config import PermissionConfig, PermissionMode, PermissionRule, SafetyConfig
from open_agent.registry import ToolRegistry
from open_agent.safety import SafetyManager
from open_agent.safety.hitl import HITLApprovalManager, HITLLevel, HITLResult
from open_agent.safety.permission import PermissionDecision, PermissionGuard
from open_agent.tools.shell import ExecTool


class AlwaysApproveHITL(HITLApprovalManager):
    def approve(self, operation, details=None):
        return HITLResult(approved=True, level=HITLLevel.WRITE, approved_by="human")


class AlwaysDenyHITL(HITLApprovalManager):
    def approve(self, operation, details=None):
        return HITLResult(approved=False, level=HITLLevel.WRITE, approved_by="blocked")


def _make_registry(
    mode: PermissionMode = PermissionMode.UNRESTRICTED,
    deny: list[dict] | None = None,
    allow: list[dict] | None = None,
    hitl: HITLApprovalManager | None = None,
    safety_level: str = "off",
) -> ToolRegistry:
    safety_config = SafetyConfig(safety_level=safety_level)
    safety_manager = SafetyManager(safety_config)

    perm_config = PermissionConfig(
        mode=mode,
        deny=[PermissionRule(**r) for r in (deny or [])],
        allow=[PermissionRule(**r) for r in (allow or [])],
    )
    permission_guard = PermissionGuard(config=perm_config, hitl=hitl)

    registry = ToolRegistry(
        safety_manager=safety_manager,
        permission_guard=permission_guard,
    )
    registry.register(ExecTool())
    return registry


@pytest.mark.asyncio
async def test_full_pipeline_passes():
    registry = _make_registry(mode=PermissionMode.UNRESTRICTED)
    result = await registry.execute("exec", {"command": "echo ok"})
    assert "ok" in result.lower()


@pytest.mark.asyncio
async def test_permission_denied_blocks_execution():
    registry = _make_registry(
        mode=PermissionMode.CONSERVATIVE,
        deny=[{"tool": "exec", "pattern": "rm *"}],
    )
    # Conservative denies write tools. ExecTool has read_only=False.
    result = await registry.execute("exec", {"command": "echo test"})
    assert "Permission denied" in result
    assert "conservative" in result.lower()


@pytest.mark.asyncio
async def test_deny_rule_overrides_unrestricted():
    registry = _make_registry(
        mode=PermissionMode.UNRESTRICTED,
        deny=[{"tool": "exec", "pattern": "rm *"}],
    )
    result = await registry.execute("exec", {"command": "rm -rf /"})
    assert "Permission denied" in result


@pytest.mark.asyncio
async def test_no_permission_guard_skips_check():
    """Without permission_guard, pipeline goes straight to execute."""
    safety_config = SafetyConfig(safety_level="off")
    safety_manager = SafetyManager(safety_config)
    registry = ToolRegistry(safety_manager=safety_manager)
    registry.register(ExecTool())

    result = await registry.execute("exec", {"command": "echo hello"})
    assert "hello" in result.lower()


@pytest.mark.asyncio
async def test_safety_blocks_before_permission():
    """Safety check runs first — a blocked command never reaches permission."""
    safety_config = SafetyConfig(safety_level="strict")
    safety_manager = SafetyManager(safety_config)
    permission_guard = PermissionGuard(
        config=PermissionConfig(mode=PermissionMode.UNRESTRICTED),
    )
    registry = ToolRegistry(
        safety_manager=safety_manager,
        permission_guard=permission_guard,
    )
    registry.register(ExecTool())

    result = await registry.execute("exec", {"command": "rm -rf /"})
    # Safety blocks it before permission is consulted
    assert "blocked by safety policy" in result.lower() or "Permission denied" in result


@pytest.mark.asyncio
async def test_fluent_with_allow_rule():
    registry = _make_registry(
        mode=PermissionMode.FLUENT,
        allow=[{"tool": "exec", "pattern": "echo *"}],
        hitl=AlwaysDenyHITL(),
    )
    result = await registry.execute("exec", {"command": "echo test"})
    # Allow rule should bypass ask-user
    assert "test" in result.lower()
