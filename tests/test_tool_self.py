"""Tests for SelfTool — runtime state inspection and config."""
import json
import pytest
from unittest.mock import MagicMock

from open_agent.tools.self import SelfTool


class _FakeLoop:
    def __init__(self, max_iterations=10, staleness_rounds=3):
        self._max_iterations = max_iterations
        self._staleness_rounds = staleness_rounds
        self._tool_messages = []
        self._runtime_memory = MagicMock()
        self._runtime_memory.task_state = MagicMock()
        self._runtime_memory.task_state.current_step = 5


class TestSelfTool:
    def test_name_and_description(self):
        tool = SelfTool()
        assert tool.name == "self"
        assert tool.description

    def test_schema(self):
        tool = SelfTool()
        schema = tool.to_schema()
        assert schema["name"] == "self"
        assert "input_schema" in schema

    def test_safety_checks(self):
        tool = SelfTool()
        assert "config" in tool.safety_checks
        assert tool.read_only is False

    @pytest.mark.asyncio
    async def test_status(self):
        loop = _FakeLoop()
        tool = SelfTool(react_loop=loop)
        result = await tool.execute(action="status")
        data = json.loads(result)
        assert data["step_count"] == 5
        assert data["max_iterations"] == 10
        assert data["tools_used"] == []
        assert data["staleness_rounds"] == 3

    @pytest.mark.asyncio
    async def test_status_no_loop(self):
        tool = SelfTool()
        result = await tool.execute(action="status")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_config_max_iterations(self):
        loop = _FakeLoop()
        tool = SelfTool(react_loop=loop)
        result = await tool.execute(action="get_config", key="max_iterations")
        data = json.loads(result)
        assert data["value"] == 10

    @pytest.mark.asyncio
    async def test_get_config_staleness_rounds(self):
        loop = _FakeLoop()
        tool = SelfTool(react_loop=loop)
        result = await tool.execute(action="get_config", key="staleness_rounds")
        data = json.loads(result)
        assert data["value"] == 3

    @pytest.mark.asyncio
    async def test_get_config_unknown_key(self):
        loop = _FakeLoop()
        tool = SelfTool(react_loop=loop)
        result = await tool.execute(action="get_config", key="provider")
        assert "Whitelist" in result

    @pytest.mark.asyncio
    async def test_get_config_missing_key(self):
        tool = SelfTool()
        result = await tool.execute(action="get_config")
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_set_config_max_iterations(self):
        loop = _FakeLoop()
        tool = SelfTool(react_loop=loop)
        result = await tool.execute(action="set_config", key="max_iterations", value=20)
        data = json.loads(result)
        assert data["old_value"] == 10
        assert data["new_value"] == 20
        assert loop._max_iterations == 20

    @pytest.mark.asyncio
    async def test_set_config_staleness_rounds(self):
        loop = _FakeLoop()
        tool = SelfTool(react_loop=loop)
        result = await tool.execute(action="set_config", key="staleness_rounds", value=5)
        data = json.loads(result)
        assert data["old_value"] == 3
        assert data["new_value"] == 5
        assert loop._staleness_rounds == 5

    @pytest.mark.asyncio
    async def test_set_config_rejects_non_whitelisted(self):
        loop = _FakeLoop()
        tool = SelfTool(react_loop=loop)
        result = await tool.execute(action="set_config", key="provider", value="test")
        assert "Cannot modify" in result
        assert "Whitelist" in result

    @pytest.mark.asyncio
    async def test_set_config_rejects_negative(self):
        loop = _FakeLoop()
        tool = SelfTool(react_loop=loop)
        result = await tool.execute(action="set_config", key="max_iterations", value=-1)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_set_config_missing_value(self):
        tool = SelfTool()
        result = await tool.execute(action="set_config", key="max_iterations")
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = SelfTool()
        result = await tool.execute(action="unknown")
        assert "Unknown action" in result

    @pytest.mark.asyncio
    async def test_weak_reference(self):
        """Verify weak reference doesn't prevent garbage collection."""
        loop = _FakeLoop()
        tool = SelfTool(react_loop=loop)
        result = await tool.execute(action="get_config", key="max_iterations")
        assert "10" in result
        del loop
        result = await tool.execute(action="status")
        assert "not available" in result.lower()
