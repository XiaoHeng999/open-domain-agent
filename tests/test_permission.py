"""Tests for PermissionGuard — deny/allow rules, mode decisions, HITL ask user."""
import pytest

from open_agent.config import PermissionConfig, PermissionMode, PermissionRule
from open_agent.safety.hitl import HITLApprovalManager, HITLLevel, HITLResult
from open_agent.safety.permission import PermissionDecision, PermissionGuard, PermissionResult


# ── Helpers ──

def _guard(
    mode: PermissionMode = PermissionMode.FLUENT,
    deny: list[dict] | None = None,
    allow: list[dict] | None = None,
    hitl: HITLApprovalManager | None = None,
) -> PermissionGuard:
    config = PermissionConfig(
        mode=mode,
        deny=[PermissionRule(**r) for r in (deny or [])],
        allow=[PermissionRule(**r) for r in (allow or [])],
    )
    return PermissionGuard(config=config, hitl=hitl)


class MockHITL(HITLApprovalManager):
    """HITL that returns a predetermined approval result."""

    def __init__(self, approved: bool = True):
        super().__init__(interactive=True)
        self._mock_approved = approved

    def approve(self, operation, details=None):
        return HITLResult(
            approved=self._mock_approved,
            level=HITLLevel.WRITE,
            approved_by="human",
        )


# ── Deny rule tests ──

class TestDenyRules:
    def test_deny_by_tool_pattern(self):
        guard = _guard(deny=[{"tool": "exec", "pattern": "rm -rf *"}])
        result = guard.check("exec", {"command": "rm -rf /"})
        assert result.decision == PermissionDecision.DENY
        assert "Denied by rule" in result.reason

    def test_deny_priority_over_allow(self):
        guard = _guard(
            deny=[{"tool": "exec", "pattern": "rm *"}],
            allow=[{"tool": "exec", "pattern": "rm *"}],
        )
        result = guard.check("exec", {"command": "rm something"})
        assert result.decision == PermissionDecision.DENY

    def test_deny_wildcard_tool(self):
        guard = _guard(deny=[{"tool": "*", "pattern": "rm -rf *"}])
        result = guard.check("exec", {"command": "rm -rf /"})
        assert result.decision == PermissionDecision.DENY

    def test_deny_path_glob(self):
        guard = _guard(deny=[{"tool": "read_file", "path": "./secrets/**"}])
        result = guard.check("read_file", {"path": "./secrets/credentials.json"})
        assert result.decision == PermissionDecision.DENY

    def test_deny_domain(self):
        guard = _guard(deny=[{"tool": "web_fetch", "domain": "169.254.169.254"}])
        result = guard.check("web_fetch", {"url": "http://169.254.169.254/latest/meta-data/"})
        assert result.decision == PermissionDecision.DENY

    def test_no_deny_match_passes(self):
        # Fluent mode, no deny match, no HITL → falls through to ask user → no HITL → deny
        guard = _guard(deny=[{"tool": "exec", "pattern": "rm *"}])
        result = guard.check("exec", {"command": "git status"})
        assert result.decision == PermissionDecision.DENY
        # Unrestricted mode bypasses mode check entirely
        guard2 = _guard(
            mode=PermissionMode.UNRESTRICTED,
            deny=[{"tool": "exec", "pattern": "rm *"}],
        )
        result2 = guard2.check("exec", {"command": "git status"})
        assert result2.decision == PermissionDecision.ALLOW


# ── Mode tests ──

class TestModes:
    def test_cautious_read_only_allowed(self):
        guard = _guard(mode=PermissionMode.CAUTIOUS)
        result = guard.check("read_file", {"path": "/tmp/test.txt"}, {"read_only": True})
        assert result.decision == PermissionDecision.ALLOW

    def test_cautious_write_defers_to_hitl(self):
        hitl = MockHITL(approved=True)
        guard = _guard(mode=PermissionMode.CAUTIOUS, hitl=hitl)
        result = guard.check("write_file", {"path": "/tmp/test.txt"}, {"read_only": False})
        assert result.decision == PermissionDecision.ALLOW
        assert "Approved by user" in result.reason

    def test_conservative_write_denied(self):
        guard = _guard(mode=PermissionMode.CONSERVATIVE)
        result = guard.check("write_file", {"path": "/tmp/test.txt"}, {"read_only": False})
        assert result.decision == PermissionDecision.DENY
        assert "conservative mode" in result.reason.lower()

    def test_conservative_read_allowed(self):
        guard = _guard(mode=PermissionMode.CONSERVATIVE)
        result = guard.check("read_file", {"path": "/tmp/test.txt"}, {"read_only": True})
        assert result.decision == PermissionDecision.ALLOW

    def test_fluent_allow_rule_bypasses_ask(self):
        guard = _guard(
            mode=PermissionMode.FLUENT,
            allow=[{"tool": "exec", "pattern": "pip install *"}],
        )
        result = guard.check("exec", {"command": "pip install requests"})
        assert result.decision == PermissionDecision.ALLOW
        assert "Allowed by rule" in result.reason

    def test_fluent_no_rule_hit_defers_to_ask(self):
        hitl = MockHITL(approved=False)
        guard = _guard(mode=PermissionMode.FLUENT, hitl=hitl)
        result = guard.check("exec", {"command": "curl http://example.com"})
        assert result.decision == PermissionDecision.DENY

    def test_unrestricted_allows_all(self):
        guard = _guard(mode=PermissionMode.UNRESTRICTED)
        result = guard.check("write_file", {"path": "/tmp/test.txt"}, {"read_only": False})
        assert result.decision == PermissionDecision.ALLOW


# ── HITL tests ──

class TestHITL:
    def test_user_approves(self):
        hitl = MockHITL(approved=True)
        guard = _guard(mode=PermissionMode.FLUENT, hitl=hitl)
        result = guard.check("exec", {"command": "some command"})
        assert result.decision == PermissionDecision.ALLOW

    def test_user_rejects(self):
        hitl = MockHITL(approved=False)
        guard = _guard(mode=PermissionMode.FLUENT, hitl=hitl)
        result = guard.check("exec", {"command": "some command"})
        assert result.decision == PermissionDecision.DENY

    def test_no_hitl_defaults_deny(self):
        guard = _guard(mode=PermissionMode.FLUENT)
        result = guard.check("exec", {"command": "some command"})
        assert result.decision == PermissionDecision.DENY
        assert "No HITL" in result.reason

    def test_non_interactive_hitl_defaults_deny(self):
        hitl = HITLApprovalManager(interactive=False)
        guard = _guard(mode=PermissionMode.FLUENT, hitl=hitl)
        # Use a write-level operation so HITL doesn't auto-approve as READ
        result = guard.check("write_file", {"path": "/tmp/test.txt", "content": "data"})
        assert result.decision == PermissionDecision.DENY


# ── Default config test ──

class TestDefaultConfig:
    def test_missing_permissions_uses_defaults(self):
        config = PermissionConfig()
        assert config.mode == PermissionMode.FLUENT
        assert config.deny == []
        assert config.allow == []
