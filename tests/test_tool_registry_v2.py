"""Tests for ToolRegistry v2 — registration, execution pipeline, truncation, snapshot/restore."""
import pytest

from open_agent.tools.base import FunctionTool, Tool
from open_agent.registry import ToolRegistry


# -- Test fixtures --

class _AddTool(Tool):
    @property
    def name(self) -> str:
        return "add"

    @property
    def description(self) -> str:
        return "Add two numbers"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        }

    async def execute(self, **kwargs):
        return str(kwargs["a"] + kwargs["b"])


class _GreetTool(Tool):
    @property
    def name(self) -> str:
        return "greet"

    @property
    def description(self) -> str:
        return "Greet someone"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }

    async def execute(self, **kwargs):
        return f"Hello, {kwargs['name']}!"


class _VerboseTool(Tool):
    @property
    def name(self) -> str:
        return "verbose"

    @property
    def description(self) -> str:
        return "Returns a long string"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return "x" * 50000


# -- Registration tests --

class TestRegistration:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = _AddTool()
        reg.register(tool)
        assert reg.has("add")
        assert reg.get("add") is tool

    def test_duplicate_registration_raises(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_AddTool())

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        reg.unregister("add")
        assert not reg.has("add")

    def test_unregister_missing_raises(self):
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.unregister("nope")

    def test_list_tools(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        reg.register(_GreetTool())
        assert len(reg.list_tools()) == 2

    def test_len_and_contains(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        assert len(reg) == 1
        assert "add" in reg


# -- Execution pipeline tests --

class TestExecutePipeline:
    @pytest.mark.asyncio
    async def test_successful_execute(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        result = await reg.execute("add", {"a": 3, "b": 4})
        assert result == "7"

    @pytest.mark.asyncio
    async def test_cast_and_execute(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        result = await reg.execute("add", {"a": "3", "b": "4"})
        assert result == "7"

    @pytest.mark.asyncio
    async def test_validation_failure(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        result = await reg.execute("add", {"a": 3})
        assert "Validation failed" in result
        assert "b" in result

    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        reg = ToolRegistry()
        result = await reg.execute("missing", {})
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_greet_execute(self):
        reg = ToolRegistry()
        reg.register(_GreetTool())
        result = await reg.execute("greet", {"name": "World"})
        assert result == "Hello, World!"


# -- Truncation tests --

class TestTruncation:
    @pytest.mark.asyncio
    async def test_result_truncated(self):
        reg = ToolRegistry(max_tool_result_tokens=100)
        reg.register(_VerboseTool())
        result = await reg.execute("verbose", {})
        assert "[truncated" in result
        assert len(result) < 50000

    @pytest.mark.asyncio
    async def test_result_not_truncated_when_small(self):
        reg = ToolRegistry(max_tool_result_tokens=20000)
        reg.register(_VerboseTool())
        result = await reg.execute("verbose", {})
        assert "[truncated" not in result


# -- Snapshot / Restore tests --

class TestSnapshotRestore:
    def test_snapshot_and_restore(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        snap = reg.snapshot()
        reg.register(_GreetTool())
        assert len(reg) == 2
        reg.restore(snap)
        assert len(reg) == 1
        assert reg.has("add")
        assert not reg.has("greet")


# -- get_definitions tests --

class TestGetDefinitions:
    def test_returns_anthropic_format(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        defs = reg.get_definitions()
        assert len(defs) == 1
        d = defs[0]
        assert d["name"] == "add"
        assert "input_schema" in d
        assert d["input_schema"]["type"] == "object"

    def test_multiple_tools(self):
        reg = ToolRegistry()
        reg.register(_AddTool())
        reg.register(_GreetTool())
        defs = reg.get_definitions()
        assert len(defs) == 2
        names = {d["name"] for d in defs}
        assert names == {"add", "greet"}


# -- Safety integration tests --

class TestSafetyIntegration:
    @pytest.mark.asyncio
    async def test_command_blocked(self):
        class _SafetyManager:
            def check_command(self, cmd):
                from open_agent.safety.command import SafetyCheckResult
                if "rm -rf" in cmd:
                    return SafetyCheckResult(safe=False, reason="dangerous pattern")
                return SafetyCheckResult(safe=True)

        tool = FunctionTool(
            name="exec",
            description="Run command",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
            handler=lambda command: "ok",
            safety_checks=["command"],
        )
        reg = ToolRegistry(safety_manager=_SafetyManager())
        reg.register(tool)
        result = await reg.execute("exec", {"command": "rm -rf /"})
        assert "blocked" in result.lower() or "safety" in result.lower()
