"""Tests for Docker sandbox restore functionality."""
import pytest
from unittest.mock import MagicMock, patch

from open_agent.sandbox.docker import DockerSandbox


class TestDockerSandboxRestore:
    @pytest.mark.asyncio
    async def test_restore_success(self):
        sandbox = DockerSandbox()

        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"ok")
        mock_client.images.get.return_value = MagicMock()  # snapshot exists

        new_container = MagicMock()
        new_container.exec_run.return_value = (0, b"ok")
        mock_client.containers.run.return_value = new_container

        sandbox._client = mock_client
        sandbox._container = mock_container

        result = await sandbox.restore("snap-001")

        assert result["success"] is True
        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once()
        mock_client.containers.run.assert_called_once_with(
            "snap-001",
            command="tail -f /dev/null",
            detach=True,
            tty=True,
            mem_limit="512m",
            network_mode="none",
            working_dir="/workspace",
        )

    @pytest.mark.asyncio
    async def test_restore_snapshot_not_found(self):
        sandbox = DockerSandbox()

        mock_client = MagicMock()
        mock_client.images.get.side_effect = Exception("image not found")
        mock_container = MagicMock()
        sandbox._client = mock_client
        sandbox._container = mock_container

        result = await sandbox.restore("nonexistent-snap")

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_restore_no_client(self):
        sandbox = DockerSandbox()
        sandbox._client = None

        result = await sandbox.restore("snap-001")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_restore_verifies_container(self):
        """After restore, exec echo ok to verify container is functional."""
        sandbox = DockerSandbox()

        mock_client = MagicMock()
        mock_client.images.get.return_value = MagicMock()

        # Verification fails
        new_container = MagicMock()
        new_container.exec_run.return_value = (1, b"error")
        mock_client.containers.run.return_value = new_container

        sandbox._client = mock_client
        sandbox._container = MagicMock()

        result = await sandbox.restore("snap-001")
        assert result["success"] is False
        assert "verification failed" in result["error"]
