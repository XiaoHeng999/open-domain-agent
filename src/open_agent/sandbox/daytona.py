"""Daytona sandbox integration — sandbox_exec / read / write / snapshot / restore."""

from __future__ import annotations

import asyncio
from typing import Any

from open_agent.base import BaseComponent
from open_agent.decorators import tool_schema


class DaytonaSandbox(BaseComponent):
    """Daytona sandbox — provides isolated execution environment."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.config = config or {}
        self._client = None
        self._workspace = None
        self.auto_timeout: int = self.config.get("auto_timeout", 300)

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
        try:
            effective_timeout = min(timeout, self.auto_timeout)

            def _daytona_exec():
                return self._workspace.process.execute(command, timeout=effective_timeout)

            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _daytona_exec),
                timeout=effective_timeout,
            )
            return {"success": True, "exit_code": result.exit_code, "output": result.output}
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Sandbox execution timed out after {effective_timeout}s")
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool_schema(name="sandbox_read_file")
    async def read_file(self, path: str) -> dict[str, Any]:
        """Read file from sandbox.
        Args:
            path: File path in sandbox
        """
        if not self._workspace:
            return {"success": False, "error": "Sandbox not started"}
        try:
            content = await asyncio.to_thread(self._workspace.fs.read_file, path)
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool_schema(name="sandbox_write_file")
    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write file to sandbox.
        Args:
            path: File path in sandbox
            content: File content to write
        """
        if not self._workspace:
            return {"success": False, "error": "Sandbox not started"}
        try:
            await asyncio.to_thread(self._workspace.fs.write_file, path, content)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool_schema(name="sandbox_snapshot")
    async def snapshot(self) -> dict[str, Any]:
        """Create sandbox snapshot for later restore."""
        if not self._workspace:
            return {"success": False, "error": "Sandbox not started"}
        try:
            snapshot_id = await asyncio.to_thread(self._workspace.create_snapshot)
            return {"success": True, "snapshot_id": snapshot_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool_schema(name="sandbox_restore")
    async def restore(self, snapshot_id: str) -> dict[str, Any]:
        """Restore sandbox to a previous snapshot.
        Args:
            snapshot_id: Snapshot ID to restore to
        """
        if not self._workspace:
            return {"success": False, "error": "Sandbox not started"}
        try:
            await asyncio.to_thread(self._workspace.restore_snapshot, snapshot_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
