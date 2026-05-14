"""Tests for sandbox auto_timeout enforcement."""
import asyncio
import pytest

from open_agent.sandbox.factory import SubprocessSandbox


class TestSubprocessSandboxAutoTimeout:
    @pytest.mark.asyncio
    async def test_normal_execution_not_affected(self):
        sandbox = SubprocessSandbox(config={"auto_timeout": 300})
        result = await sandbox.exec("echo hello", timeout=10)
        assert result["success"] is True
        assert "hello" in result["output"]

    @pytest.mark.asyncio
    async def test_timeout_triggers_asyncio_timeout_error(self):
        sandbox = SubprocessSandbox(config={"auto_timeout": 1})
        with pytest.raises(asyncio.TimeoutError, match="timed out"):
            await sandbox.exec("sleep 10", timeout=30)

    @pytest.mark.asyncio
    async def test_custom_auto_timeout(self):
        sandbox = SubprocessSandbox(config={"auto_timeout": 2})
        # Short sleep should succeed within 2s
        result = await sandbox.exec("echo ok", timeout=5)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_auto_timeout_overrides_longer_timeout(self):
        """When auto_timeout < timeout, auto_timeout wins."""
        sandbox = SubprocessSandbox(config={"auto_timeout": 1})
        with pytest.raises(asyncio.TimeoutError):
            await sandbox.exec("sleep 10", timeout=60)
