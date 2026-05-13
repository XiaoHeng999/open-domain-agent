"""Search tool — code search via ripgrep (grep) and file pattern matching (glob)."""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from open_agent.tools.base import Tool

_MAX_RESULTS = 100


class SearchTool(Tool):
    """Code search tool providing grep (via ripgrep) and glob file matching."""

    def __init__(self, workspace: str = ".") -> None:
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search code: grep file contents via ripgrep or match file names by glob pattern."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["grep", "glob"],
                    "description": "Search action: grep for content search, glob for file name matching",
                },
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex for grep, glob for file names)",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (relative to workspace)",
                },
                "file_type": {
                    "type": "string",
                    "description": "File extension filter for grep (e.g. 'py', 'js')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 100)",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
            "required": ["action", "pattern"],
        }

    @property
    def read_only(self) -> bool:
        return True

    @property
    def safety_checks(self) -> list[str]:
        return ["path"]

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        if action == "grep":
            return await self._grep(kwargs)
        if action == "glob":
            return await self._glob(kwargs)
        return f"Error: Unknown action: {action}"

    async def _grep(self, kwargs: dict[str, Any]) -> str:
        pattern = kwargs.get("pattern", "")
        if not pattern:
            return "Error: pattern is required for grep"

        if not shutil.which("rg"):
            return (
                "Error: ripgrep (rg) is not installed. "
                "Install it with: apt-get install ripgrep / brew install ripgrep"
            )

        search_path = kwargs.get("path", ".")
        file_type = kwargs.get("file_type")
        max_results = min(kwargs.get("max_results", _MAX_RESULTS), _MAX_RESULTS)

        args: list[str] = ["--line-number", "--no-heading"]
        if file_type:
            args.extend(["--type-add", f"custom:*.{file_type}", "--type", "custom"])
        args.extend(["--", pattern, search_path])

        try:
            proc = await asyncio.create_subprocess_exec(
                "rg", *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._workspace,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            return "Error: grep search timed out after 30s"

        if proc.returncode == 2:
            err = stderr.decode("utf-8", errors="replace").strip()
            return f"Error: ripgrep error: {err}"

        if proc.returncode == 1:
            return "No matches found."

        output = stdout.decode("utf-8", errors="replace")
        lines = output.strip().split("\n") if output.strip() else []
        if len(lines) > max_results:
            lines = lines[:max_results]
            lines.append(f"...[truncated, {len(output.strip().splitlines())} total matches]")

        return "\n".join(lines) if lines else "No matches found."

    async def _glob(self, kwargs: dict[str, Any]) -> str:
        pattern = kwargs.get("pattern", "")
        if not pattern:
            return "Error: pattern is required for glob"

        search_path = kwargs.get("path", ".")
        base = Path(self._workspace) / search_path

        if not base.exists():
            return f"Error: path does not exist: {search_path}"

        matches = sorted(str(p.relative_to(Path(self._workspace))) for p in base.glob(pattern) if p.is_file())

        if not matches:
            return "No files matched the pattern."

        return "\n".join(matches)
