"""Daytona sandbox integration — sandbox_exec / read / write / snapshot / restore."""

from __future__ import annotations

from typing import Any

from open_agent.base import BaseComponent
from open_agent.decorators import tool_schema


class DaytonaSandbox(BaseComponent):
    """Daytona sandbox — provides isolated execution environment."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._client = None
        self._workspace = None

    async def on_start(self) -> None:
        try:
            from daytona_sdk import Daytona
            self._client = Daytona()
            self._workspace = self._client.create()
        except ImportError:
            raise ImportError("Install daytona-sdk: pip install daytona-sdk")

    async def on_stop(self) -> None:
        if self._workspace and self._client:
            try:
                self._client.remove(self._workspace)
            except Exception:
                pass

    @tool_schema(name="sandbox_exec")
    async def exec(self, command: str, timeout: int = 30) -> dict[str, Any]:
        """Execute command in sandbox.
        Args:
            command: Shell command to execute
            timeout: Execution timeout in seconds
        """
        if not self._workspace:
            return {"success": False, "error": "Sandbox not started"}
        result = self._workspace.process.execute(command, timeout=timeout)
        return {"success": True, "exit_code": result.exit_code, "output": result.output}

    @tool_schema(name="sandbox_read_file")
    async def read_file(self, path: str) -> dict[str, Any]:
        """Read file from sandbox.
        Args:
            path: File path in sandbox
        """
        if not self._workspace:
            return {"success": False, "error": "Sandbox not started"}
        content = self._workspace.fs.read_file(path)
        return {"success": True, "content": content}

    @tool_schema(name="sandbox_write_file")
    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write file to sandbox.
        Args:
            path: File path in sandbox
            content: File content to write
        """
        if not self._workspace:
            return {"success": False, "error": "Sandbox not started"}
        self._workspace.fs.write_file(path, content)
        return {"success": True}

    @tool_schema(name="sandbox_snapshot")
    async def snapshot(self) -> dict[str, Any]:
        """Create sandbox snapshot for later restore."""
        if not self._workspace:
            return {"success": False, "error": "Sandbox not started"}
        snapshot_id = self._workspace.create_snapshot()
        return {"success": True, "snapshot_id": snapshot_id}

    @tool_schema(name="sandbox_restore")
    async def restore(self, snapshot_id: str) -> dict[str, Any]:
        """Restore sandbox to a previous snapshot.
        Args:
            snapshot_id: Snapshot ID to restore to
        """
        if not self._workspace:
            return {"success": False, "error": "Sandbox not started"}
        self._workspace.restore_snapshot(snapshot_id)
        return {"success": True}
