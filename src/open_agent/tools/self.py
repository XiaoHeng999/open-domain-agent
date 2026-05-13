"""Self tool — runtime state inspection and dynamic configuration."""
from __future__ import annotations

import json
import weakref
from typing import Any

from open_agent.tools.base import Tool

_CONFIG_WHITELIST = {"max_iterations", "staleness_rounds"}


class SelfTool(Tool):
    """Inspect and modify agent runtime state."""

    def __init__(
        self,
        react_loop: Any = None,
        runtime: Any = None,
    ) -> None:
        self._loop_ref = weakref.ref(react_loop) if react_loop else None
        self._runtime_ref = weakref.ref(runtime) if runtime else None

    @property
    def name(self) -> str:
        return "self"

    @property
    def description(self) -> str:
        return "Inspect agent runtime state (status, get_config) or modify whitelisted config (set_config)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "get_config", "set_config"],
                    "description": "Action to perform: status, get_config, or set_config",
                },
                "key": {
                    "type": "string",
                    "description": "Config key for get_config/set_config",
                },
                "value": {
                    "description": "New value for set_config (integer)",
                },
            },
            "required": ["action"],
        }

    @property
    def read_only(self) -> bool:
        return False

    @property
    def safety_checks(self) -> list[str]:
        return ["config"]

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        if action == "status":
            return self._status()
        if action == "get_config":
            return self._get_config(kwargs.get("key", ""))
        if action == "set_config":
            return self._set_config(kwargs.get("key", ""), kwargs.get("value"))
        return f"Error: Unknown action: {action}"

    def _get_loop(self) -> Any:
        if self._loop_ref is None:
            return None
        return self._loop_ref()

    def _status(self) -> str:
        loop = self._get_loop()
        if loop is None:
            return json.dumps({"error": "ReActLoop reference not available"})

        tools_used: list[str] = []
        for msg in getattr(loop, "_tool_messages", []):
            if msg.get("role") == "assistant":
                for block in msg.get("content", []):
                    if block.get("type") == "tool_use":
                        name = block.get("function", {}).get("name", "")
                        if name and name not in tools_used:
                            tools_used.append(name)
            elif "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    name = tc.get("function", {}).get("name", "")
                    if name and name not in tools_used:
                        tools_used.append(name)

        step_count = 0
        runtime_memory = getattr(loop, "_runtime_memory", None)
        if runtime_memory is not None:
            task_state = getattr(runtime_memory, "task_state", None)
            if task_state is not None:
                step_count = getattr(task_state, "current_step", 0)

        status = {
            "step_count": step_count,
            "max_iterations": getattr(loop, "_max_iterations", 0),
            "tools_used": tools_used,
            "staleness_rounds": getattr(loop, "_staleness_rounds", 0),
        }
        return json.dumps(status)

    def _get_config(self, key: str) -> str:
        if not key:
            return "Error: key is required for get_config"
        loop = self._get_loop()
        if loop is None:
            return "Error: ReActLoop reference not available"
        if key == "max_iterations":
            return json.dumps({"key": key, "value": getattr(loop, "_max_iterations", None)})
        if key == "staleness_rounds":
            return json.dumps({"key": key, "value": getattr(loop, "_staleness_rounds", None)})
        return f"Error: Unknown config key: {key}. Whitelist: {sorted(_CONFIG_WHITELIST)}"

    def _set_config(self, key: str, value: Any) -> str:
        if not key:
            return "Error: key is required for set_config"
        if value is None:
            return "Error: value is required for set_config"
        if key not in _CONFIG_WHITELIST:
            return f"Error: Cannot modify '{key}'. Whitelist: {sorted(_CONFIG_WHITELIST)}"

        loop = self._get_loop()
        if loop is None:
            return "Error: ReActLoop reference not available"

        if key == "max_iterations":
            if not isinstance(value, int) or value < 1:
                return "Error: max_iterations must be a positive integer"
            old = loop._max_iterations
            loop._max_iterations = value
            return json.dumps({"key": key, "old_value": old, "new_value": value})

        if key == "staleness_rounds":
            if not isinstance(value, int) or value < 0:
                return "Error: staleness_rounds must be a non-negative integer"
            old = loop._staleness_rounds
            loop._staleness_rounds = value
            return json.dumps({"key": key, "old_value": old, "new_value": value})

        return f"Error: Unknown config key: {key}"
