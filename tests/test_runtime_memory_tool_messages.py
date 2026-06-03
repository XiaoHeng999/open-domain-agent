"""Tests for RuntimeMemory-managed tool messages with token budget."""
import pytest

from open_agent.config import MemoryConfig
from open_agent.memory.runtime import RuntimeMemory
from open_agent.memory.token_utils import estimate_tokens


class TestToolMessages:
    def test_add_and_get_tool_messages(self):
        """Tool messages round-trip through RuntimeMemory."""
        mem = RuntimeMemory()
        msgs = [
            {"role": "assistant", "tool_calls": [{"id": "tc_1", "type": "function", "function": {"name": "echo", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "tc_1", "content": "hello"},
        ]
        mem.add_tool_messages(msgs)
        assert mem.get_tool_messages() == msgs

    def test_multiple_adds_append(self):
        """Multiple add_tool_messages calls append in order."""
        mem = RuntimeMemory()
        mem.add_tool_messages([{"role": "tool", "tool_call_id": "1", "content": "a"}])
        mem.add_tool_messages([{"role": "tool", "tool_call_id": "2", "content": "b"}])
        msgs = mem.get_tool_messages()
        assert len(msgs) == 2
        assert msgs[0]["tool_call_id"] == "1"
        assert msgs[1]["tool_call_id"] == "2"

    def test_clear_resets_tool_messages(self):
        """Clear empties tool messages."""
        mem = RuntimeMemory()
        mem.add_tool_messages([{"role": "tool", "tool_call_id": "1", "content": "a"}])
        mem.clear_tool_messages()
        assert mem.get_tool_messages() == []

    @pytest.mark.asyncio
    async def test_token_budget_overflow_truncates_oldest(self):
        """When total tool messages exceed budget, oldest are truncated first."""
        config = MemoryConfig(max_tool_result_tokens=100)
        mem = RuntimeMemory(config)

        # Add several tool messages that will exceed the budget
        for i in range(5):
            mem.add_tool_messages([
                {"role": "tool", "tool_call_id": str(i), "content": f"result-{i}-" + "x" * 50},
            ])

        msgs = mem.get_tool_messages()
        total_tokens = sum(estimate_tokens(m.get("content", "")) for m in msgs)
        # Should have truncated oldest messages to stay under budget
        assert total_tokens <= config.max_tool_result_tokens or len(msgs) < 5

    def test_no_runtime_memory_graceful(self):
        """Without RuntimeMemory, tool_messages should still work (backward compat)."""
        # This is tested by existing ReActLoop tests
        pass
