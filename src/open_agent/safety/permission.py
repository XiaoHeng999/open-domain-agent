"""PermissionGuard — deny → mode → allow → ask user four-stage decision pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatch
from typing import Any

from open_agent.config import PermissionConfig, PermissionMode
from open_agent.safety.hitl import HITLApprovalManager


class PermissionDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class PermissionResult:
    """Result of a permission check."""

    decision: PermissionDecision
    reason: str = ""


class PermissionGuard:
    """Permission decision middleware — deny rules → mode → allow rules → ask user."""

    def __init__(
        self,
        config: PermissionConfig,
        hitl: HITLApprovalManager | None = None,
    ) -> None:
        self._mode = config.mode
        self._deny_rules = config.deny
        self._allow_rules = config.allow
        self._hitl = hitl

    def check(
        self,
        tool_name: str,
        params: dict[str, Any],
        tool_meta: dict[str, Any] | None = None,
    ) -> PermissionResult:
        """Run the four-stage permission pipeline.

        tool_meta can contain 'read_only' (bool) to indicate the tool's nature.
        """
        meta = tool_meta or {}
        read_only = meta.get("read_only", False)

        # Stage 1: Deny rules — if any match, immediately deny
        deny_reason = self._match_rules(self._deny_rules, tool_name, params)
        if deny_reason:
            return PermissionResult(
                decision=PermissionDecision.DENY,
                reason=f"Denied by rule: {deny_reason}",
            )

        # Stage 2: Mode-based decision
        mode_result = self._check_mode(read_only)
        if mode_result is not None:
            return mode_result

        # Stage 3: Allow rules — if any match, auto-allow
        allow_reason = self._match_rules(self._allow_rules, tool_name, params)
        if allow_reason:
            return PermissionResult(
                decision=PermissionDecision.ALLOW,
                reason=f"Allowed by rule: {allow_reason}",
            )

        # Stage 4: Ask user via HITL
        return self._ask_user(tool_name, params)

    @staticmethod
    def _safe_str(value: Any, field_name: str) -> str:
        """Convert param value to str, logging if coercion was needed."""
        if isinstance(value, str):
            return value
        import logging as _logging
        _logging.getLogger("open_agent.safety.permission").debug(
            "permission param type coercion: %s was %s, not str", field_name, type(value).__name__,
        )
        return str(value)

    def _match_rules(
        self,
        rules: list[Any],
        tool_name: str,
        params: dict[str, Any],
    ) -> str | None:
        """Check if any rule matches. Returns the matching rule description or None."""
        for rule in rules:
            if not fnmatch(tool_name, rule.tool):
                continue
            if rule.pattern is not None:
                command = self._safe_str(params.get("command", ""), "command")
                if not fnmatch(command, rule.pattern):
                    continue
            if rule.path is not None:
                path = self._safe_str(params.get("path", ""), "path")
                if not fnmatch(path, rule.path):
                    continue
            if rule.domain is not None:
                url = self._safe_str(params.get("url", ""), "url")
                if rule.domain not in url:
                    continue
            parts = [f"tool={rule.tool}"]
            if rule.pattern:
                parts.append(f"pattern={rule.pattern}")
            if rule.path:
                parts.append(f"path={rule.path}")
            if rule.domain:
                parts.append(f"domain={rule.domain}")
            return ", ".join(parts)
        return None

    def _check_mode(self, read_only: bool) -> PermissionResult | None:
        """Mode-based decision. Returns None if mode cannot decide (defer to later stages)."""
        if self._mode == PermissionMode.UNRESTRICTED:
            return PermissionResult(
                decision=PermissionDecision.ALLOW,
                reason="Unrestricted mode",
            )

        if self._mode == PermissionMode.CONSERVATIVE:
            if not read_only:
                return PermissionResult(
                    decision=PermissionDecision.DENY,
                    reason="Write blocked in conservative mode",
                )
            return PermissionResult(
                decision=PermissionDecision.ALLOW,
                reason="Read allowed in conservative mode",
            )

        if self._mode == PermissionMode.CAUTIOUS:
            if read_only:
                return PermissionResult(
                    decision=PermissionDecision.ALLOW,
                    reason="Read-only auto-allowed in cautious mode",
                )
            # Defer to allow rules then ask user
            return None

        # FLUENT mode: read-only auto-allowed, others defer to allow rules then ask
        if read_only:
            return PermissionResult(
                decision=PermissionDecision.ALLOW,
                reason="Read-only auto-allowed in fluent mode",
            )
        return None

    def _ask_user(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> PermissionResult:
        """Ask user via HITL approval manager. Defaults to deny in non-interactive mode."""
        if self._hitl is None:
            return PermissionResult(
                decision=PermissionDecision.DENY,
                reason="No HITL manager available, defaulting to deny",
            )

        operation = f"{tool_name}({', '.join(f'{k}={v!r}' for k, v in params.items())})"
        details = dict(params)
        hitl_result = self._hitl.approve(operation, details)

        if hitl_result.approved:
            return PermissionResult(
                decision=PermissionDecision.ALLOW,
                reason="Approved by user",
            )
        return PermissionResult(
            decision=PermissionDecision.DENY,
            reason=f"Rejected by user: {hitl_result.reason or 'user denied'}",
        )
