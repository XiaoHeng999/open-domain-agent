"""Human-in-the-Loop tiered approval — Read auto / Write confirm / Dangerous block."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("open_agent.safety.hitl")

_MAX_PREVIEW_LEN = 100


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
    """Three-tier approval: Read(auto) -> Write(confirm) -> Dangerous(blocked).

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

    def approve(
        self,
        operation: str,
        details: dict[str, Any] | None = None,
        safety_risks: list[Any] | None = None,
    ) -> HITLResult:
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
            approved = self._ask_human(summary, operation, details, safety_risks=safety_risks)
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

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate_value(value: Any, max_len: int = _MAX_PREVIEW_LEN) -> str:
        """Truncate a value to max_len characters for display."""
        text = str(value)
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."

    @staticmethod
    def _format_approval_prompt(
        level: str,
        summary: str,
        operation: str,
        details: dict[str, Any] | None,
        safety_risks: list[Any] | None = None,
    ) -> str:
        """Build a structured approval prompt with risk level, target, and guidance."""
        # Extract key info
        target = ""
        detail_lines: list[str] = []
        if details:
            for key in ("path", "url", "command", "target"):
                val = details.get(key)
                if val is not None:
                    target = HITLApprovalManager._truncate_value(val)
                    break
            for k, v in (details or {}).items():
                detail_lines.append(f"  {k}={HITLApprovalManager._truncate_value(v)}")

        lines = [
            f"[bold yellow]\\[{level}][/bold yellow] Operation requires approval",
            f"  [dim]Operation:[/dim] {operation}",
        ]
        if target:
            lines.append(f"  [dim]Target:[/dim]    {target}")

        # Safety risk context
        if safety_risks:
            for risk in safety_risks:
                rule_info = risk.matched_pattern or risk.check_type
                lines.append(f"  [bold orange1]\\[SAFETY][/bold orange1] {risk.reason} (rule: {rule_info})")
                # Suggest alternatives based on check type
                if risk.check_type == "command":
                    lines.append(f"  [dim]Suggestion:[/dim] Consider using web_search or a safer alternative")

        lines.append("  [dim]Choose:[/dim]    [y] confirm / [n] reject / [d] view details")
        return "\n".join(lines)

    def _ask_human(
        self,
        summary: str,
        operation: str = "",
        details: dict[str, Any] | None = None,
        safety_risks: list[Any] | None = None,
    ) -> bool:
        """Interactive human confirmation via Rich CLI."""
        try:
            from rich.console import Console
            from rich.panel import Panel

            console = Console()
            level = self.classify_operation(operation, details).value.upper()
            prompt_text = self._format_approval_prompt(
                level, summary, operation, details, safety_risks=safety_risks,
            )
            console.print(Panel(prompt_text, border_style="yellow"))

            while True:
                response = console.input("[bold]Your choice [y/n/d]:[/bold] ").strip().lower()

                if response in ("y", "yes"):
                    return True
                if response in ("n", "no", ""):
                    return False
                if response in ("d", "detail", "details"):
                    console.print("[dim]--- Full operation details ---[/dim]")
                    console.print(f"  [dim]Operation:[/dim] {operation}")
                    if details:
                        for k, v in details.items():
                            console.print(f"  [dim]{k}:[/dim] {v}")
                    console.print("[dim]--- end details ---[/dim]")
                    continue
                console.print("[dim]Please enter y, n, or d.[/dim]")
        except Exception:
            logger.debug("HITL prompt failed, defaulting to deny", exc_info=True)
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
                parts.append(f"{key}={self._truncate_value(details[key])}")
        return " | ".join(parts)

    def reset_trust(self) -> None:
        self._write_approval_count = 0
        self._trust_escalated = False
