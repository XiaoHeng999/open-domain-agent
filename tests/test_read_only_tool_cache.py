"""Tests for read-only tool result caching in ToolRegistry.execute."""
import pytest

from open_agent.memory.runtime import RuntimeMemory
from open_agent.registry import ToolRegistry
from open_agent.tools.base import FunctionTool, Tool


class _ReadOnlyTool(Tool):
    call_count = 0

    @property
    def name(self) -> str:
        return "ro"

    @property
    def description(self) -> str:
        return "Read-only tool"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs):
        self.call_count += 1
        return f"result-{kwargs['query']}-{self.call_count}"


class _WriteTool(Tool):
    call_count = 0

    @property
    def name(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return "Write tool"

    @property
    def read_only(self) -> bool:
        return False

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "data": {"type": "string"},
            },
            "required": ["data"],
        }

    async def execute(self, **kwargs):
        self.call_count += 1
        return f"wrote-{kwargs['data']}-{self.call_count}"


class TestReadOnlyCache:
    @pytest.mark.asyncio
    async def test_second_call_returns_cached_result(self):
        """Second call with same params returns cached result without re-executing."""
        mem = RuntimeMemory()
        reg = ToolRegistry(runtime_memory=mem)
        tool = _ReadOnlyTool()
        reg.register(tool)

        r1 = await reg.execute("ro", {"query": "a"})
        assert r1 == "result-a-1"

        r2 = await reg.execute("ro", {"query": "a"})
        assert r2 == "result-a-1"  # cached, not "result-a-2"
        assert tool.call_count == 1

    @pytest.mark.asyncio
    async def test_non_read_only_tools_not_cached(self):
        """Non-read-only tools always execute, never cached."""
        mem = RuntimeMemory()
        reg = ToolRegistry(runtime_memory=mem)
        tool = _WriteTool()
        reg.register(tool)

        r1 = await reg.execute("write", {"data": "x"})
        r2 = await reg.execute("write", {"data": "x"})
        assert r1 == "wrote-x-1"
        assert r2 == "wrote-x-2"
        assert tool.call_count == 2

    @pytest.mark.asyncio
    async def test_different_params_different_cache_keys(self):
        """Different parameter sets produce different cache keys."""
        mem = RuntimeMemory()
        reg = ToolRegistry(runtime_memory=mem)
        tool = _ReadOnlyTool()
        reg.register(tool)

        r1 = await reg.execute("ro", {"query": "a"})
        r2 = await reg.execute("ro", {"query": "b"})
        assert r1 == "result-a-1"
        assert r2 == "result-b-2"
        assert tool.call_count == 2

    @pytest.mark.asyncio
    async def test_no_runtime_memory_no_caching(self):
        """Without runtime_memory, no caching occurs."""
        reg = ToolRegistry()
        tool = _ReadOnlyTool()
        reg.register(tool)

        r1 = await reg.execute("ro", {"query": "a"})
        r2 = await reg.execute("ro", {"query": "a"})
        assert r1 == "result-a-1"
        assert r2 == "result-a-2"
        assert tool.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_populated_after_middleware(self):
        """Result is stored in cache after successful execution."""
        mem = RuntimeMemory()
        reg = ToolRegistry(runtime_memory=mem)
        tool = _ReadOnlyTool()
        reg.register(tool)

        await reg.execute("ro", {"query": "test"})

        # Verify cache was populated
        cached = mem.cache_get("ro", {"query": "test"})
        assert cached == "result-test-1"
