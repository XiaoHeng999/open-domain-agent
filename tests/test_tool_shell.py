"""Tests for ExecTool — shell execution."""
import pytest

from open_agent.tools.shell import ExecTool


class TestExecTool:
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        tool = ExecTool()
        result = await tool.execute(command="echo hello")
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_nonzero_exit_code(self):
        tool = ExecTool()
        result = await tool.execute(command="ls /nonexistent_dir_xyz")
        assert "Error" in result
        assert "exit code" in result

    @pytest.mark.asyncio
    async def test_timeout(self):
        tool = ExecTool(timeout=1)
        result = await tool.execute(command="sleep 10")
        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_output_truncation(self):
        tool = ExecTool(max_output_chars=50)
        result = await tool.execute(command="python3 -c \"print('x' * 1000)\"")
        assert "[truncated" in result

    @pytest.mark.asyncio
    async def test_safety_checks(self):
        tool = ExecTool()
        assert "command" in tool.safety_checks

    @pytest.mark.asyncio
    async def test_working_directory(self, tmp_path):
        tool = ExecTool(workspace=str(tmp_path))
        result = await tool.execute(command="pwd")
        assert str(tmp_path) in result

    @pytest.mark.asyncio
    async def test_tool_schema_format(self):
        tool = ExecTool()
        schema = tool.to_schema()
        assert schema["name"] == "exec"
        assert "input_schema" in schema
