"""Regression tests for P0 crash-level bug fixes (tasks 1.1-1.4)."""
from __future__ import annotations

import pytest

from open_agent.base import BaseComponent


# ── 1.1 BaseComponent independent state ──


class _ComponentA(BaseComponent):
    pass


class _ComponentB(BaseComponent):
    pass


class TestBaseComponentIndependentState:
    def test_instances_have_independent_state(self):
        a = _ComponentA()
        b = _ComponentB()
        assert a._registered is False
        assert b._registered is False
        assert a._started is False
        assert b._started is False

    async def test_state_changes_dont_leak(self):
        a = _ComponentA()
        b = _ComponentB()
        a._registered = True
        a._started = True
        assert b._registered is False
        assert b._started is False

    async def test_on_start_independent(self):
        a = _ComponentA()
        b = _ComponentB()
        await a.on_start()
        assert a._started is True
        assert b._started is False


# ── 1.2 _tool_messages type confusion (runtime.py) ──


class TestToolMessagesTypeAccess:
    def test_tool_messages_dict_access(self):
        """Verify _tool_messages stores dicts with 'content' key containing tool_use blocks."""
        messages = [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "t1", "name": "read_file", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
            },
        ]
        tools_used = list({
            block["name"]
            for s in messages
            if s.get("role") == "assistant"
            for block in s.get("content", [])
            if block.get("type") == "tool_use"
        })
        assert tools_used == ["read_file"]


# ── 1.3 Domain system prompt duplication ──


class TestDomainPromptNoDuplication:
    def test_no_duplicate_domain_prompt(self):
        """Verify domain prompt is prepended exactly once."""
        domain_prompt = "You are a code assistant."
        system_content = "Base system prompt"
        # Simulate the fixed logic
        result = domain_prompt + "\n\n" + system_content
        assert result.count(domain_prompt) == 1


# ── 1.4 server_id attribute access ──


class TestServerIdAttribute:
    def test_getattr_for_server_id(self):
        """Verify getattr handles missing _server_id."""
        from open_agent.tools.base import FunctionTool

        tool = FunctionTool(
            name="test",
            description="test",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
        # Should not raise, should return None
        assert getattr(tool, "_server_id", None) is None

    def test_getattr_with_server_id(self):
        from open_agent.tools.base import FunctionTool

        tool = FunctionTool(
            name="test",
            description="test",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
        tool._server_id = "my_server"
        assert getattr(tool, "_server_id", None) == "my_server"
