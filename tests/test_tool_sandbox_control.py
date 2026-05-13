"""Tests for SandboxControlTool — sandbox lifecycle management."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from open_agent.tools.sandbox_control import SandboxControlTool


class _FakeSandbox:
    def __init__(self):
        self._started = False

    async def on_start(self):
        self._started = True

    async def exec(self, command, timeout=30):
        if command == "fail":
            return {"success": False, "error": "command failed", "exit_code": 1}
        return {"success": True, "output": f"ran: {command}", "exit_code": 0}

    async def snapshot(self):
        return {"success": True, "snapshot_id": "snap_001"}

    async def restore(self, snapshot_id):
        if snapshot_id == "bad":
            return {"success": False, "error": "snapshot not found"}
        return {"success": True, "restored_from": snapshot_id}


class TestSandboxControlTool:
    def test_name_and_description(self):
        tool = SandboxControlTool(sandbox=MagicMock())
        assert tool.name == "sandbox_control"
        assert tool.description

    def test_schema(self):
        tool = SandboxControlTool(sandbox=MagicMock())
        schema = tool.to_schema()
        assert schema["name"] == "sandbox_control"
        assert "input_schema" in schema

    def test_safety_checks(self):
        tool = SandboxControlTool(sandbox=MagicMock())
        assert "command" in tool.safety_checks
        assert tool.read_only is False

    @pytest.mark.asyncio
    async def test_start(self):
        sandbox = _FakeSandbox()
        tool = SandboxControlTool(sandbox=sandbox)
        result = await tool.execute(action="start")
        data = json.loads(result)
        assert data["status"] == "started"
        assert sandbox._started

    @pytest.mark.asyncio
    async def test_start_no_sandbox(self):
        tool = SandboxControlTool(sandbox=None)
        result = await tool.execute(action="start")
        assert "No sandbox" in result

    @pytest.mark.asyncio
    async def test_exec(self):
        sandbox = _FakeSandbox()
        tool = SandboxControlTool(sandbox=sandbox)
        result = await tool.execute(action="exec", command="echo hello")
        data = json.loads(result)
        assert data["success"] is True
        assert "echo hello" in data["output"]

    @pytest.mark.asyncio
    async def test_exec_failure(self):
        sandbox = _FakeSandbox()
        tool = SandboxControlTool(sandbox=sandbox)
        result = await tool.execute(action="exec", command="fail")
        data = json.loads(result)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_exec_missing_command(self):
        tool = SandboxControlTool(sandbox=_FakeSandbox())
        result = await tool.execute(action="exec")
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_snapshot(self):
        sandbox = _FakeSandbox()
        tool = SandboxControlTool(sandbox=sandbox)
        result = await tool.execute(action="snapshot")
        data = json.loads(result)
        assert data["success"] is True
        assert data["snapshot_id"] == "snap_001"

    @pytest.mark.asyncio
    async def test_restore(self):
        sandbox = _FakeSandbox()
        tool = SandboxControlTool(sandbox=sandbox)
        result = await tool.execute(action="restore", snapshot_id="snap_001")
        data = json.loads(result)
        assert data["success"] is True
        assert data["restored_from"] == "snap_001"

    @pytest.mark.asyncio
    async def test_restore_missing_snapshot_id(self):
        tool = SandboxControlTool(sandbox=_FakeSandbox())
        result = await tool.execute(action="restore")
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = SandboxControlTool(sandbox=MagicMock())
        result = await tool.execute(action="unknown")
        assert "Unknown action" in result
