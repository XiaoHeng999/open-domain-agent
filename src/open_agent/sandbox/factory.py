"""SandboxFactory — config-driven sandbox selection."""

from __future__ import annotations

from typing import Any

from open_agent.base import BaseComponent
from open_agent.config import SandboxConfig


class SubprocessSandbox(BaseComponent):
    """Minimal sandbox using subprocess — no isolation, for development only."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.config = config or {}

    async def exec(self, command: str, timeout: int = 30) -> dict[str, Any]:
        import asyncio
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "output": stdout.decode(errors="replace"),
                "error": stderr.decode(errors="replace") if stderr else None,
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def read_file(self, path: str) -> dict[str, Any]:
        try:
            from pathlib import Path
            content = Path(path).read_text()
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        try:
            from pathlib import Path
            Path(path).write_text(content)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def snapshot(self) -> dict[str, Any]:
        return {"success": False, "error": "Subprocess sandbox does not support snapshots"}

    async def restore(self, snapshot_id: str) -> dict[str, Any]:
        return {"success": False, "error": "Subprocess sandbox does not support restore"}


class SandboxFactory:
    """Create sandbox instances based on config."""

    @staticmethod
    def create(config: SandboxConfig) -> BaseComponent:
        if config.backend == "daytona":
            from open_agent.sandbox.daytona import DaytonaSandbox
            return DaytonaSandbox()
        elif config.backend == "docker":
            from open_agent.sandbox.docker import DockerSandbox
            return DockerSandbox()
        else:
            return SubprocessSandbox()
