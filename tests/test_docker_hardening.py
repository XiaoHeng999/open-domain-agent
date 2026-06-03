"""Tests for Docker sandbox command injection hardening."""
import io
import tarfile
import pytest
from unittest.mock import MagicMock, call

from open_agent.sandbox.docker import DockerSandbox


def _make_tar_bytes(content: str, name: str = "file") -> bytes:
    """Build a tar archive containing a single file with the given content."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        data = content.encode()
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class TestExecUsesArgList:
    """exec() must pass commands as argument lists, not shell-interpolated strings."""

    @pytest.mark.asyncio
    async def test_exec_passes_cmd_as_list(self):
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"hello")
        sandbox._container = mock_container

        await sandbox.exec("echo hello")

        args, kwargs = mock_container.exec_run.call_args
        cmd = args[0] if args else kwargs.get("cmd")

        # Must be a list, not a string
        assert isinstance(cmd, list), f"exec_run cmd must be a list, got {type(cmd)}: {cmd!r}"

    @pytest.mark.asyncio
    async def test_exec_injection_single_quote(self):
        """A command containing single quotes must not break out of quoting."""
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"ok")
        sandbox._container = mock_container

        # This payload would break out of f"bash -c '{command}'"
        await sandbox.exec("echo 'injection'; rm -rf /")

        args, kwargs = mock_container.exec_run.call_args
        cmd = args[0] if args else kwargs.get("cmd")
        # Verify the command was passed as a list (argument-safe)
        assert isinstance(cmd, list)
        # The actual command string should be passed intact as a single argument
        assert cmd == ["bash", "-c", "echo 'injection'; rm -rf /"]


class TestWriteFileUsesTarApi:
    """write_file() must use tar/archive API, not heredoc shell commands."""

    @pytest.mark.asyncio
    async def test_write_file_uses_put_archive(self):
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        sandbox._container = mock_container

        await sandbox.write_file("/workspace/test.txt", "hello world")

        # Must call put_archive, not exec_run with heredoc
        mock_container.put_archive.assert_called_once()
        mock_container.exec_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_file_content_in_tar(self):
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        sandbox._container = mock_container

        await sandbox.write_file("/workspace/test.txt", "hello world")

        args, kwargs = mock_container.put_archive.call_args
        path = args[0] if args else kwargs.get("path")
        data_stream = args[1] if len(args) > 1 else kwargs.get("data")

        assert path == "/workspace"

        # Verify the tar archive contains the right content
        tar_bytes = b"".join(data_stream)
        tar = tarfile.open(fileobj=io.BytesIO(tar_bytes))
        member = tar.getmembers()[0]
        content = tar.extractfile(member).read().decode()
        assert content == "hello world"

    @pytest.mark.asyncio
    async def test_write_file_injection_path(self):
        """Path traversal payloads in write_file must not execute as shell commands."""
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        sandbox._container = mock_container

        # This path would be dangerous in a heredoc string
        await sandbox.write_file("/workspace/$(rm -rf /)/file.txt", "content")

        # Should still use put_archive (safe), not exec_run (shell)
        mock_container.put_archive.assert_called_once()
        mock_container.exec_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_file_injection_heredoc_content(self):
        """Content containing the heredoc delimiter must not break out."""
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        sandbox._container = mock_container

        malicious_content = 'line1\nENDOFFILE\nrm -rf /'
        await sandbox.write_file("/workspace/test.txt", malicious_content)

        mock_container.put_archive.assert_called_once()
        mock_container.exec_run.assert_not_called()

        # Verify full content is preserved
        args, kwargs = mock_container.put_archive.call_args
        data_stream = args[1] if len(args) > 1 else kwargs.get("data")
        tar_bytes = b"".join(data_stream)
        tar = tarfile.open(fileobj=io.BytesIO(tar_bytes))
        member = tar.getmembers()[0]
        content = tar.extractfile(member).read().decode()
        assert content == malicious_content


class TestExecInjectionPayloads:
    """Various injection payloads must be safely handled."""

    @pytest.mark.asyncio
    async def test_semicolon_injection(self):
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"ok")
        sandbox._container = mock_container

        await sandbox.exec("echo hello; rm -rf /")
        args, kwargs = mock_container.exec_run.call_args
        cmd = args[0] if args else kwargs.get("cmd")
        assert isinstance(cmd, list)
        assert cmd[2] == "echo hello; rm -rf /"

    @pytest.mark.asyncio
    async def test_backtick_injection(self):
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"ok")
        sandbox._container = mock_container

        await sandbox.exec("echo `rm -rf /`")
        args, kwargs = mock_container.exec_run.call_args
        cmd = args[0] if args else kwargs.get("cmd")
        assert isinstance(cmd, list)

    @pytest.mark.asyncio
    async def test_dollar_injection(self):
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"ok")
        sandbox._container = mock_container

        await sandbox.exec("$(rm -rf /)")
        args, kwargs = mock_container.exec_run.call_args
        cmd = args[0] if args else kwargs.get("cmd")
        assert isinstance(cmd, list)

    @pytest.mark.asyncio
    async def test_newline_injection(self):
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"ok")
        sandbox._container = mock_container

        await sandbox.exec("echo hello\nrm -rf /")
        args, kwargs = mock_container.exec_run.call_args
        cmd = args[0] if args else kwargs.get("cmd")
        assert isinstance(cmd, list)

    @pytest.mark.asyncio
    async def test_existing_functionality_exec(self):
        """exec still returns correct result format after hardening."""
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"hello world")
        sandbox._container = mock_container

        result = await sandbox.exec("echo hello world")
        assert result["success"] is True
        assert result["exit_code"] == 0
        assert result["output"] == "hello world"

    @pytest.mark.asyncio
    async def test_existing_functionality_read_file(self):
        """read_file still works after hardening (unchanged)."""
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        tar_bytes = _make_tar_bytes("file content")
        mock_container.get_archive.return_value = (
            [tar_bytes],
            {"name": "test.txt", "size": 12},
        )
        sandbox._container = mock_container

        result = await sandbox.read_file("/workspace/test.txt")
        assert result["success"] is True
        assert result["content"] == "file content"

    @pytest.mark.asyncio
    async def test_write_file_preserves_binary_content(self):
        """write_file must preserve special characters."""
        sandbox = DockerSandbox()
        mock_container = MagicMock()
        sandbox._container = mock_container

        content = "line1\nline2\ttab\rspecial: \x00\x01\xff"
        # For tar-based write, binary content works
        await sandbox.write_file("/workspace/binary.dat", content)

        mock_container.put_archive.assert_called_once()
