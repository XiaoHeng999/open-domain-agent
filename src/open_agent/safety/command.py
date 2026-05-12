"""Command safety checker — blacklist + regex pattern matching."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Dangerous shell metacharacters that can bypass whitelist
_DANGEROUS_METACHAR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r";"),           # command separator
    re.compile(r"\|"),          # pipe
    re.compile(r"&&"),          # AND operator
    re.compile(r"\|\|"),        # OR operator
    re.compile(r"\$\("),        # command substitution
    re.compile(r"`"),           # backtick substitution
    re.compile(r">"),           # redirect
    re.compile(r"<"),           # redirect input
]

# Dangerous command patterns
_BLACKLIST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/(\s|$)"),  # rm -rf /
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+.*of=/dev/"),
    re.compile(r":\(\)\{.*:\|:&.*\}"),  # fork bomb
    re.compile(r"\bchmod\s+777\s+/"),
    re.compile(r"\bchown\s+.*\s+/"),
    re.compile(r">\s*/dev/sd[a-z]"),  # write to block device
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\binit\s+[06]"),
    re.compile(r"\bformat\s+[A-Z]:"),
    re.compile(r"\bdel\s+/[sS]\s+/[qQ]"),  # Windows recursive delete
]

_WHITELIST_COMMANDS: set[str] = {
    "ls", "cat", "head", "tail", "grep", "find", "wc", "sort", "uniq",
    "echo", "pwd", "whoami", "date", "which", "env", "printenv",
    "git status", "git log", "git diff", "git branch",
    "python3", "pip",
}


@dataclass
class SafetyCheckResult:
    """Result of a command safety check."""

    safe: bool
    reason: str = ""
    matched_pattern: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"safe": self.safe, "reason": self.reason}


class CommandSafetyChecker:
    """Check shell commands against blacklist patterns and optional whitelist."""

    def __init__(
        self,
        extra_patterns: list[str] | None = None,
        whitelist_mode: bool = False,
    ) -> None:
        self._patterns = list(_BLACKLIST_PATTERNS)
        if extra_patterns:
            self._patterns.extend(re.compile(p) for p in extra_patterns)
        self._whitelist_mode = whitelist_mode

    def check(self, command: str) -> SafetyCheckResult:
        """Check if a command is safe to execute."""
        if not command.strip():
            return SafetyCheckResult(safe=True)

        # Check for dangerous shell metacharacters first (prevents whitelist bypass)
        for pattern in _DANGEROUS_METACHAR_PATTERNS:
            if pattern.search(command):
                return SafetyCheckResult(
                    safe=False,
                    reason=f"Dangerous shell metacharacter detected",
                    matched_pattern=pattern.pattern,
                )

        # Whitelist mode: only allow known-safe commands
        if self._whitelist_mode:
            cmd_prefix = command.strip().split()[0] if command.strip() else ""
            if cmd_prefix not in _WHITELIST_COMMANDS:
                return SafetyCheckResult(
                    safe=False,
                    reason=f"Command not in whitelist: {cmd_prefix}",
                    matched_pattern="whitelist",
                )
            return SafetyCheckResult(safe=True)

        # Blacklist mode: check against dangerous patterns
        for pattern in self._patterns:
            if pattern.search(command):
                return SafetyCheckResult(
                    safe=False,
                    reason=f"Dangerous command pattern matched",
                    matched_pattern=pattern.pattern,
                )

        return SafetyCheckResult(safe=True)
