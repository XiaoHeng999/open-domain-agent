"""Tests for ExecTool sandbox injection — verify execution paths."""
import asyncio
import pytest

from open_agent.tools.shell import ExecTool


class MockSandbox:
    """Minimal mock sandbox matching the exec() interface."""

    def __init__(self, output: str = "mock output", success: bool = True,
                 exit_code: int = 0, error: str | None = None):
        self._output = output
        self._success = success
        self._exit_code = exit_code
        self._error = error
        self.last_command = None
        self.last_timeout = None

    async def exec(self, command: str, timeout: int = 30) -> dict:
        self.last_command = command
        self.last_timeout = timeout
        return {
            "success": self._success,
            "exit_code": self._exit_code,
            "output": self._output,
            "error": self._error,
        }


@pytest.mark.asyncio
async def test_exec_with_sandbox():
    sandbox = MockSandbox(output="hello from sandbox")
    tool = ExecTool(sandbox=sandbox)
    result = await tool.execute(command="echo hello")
    assert result == "hello from sandbox"
    assert sandbox.last_command == "echo hello"


@pytest.mark.asyncio
async def test_exec_without_sandbox():
    tool = ExecTool()
    result = await tool.execute(command="echo hello")
    assert "hello" in result.lower()


@pytest.mark.asyncio
async def test_sandbox_error_result():
    sandbox = MockSandbox(success=False, exit_code=1, error="permission denied")
    tool = ExecTool(sandbox=sandbox)
    result = await tool.execute(command="bad command")
    assert "Error (exit code 1)" in result


@pytest.mark.asyncio
async def test_sandbox_timeout():
    sandbox = MockSandbox(success=False, error="Command timed out after 5s")
    tool = ExecTool(sandbox=sandbox)
    result = await tool.execute(command="sleep 100", timeout=5)
    assert "Error" in result


@pytest.mark.asyncio
async def test_sandbox_exception():
    class FailingSandbox:
        async def exec(self, command, timeout=30):
            raise ConnectionError("sandbox unavailable")

    tool = ExecTool(sandbox=FailingSandbox())
    result = await tool.execute(command="echo test")
    assert "Sandbox execution failed" in result


@pytest.mark.asyncio
async def test_exec_subprocess_timeout():
    tool = ExecTool(timeout=1)
    result = await tool.execute(command="sleep 100", timeout=1)
    assert "timed out" in result.lower()


@pytest.mark.asyncio
async def test_exec_output_truncation():
    tool = ExecTool(sandbox=MockSandbox(output="x" * 15000), max_output_chars=100)
    result = await tool.execute(command="big output")
    assert len(result) < 200
    assert "truncated" in result.lower()
