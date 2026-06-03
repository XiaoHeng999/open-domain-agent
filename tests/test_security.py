"""Tests for security & sandbox modules."""

from __future__ import annotations

import pytest

from open_agent.config import SafetyConfig
from open_agent.safety import SafetyManager
from open_agent.safety.command import CommandSafetyChecker
from open_agent.safety.hitl import HITLApprovalManager, HITLLevel
from open_agent.safety.ssrf import SSRFProtector
from open_agent.safety.workspace import PathRestrictor
from open_agent.sandbox.factory import SandboxFactory, SubprocessSandbox
from open_agent.config import SandboxConfig


class TestCommandSafety:
    def test_safe_command(self):
        checker = CommandSafetyChecker()
        assert checker.check("ls -la").safe
        assert checker.check("echo hello").safe
        assert checker.check("python3 script.py").safe

    def test_blocked_rm_rf(self):
        checker = CommandSafetyChecker()
        result = checker.check("rm -rf /")
        assert not result.safe
        assert result.matched_pattern is not None

    def test_blocked_fork_bomb(self):
        checker = CommandSafetyChecker()
        result = checker.check(":(){ :|:& };:")
        assert not result.safe

    def test_blocked_mkfs(self):
        checker = CommandSafetyChecker()
        assert not checker.check("mkfs /dev/sda1").safe

    def test_blocked_dd(self):
        checker = CommandSafetyChecker()
        assert not checker.check("dd if=/dev/zero of=/dev/sda").safe

    def test_blocked_shutdown(self):
        checker = CommandSafetyChecker()
        assert not checker.check("shutdown -h now").safe

    def test_whitelist_mode(self):
        checker = CommandSafetyChecker(whitelist_mode=True)
        assert checker.check("ls -la").safe
        assert not checker.check("curl http://example.com").safe

    def test_empty_command(self):
        checker = CommandSafetyChecker()
        assert checker.check("").safe
        assert checker.check("  ").safe


class TestSSRFProtection:
    def test_block_localhost(self):
        protector = SSRFProtector()
        assert not protector.check_url("http://127.0.0.1/admin").safe
        assert not protector.check_url("http://localhost/secret").safe

    def test_block_private_ip(self):
        protector = SSRFProtector()
        assert not protector.check_url("http://10.0.0.1/api").safe
        assert not protector.check_url("http://192.168.1.1/router").safe
        assert not protector.check_url("http://172.16.0.1/internal").safe

    def test_block_cloud_metadata(self):
        protector = SSRFProtector()
        assert not protector.check_url("http://169.254.169.254/latest/meta-data/").safe

    def test_block_private_domain(self):
        protector = SSRFProtector()
        assert not protector.check_url("http://myapp.local/api").safe
        assert not protector.check_url("http://db.internal/query").safe

    def test_allow_public_url(self):
        protector = SSRFProtector()
        assert protector.check_url("https://api.example.com/v1/data").safe
        assert protector.check_url("https://github.com/repo").safe

    def test_dns_rebinding_check(self):
        protector = SSRFProtector()
        result = protector.check_resolved_ip("127.0.0.1", "evil.com")
        assert not result.safe
        assert "DNS rebinding" in result.reason

    def test_ip_check(self):
        protector = SSRFProtector()
        assert not protector.check_ip("10.0.0.1").safe
        assert not protector.check_ip("192.168.1.1").safe
        assert protector.check_ip("8.8.8.8").safe


class TestWorkspacePath:
    def test_allow_workspace_path(self, tmp_path):
        restrictor = PathRestrictor(workspace=str(tmp_path))
        assert restrictor.check_path(str(tmp_path / "file.txt")).safe

    def test_block_path_traversal(self, tmp_path):
        restrictor = PathRestrictor(workspace=str(tmp_path))
        result = restrictor.check_path(str(tmp_path / ".." / "etc" / "passwd"))
        assert not result.safe

    def test_block_outside_workspace(self, tmp_path):
        restrictor = PathRestrictor(workspace=str(tmp_path))
        assert not restrictor.check_path("/etc/passwd").safe

    def test_block_sensitive_file(self, tmp_path):
        restrictor = PathRestrictor(workspace=str(tmp_path))
        assert not restrictor.check_path(str(tmp_path / ".env")).safe
        assert not restrictor.check_path(str(tmp_path / "credentials.json")).safe
        assert not restrictor.check_path(str(tmp_path / "secret.key")).safe

    def test_trusted_paths(self, tmp_path):
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        restrictor = PathRestrictor(
            workspace=str(tmp_path),
            trusted_paths=[str(other_dir)],
        )
        assert restrictor.check_path(str(other_dir / "file.txt")).safe


class TestHITL:
    @pytest.mark.asyncio
    async def test_read_auto_approved(self):
        hitl = HITLApprovalManager(interactive=False)
        result = await hitl.approve("read_file", {"path": "/tmp/test.txt"})
        assert result.approved
        assert result.approved_by == "auto"
        assert result.level == HITLLevel.READ

    @pytest.mark.asyncio
    async def test_write_needs_approval(self):
        hitl = HITLApprovalManager(interactive=False)
        result = await hitl.approve("write_file", {"path": "/tmp/test.txt"})
        assert not result.approved  # non-interactive rejects
        assert result.level == HITLLevel.WRITE

    @pytest.mark.asyncio
    async def test_dangerous_blocked(self):
        hitl = HITLApprovalManager(interactive=False)
        result = await hitl.approve("delete_file", {"path": "/tmp/test.txt"})
        assert not result.approved
        assert result.level == HITLLevel.DANGEROUS

    def test_classify_levels(self):
        hitl = HITLApprovalManager()
        assert hitl.classify_operation("read_file") == HITLLevel.READ
        assert hitl.classify_operation("write_file") == HITLLevel.WRITE
        assert hitl.classify_operation("delete_file") == HITLLevel.DANGEROUS

    @pytest.mark.asyncio
    async def test_trust_escalation(self):
        hitl = HITLApprovalManager(trust_threshold=2, interactive=False)
        hitl._interactive = True
        hitl._ask_human = lambda s, op="", dt=None, **kwargs: True  # type: ignore

        r1 = await hitl.approve("write_file", {"path": "/tmp/a"})
        assert r1.approved
        r2 = await hitl.approve("write_file", {"path": "/tmp/b"})
        assert r2.approved

        # After threshold, should auto-approve
        assert hitl._trust_escalated
        r3 = await hitl.approve("write_file", {"path": "/tmp/c"})
        assert r3.approved
        assert r3.approved_by == "auto"

    @pytest.mark.asyncio
    async def test_whitelist_path(self):
        hitl = HITLApprovalManager(interactive=False, whitelist_paths=["/tmp/safe"])
        result = await hitl.approve("write_file", {"path": "/tmp/safe"})
        assert result.approved


class TestSafetyManager:
    def test_strict_blocks_dangerous(self):
        mgr = SafetyManager(SafetyConfig(safety_level="strict"))
        assert not mgr.check_command("rm -rf /").safe
        assert not mgr.check_url("http://127.0.0.1/").safe

    def test_off_allows_all(self):
        mgr = SafetyManager(SafetyConfig(safety_level="off"))
        assert mgr.check_command("rm -rf /").safe
        assert mgr.check_url("http://127.0.0.1/").safe

    @pytest.mark.asyncio
    async def test_permissive_allows_write(self):
        mgr = SafetyManager(SafetyConfig(safety_level="permissive"))
        result = await mgr.approve_operation("write_file", {"path": "/tmp/test"})
        assert result.approved


class TestSandboxFactory:
    def test_create_subprocess(self):
        sandbox = SandboxFactory.create(SandboxConfig(backend="subprocess"))
        assert isinstance(sandbox, SubprocessSandbox)

    @pytest.mark.asyncio
    async def test_subprocess_exec(self):
        sandbox = SubprocessSandbox()
        result = await sandbox.exec("echo hello")
        assert result["success"]
        assert "hello" in result["output"]

    @pytest.mark.asyncio
    async def test_subprocess_file_ops(self, tmp_path):
        sandbox = SubprocessSandbox()
        test_file = tmp_path / "test.txt"

        write_result = await sandbox.write_file(str(test_file), "hello world")
        assert write_result["success"]

        read_result = await sandbox.read_file(str(test_file))
        assert read_result["success"]
        assert read_result["content"] == "hello world"
