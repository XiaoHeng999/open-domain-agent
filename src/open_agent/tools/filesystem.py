"""Filesystem tools — read_file, write_file, edit_file, list_dir.

All tools are scoped to a workspace directory to prevent path traversal.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from open_agent.tools.base import Tool


def _resolve_path(path: str, workspace: str) -> Path:
    """Resolve path relative to workspace, raising on traversal."""
    workspace = os.path.abspath(workspace)
    resolved = os.path.abspath(os.path.join(workspace, path))
    if not resolved.startswith(workspace):
        raise ValueError(f"Path escapes workspace: {path}")
    return Path(resolved)


class ReadFileTool(Tool):
    """Read file contents, optionally with offset/limit for pagination."""

    def __init__(self, workspace: str = ".") -> None:
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file. Supports offset and limit for paginated reading."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file (relative to workspace)"},
                "offset": {"type": "integer", "description": "Line number to start reading from (0-based)"},
                "limit": {"type": "integer", "description": "Maximum number of lines to read"},
            },
            "required": ["path"],
        }

    @property
    def read_only(self) -> bool:
        return True

    @property
    def safety_checks(self) -> list[str]:
        return ["path"]

    async def execute(self, **kwargs: Any) -> str:
        path = kwargs.get("path", "")
        offset = kwargs.get("offset")
        limit = kwargs.get("limit")

        try:
            resolved = _resolve_path(path, self._workspace)
        except ValueError as e:
            return f"Error: {e}"

        if not resolved.is_file():
            return f"Error: File not found: {path}"

        try:
            lines = resolved.read_text(encoding="utf-8").splitlines()
            if offset is not None:
                lines = lines[offset:]
            if limit is not None:
                lines = lines[:limit]
            return "\n".join(lines)
        except Exception as e:
            return f"Error: Failed to read file: {e}"


class WriteFileTool(Tool):
    """Write content to a file, creating parent directories as needed."""

    def __init__(self, workspace: str = ".") -> None:
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates parent directories automatically."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file (relative to workspace)"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        }

    @property
    def safety_checks(self) -> list[str]:
        return ["path"]

    async def execute(self, **kwargs: Any) -> str:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")

        try:
            resolved = _resolve_path(path, self._workspace)
        except ValueError as e:
            return f"Error: {e}"

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error: Failed to write file: {e}"


class EditFileTool(Tool):
    """Edit a file by replacing an exact string match."""

    def __init__(self, workspace: str = ".") -> None:
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Edit a file by replacing an exact string. The old_string must be unique in the file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file (relative to workspace)"},
                "old_string": {"type": "string", "description": "Exact text to find and replace"},
                "new_string": {"type": "string", "description": "Text to replace with"},
            },
            "required": ["path", "old_string", "new_string"],
        }

    @property
    def safety_checks(self) -> list[str]:
        return ["path"]

    async def execute(self, **kwargs: Any) -> str:
        path = kwargs.get("path", "")
        old_string = kwargs.get("old_string", "")
        new_string = kwargs.get("new_string", "")

        try:
            resolved = _resolve_path(path, self._workspace)
        except ValueError as e:
            return f"Error: {e}"

        if not resolved.is_file():
            return f"Error: File not found: {path}"

        try:
            content = resolved.read_text(encoding="utf-8")
            count = content.count(old_string)
            if count == 0:
                return "Error: old_string not found in file"
            if count > 1:
                return f"Error: old_string matches {count} times. Provide more context to make it unique."
            content = content.replace(old_string, new_string)
            resolved.write_text(content, encoding="utf-8")
            return f"Successfully edited {path}"
        except Exception as e:
            return f"Error: Failed to edit file: {e}"


class ListDirTool(Tool):
    """List directory contents with type indicators."""

    def __init__(self, workspace: str = ".") -> None:
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List the contents of a directory with type indicators."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the directory (relative to workspace)"},
            },
            "required": ["path"],
        }

    @property
    def read_only(self) -> bool:
        return True

    @property
    def safety_checks(self) -> list[str]:
        return ["path"]

    async def execute(self, **kwargs: Any) -> str:
        path = kwargs.get("path", "")

        try:
            resolved = _resolve_path(path, self._workspace)
        except ValueError as e:
            return f"Error: {e}"

        if not resolved.is_dir():
            return f"Error: Directory not found: {path}"

        entries = sorted(resolved.iterdir())
        if not entries:
            return "(empty directory)"

        lines: list[str] = []
        for entry in entries:
            if entry.is_dir():
                lines.append(f"[DIR]  {entry.name}/")
            else:
                lines.append(f"[FILE] {entry.name}")
        return "\n".join(lines)
