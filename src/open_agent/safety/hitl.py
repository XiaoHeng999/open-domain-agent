"""Human-in-the-Loop tiered approval — Read auto / Write confirm / Dangerous block."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HITLLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    DANGEROUS = "dangerous"


@dataclass
class HITLResult:
    """Result of a HITL approval check."""

    approved: bool
    level: HITLLevel
    approved_by: str  # "auto" | "human" | "blocked"
    operation_summary: str = ""
    reason: str = ""


class HITLApprovalManager:
    """Three-tier approval: Read(auto) → Write(confirm) → Dangerous(blocked).

    Supports session-level trust escalation: after N consecutive same-type
    approvals, auto-approve that category.
    """

    def __init__(
        self,
        trust_threshold: int = 5,
        interactive: bool = True,
        whitelist_paths: list[str] | None = None,
    ) -> None:
        self._trust_threshold = trust_threshold
        self._interactive = interactive
        self._whitelist_paths = set(whitelist_paths or [])
        self._write_approval_count: int = 0
        self._trust_escalated: bool = False

    def classify_operation(self, operation: str, details: dict[str, Any] | None = None) -> HITLLevel:
        """Classify an operation into a HITL level."""
        op_lower = operation.lower()

        dangerous_keywords = ["delete", "rm ", "drop ", "truncate", "format", "mkfs"]
        for kw in dangerous_keywords:
            if kw in op_lower:
                return HITLLevel.DANGEROUS

        write_keywords = ["write", "create", "update", "modify", "post", "put", "patch", "install", "config"]
        for kw in write_keywords:
            if kw in op_lower:
                return HITLLevel.WRITE

        return HITLLevel.READ

    def approve(self, operation: str, details: dict[str, Any] | None = None) -> HITLResult:
        """Check if an operation is approved based on its level."""
        level = self.classify_operation(operation, details)
        summary = self._build_summary(operation, details)

        if level == HITLLevel.READ:
            return HITLResult(
                approved=True,
                level=level,
                approved_by="auto",
                operation_summary=summary,
            )

        if level == HITLLevel.DANGEROUS:
            return HITLResult(
                approved=False,
                level=level,
                approved_by="blocked",
                operation_summary=summary,
                reason="Dangerous operation blocked by HITL policy",
            )

        # Write level
        if self._trust_escalated:
            return HITLResult(
                approved=True,
                level=level,
                approved_by="auto",
                operation_summary=summary,
                reason="Session trust escalated",
            )

        if self._is_whitelisted(operation, details):
            return HITLResult(
                approved=True,
                level=level,
                approved_by="auto",
                operation_summary=summary,
                reason="Whitelisted operation",
            )

        if self._interactive:
            approved = self._ask_human(summary)
        else:
            approved = False

        if approved:
            self._write_approval_count += 1
            if self._write_approval_count >= self._trust_threshold:
                self._trust_escalated = True

        return HITLResult(
            approved=approved,
            level=level,
            approved_by="human" if approved else "blocked",
            operation_summary=summary,
        )

    def _ask_human(self, summary: str) -> bool:
        """Interactive human confirmation via Rich CLI."""
        try:
            from rich.console import Console
            console = Console()
            console.print(f"\n[yellow]⚠ Write operation requires approval:[/yellow] {summary}")
            response = console.input("[bold]Approve? [y/N]:[/bold] ").strip().lower()
            return response in ("y", "yes")
        except Exception:
            return False

    def _is_whitelisted(self, operation: str, details: dict[str, Any] | None) -> bool:
        if not details:
            return False
        path = details.get("path", "")
        return path in self._whitelist_paths

    def _build_summary(self, operation: str, details: dict[str, Any] | None) -> str:
        if not details:
            return operation
        parts = [operation]
        for key in ("path", "url", "command", "target"):
            if key in details:
                parts.append(f"{key}={details[key]}")
        return " | ".join(parts)

    def reset_trust(self) -> None:
        self._write_approval_count = 0
        self._trust_escalated = False
