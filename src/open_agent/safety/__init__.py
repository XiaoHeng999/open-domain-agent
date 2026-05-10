"""Safety module — unified security management with strict/permissive/off levels."""

from __future__ import annotations

from typing import Any

from open_agent.config import SafetyConfig
from open_agent.safety.command import CommandSafetyChecker, SafetyCheckResult
from open_agent.safety.hitl import HITLApprovalManager, HITLLevel, HITLResult
from open_agent.safety.ssrf import SSRFProtector
from open_agent.safety.workspace import PathRestrictor


class SafetyManager:
    """Unified security manager — orchestrates all safety checks."""

    def __init__(self, config: SafetyConfig, workspace: str = ".") -> None:
        self.config = config
        self.level = config.safety_level
        self.command_checker = CommandSafetyChecker()
        self.ssrf_protector = SSRFProtector()
        self.path_restrictor = PathRestrictor(
            workspace=workspace,
            sensitive_files=config.sensitive_files,
            trusted_paths=config.trusted_paths,
        )
        self.hitl = HITLApprovalManager(
            interactive=True,
            whitelist_paths=config.trusted_paths,
        )

    def check_command(self, command: str) -> SafetyCheckResult:
        if self.level == "off":
            return SafetyCheckResult(safe=True)
        return self.command_checker.check(command)

    def check_url(self, url: str) -> SafetyCheckResult:
        if self.level == "off":
            return SafetyCheckResult(safe=True)
        return self.ssrf_protector.check_url(url)

    def check_path(self, path: str, allow_write: bool = False) -> SafetyCheckResult:
        if self.level == "off":
            return SafetyCheckResult(safe=True)
        return self.path_restrictor.check_path(path, allow_write=allow_write)

    def approve_operation(self, operation: str, details: dict[str, Any] | None = None) -> HITLResult:
        if self.level == "off":
            return HITLResult(approved=True, level=HITLLevel.READ, approved_by="auto")
        if self.level == "permissive":
            result = self.hitl.approve(operation, details)
            if not result.approved and result.level != HITLLevel.DANGEROUS:
                return HITLResult(
                    approved=True,
                    level=result.level,
                    approved_by="auto",
                    operation_summary=result.operation_summary,
                    reason="Permissive mode auto-approve",
                )
            return result
        return self.hitl.approve(operation, details)
