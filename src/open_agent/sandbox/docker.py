"""Docker sandbox fallback — used when Daytona is unavailable."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from open_agent.base import BaseComponent
from open_agent.decorators import tool_schema

logger = logging.getLogger("open_agent.sandbox")


class DockerSandbox(BaseComponent):
    """Docker-based sandbox for isolated command execution."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.config = config or {}
        self._client = None
        self._container = None
        self._image = self.config.get("image", "python:3.11-slim")
        self._working_dir = self.config.get("working_dir", "/workspace")
        self.auto_timeout: int = self.config.get("auto_timeout", 300)

    async def on_start(self) -> None:
        try:
            import docker
            self._client = docker.from_env()
            self._container = self._client.containers.run(
                self._image,
                command="tail -f /dev/null",
                detach=True,
                tty=True,
                mem_limit=self.config.get("mem_limit", "512m"),
                network_mode=self.config.get("network_mode", "none"),
            )
        except ImportError:
            raise ImportError("Install docker: pip install docker")
        except Exception as e:
            raise RuntimeError(f"Failed to start Docker container: {e}")

    async def on_stop(self) -> None:
        if self._container:
            try:
                self._container.stop(timeout=5)
                self._container.remove()
            except Exception:
                pass

    @tool_schema(name="sandbox_exec")
    async def exec(self, command: str, timeout: int = 30) -> dict[str, Any]:
        if not self._container:
            return {"success": False, "error": "Sandbox not started"}
        try:
            effective_timeout = min(timeout, self.auto_timeout)

            def _docker_exec():
                exit_code, output = self._container.exec_run(cmd=["bash", "-c", command])
                return exit_code, output

            exit_code, output = await asyncio.wait_for(
                asyncio.to_thread(_docker_exec),
                timeout=effective_timeout,
            )
            return {"success": exit_code == 0, "exit_code": exit_code, "output": output.decode(errors="replace")}
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Sandbox execution timed out after {effective_timeout}s")
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool_schema(name="sandbox_read_file")
    async def read_file(self, path: str) -> dict[str, Any]:
        if not self._container:
            return {"success": False, "error": "Sandbox not started"}
        try:
            import tarfile
            import io

            def _read():
                bits, stat = self._container.get_archive(path)
                tar_stream = io.BytesIO(b"".join(bits))
                tar = tarfile.open(fileobj=tar_stream)
                member = tar.getmembers()[0]
                return tar.extractfile(member).read().decode()

            content = await asyncio.to_thread(_read)
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool_schema(name="sandbox_write_file")
    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        if not self._container:
            return {"success": False, "error": "Sandbox not started"}
        try:
            import tarfile
            import io as _io
            import os

            filename = os.path.basename(path)
            parent = os.path.dirname(path) or "/"

            buf = _io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                data = content.encode()
                info = tarfile.TarInfo(name=filename)
                info.size = len(data)
                tar.addfile(info, _io.BytesIO(data))
            buf.seek(0)

            await asyncio.to_thread(self._container.put_archive, parent, buf)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool_schema(name="sandbox_snapshot")
    async def snapshot(self) -> dict[str, Any]:
        if not self._container:
            return {"success": False, "error": "Sandbox not started"}
        try:
            image = await asyncio.to_thread(self._container.commit)
            return {"success": True, "snapshot_id": image.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool_schema(name="sandbox_restore")
    async def restore(self, snapshot_id: str) -> dict[str, Any]:
        if not self._client:
            return {"success": False, "error": "Docker client not initialized"}
        try:
            # Check snapshot exists
            try:
                await asyncio.to_thread(self._client.images.get, snapshot_id)
            except Exception:
                return {"success": False, "error": f"Snapshot {snapshot_id} not found"}

            # Stop old container
            old_container = self._container
            self._container = None

            if old_container:
                try:
                    await asyncio.to_thread(old_container.stop, timeout=5)
                    await asyncio.to_thread(old_container.remove)
                except Exception:
                    pass

            # Create new container from snapshot image
            try:
                self._container = await asyncio.to_thread(
                    self._client.containers.run,
                    snapshot_id,
                    command="tail -f /dev/null",
                    detach=True,
                    tty=True,
                    working_dir=self._working_dir,
                    mem_limit=self.config.get("mem_limit", "512m"),
                    network_mode=self.config.get("network_mode", "none"),
                )
            except Exception as e:
                return {"success": False, "error": f"Failed to create container from snapshot: {e}"}

            # Verify new container is working
            try:
                exit_code, output = await asyncio.to_thread(
                    self._container.exec_run, cmd="echo ok"
                )
                if exit_code != 0:
                    return {"success": False, "error": f"Container verification failed: {output.decode(errors='replace')}"}
            except Exception as e:
                return {"success": False, "error": f"Container verification failed: {e}"}

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"Docker restore failed: {e}"}
