"""Workspace path restriction — path traversal prevention + sensitive file protection."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from open_agent.safety.command import SafetyCheckResult


class PathRestrictor:
    """Restrict file operations to workspace boundary, block sensitive files."""

    def __init__(
        self,
        workspace: str | Path,
        sensitive_files: list[str] | None = None,
        trusted_paths: list[str] | None = None,
    ) -> None:
        self._workspace = Path(workspace).resolve()
        self._sensitive_patterns = sensitive_files or [
            ".env", "credentials.json", "credentials", "*.key", "*.pem",
            "*.p12", "*.pfx", "id_rsa", "id_ed25519", ".netrc", ".aws/credentials",
        ]
        self._trusted_paths = {Path(p).resolve() for p in (trusted_paths or [])}

    def check_path(self, path: str | Path, allow_write: bool = False) -> SafetyCheckResult:
        """Check if a path is within workspace and not sensitive."""
        try:
            resolved = Path(path).resolve()
        except Exception:
            return SafetyCheckResult(safe=False, reason=f"Invalid path: {path}")

        # Check path traversal
        if not self._is_within_workspace(resolved) and resolved not in self._trusted_paths:
            return SafetyCheckResult(
                safe=False,
                reason=f"Path outside workspace: {resolved} (workspace: {self._workspace})",
            )

        # Check sensitive file
        if self._is_sensitive(resolved):
            return SafetyCheckResult(
                safe=False,
                reason=f"Sensitive file protected: {resolved.name}",
            )

        return SafetyCheckResult(safe=True)

    def _is_within_workspace(self, path: Path) -> bool:
        try:
            path.relative_to(self._workspace)
            return True
        except ValueError:
            return False

    def _is_sensitive(self, path: Path) -> bool:
        name = path.name
        str_path = str(path)
        for pattern in self._sensitive_patterns:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(str_path, f"*/{pattern}"):
                return True
        return False
