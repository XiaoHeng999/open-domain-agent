"""Shell execution tool — async subprocess with timeout and output truncation."""
from __future__ import annotations

import asyncio
from typing import Any

from open_agent.tools.base import Tool


class ExecTool(Tool):
    """Execute shell commands via async subprocess or sandbox."""

    def __init__(
        self,
        workspace: str = ".",
        timeout: int = 30,
        max_output_chars: int = 10000,
        sandbox: Any = None,
    ) -> None:
        self._workspace = workspace
        self._timeout = timeout
        self._max_output_chars = max_output_chars
        self._sandbox = sandbox

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
            },
            "required": ["command"],
        }

    @property
    def safety_checks(self) -> list[str]:
        return ["command"]

    async def execute(self, **kwargs: Any) -> str:
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", self._timeout)

        if self._sandbox is not None:
            return await self._exec_via_sandbox(command, timeout)
        return await self._exec_via_subprocess(command, timeout)

    async def _exec_via_sandbox(self, command: str, timeout: int) -> str:
        """Execute via sandbox instance."""
        try:
            result = await self._sandbox.exec(command, timeout=timeout)
        except Exception as exc:
            return f"Error: Sandbox execution failed: {exc}"

        if not result.get("success", False):
            error = result.get("error", "unknown error")
            exit_code = result.get("exit_code")
            if exit_code is not None:
                output = result.get("output", "")
                return f"Error (exit code {exit_code}): {output or error}"
            return f"Error: {error}"

        output = result.get("output", "")
        stderr = result.get("error", "")
        if stderr:
            output += f"\n[stderr]: {stderr}"

        return self._truncate(output)

    async def _exec_via_subprocess(self, command: str, timeout: int) -> str:
        """Execute via asyncio subprocess on host."""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._workspace,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: Command timed out after {timeout}s"

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            output = f"Error (exit code {proc.returncode}): {stderr_str or stdout_str}"
        else:
            output = stdout_str
            if stderr_str:
                output += f"\n[stderr]: {stderr_str}"

        return self._truncate(output)

    def _truncate(self, output: str) -> str:
        if len(output) > self._max_output_chars:
            return output[:self._max_output_chars] + f"\n...[truncated, {len(output)} chars total]"
        return output
