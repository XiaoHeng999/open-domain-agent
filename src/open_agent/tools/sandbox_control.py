"""Sandbox control tool — expose sandbox lifecycle as an agent-callable tool."""
from __future__ import annotations

import json
from typing import Any

from open_agent.tools.base import Tool


class SandboxControlTool(Tool):
    """Control sandbox lifecycle: start, exec, snapshot, restore."""

    def __init__(self, sandbox: Any) -> None:
        self._sandbox = sandbox

    @property
    def name(self) -> str:
        return "sandbox_control"

    @property
    def description(self) -> str:
        return "Manage sandbox environments: start, execute commands, create/restore snapshots."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "exec", "snapshot", "restore"],
                    "description": "Sandbox action to perform",
                },
                "command": {
                    "type": "string",
                    "description": "Command to execute (for action='exec')",
                },
                "snapshot_id": {
                    "type": "string",
                    "description": "Snapshot ID to restore (for action='restore')",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default 30)",
                    "default": 30,
                },
            },
            "required": ["action"],
        }

    @property
    def read_only(self) -> bool:
        return False

    @property
    def safety_checks(self) -> list[str]:
        return ["command"]

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        if action == "start":
            return await self._start()
        if action == "exec":
            return await self._exec(kwargs)
        if action == "snapshot":
            return await self._snapshot()
        if action == "restore":
            return await self._restore(kwargs)
        return f"Error: Unknown action: {action}"

    async def _start(self) -> str:
        if self._sandbox is None:
            return "Error: No sandbox instance configured"
        try:
            if hasattr(self._sandbox, "on_start"):
                await self._sandbox.on_start()
            return json.dumps({"status": "started", "sandbox_type": type(self._sandbox).__name__})
        except Exception as exc:
            return f"Error: Failed to start sandbox: {exc}"

    async def _exec(self, kwargs: dict[str, Any]) -> str:
        command = kwargs.get("command", "")
        if not command:
            return "Error: command is required for exec action"
        if self._sandbox is None:
            return "Error: No sandbox instance configured"
        timeout = kwargs.get("timeout", 30)
        try:
            result = await self._sandbox.exec(command, timeout=timeout)
            return json.dumps(result)
        except Exception as exc:
            return f"Error: Sandbox exec failed: {exc}"

    async def _snapshot(self) -> str:
        if self._sandbox is None:
            return "Error: No sandbox instance configured"
        try:
            result = await self._sandbox.snapshot()
            return json.dumps(result)
        except Exception as exc:
            return f"Error: Snapshot failed: {exc}"

    async def _restore(self, kwargs: dict[str, Any]) -> str:
        snapshot_id = kwargs.get("snapshot_id", "")
        if not snapshot_id:
            return "Error: snapshot_id is required for restore action"
        if self._sandbox is None:
            return "Error: No sandbox instance configured"
        try:
            result = await self._sandbox.restore(snapshot_id)
            return json.dumps(result)
        except Exception as exc:
            return f"Error: Restore failed: {exc}"
