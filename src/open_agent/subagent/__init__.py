"""Subagent package — agent-as-a-tool implementation."""

from open_agent.subagent.types import SubagentPreset, SubagentResult
from open_agent.subagent.manager import SubagentManager
from open_agent.subagent.tool import SubagentTool

__all__ = ["SubagentTool", "SubagentManager", "SubagentPreset", "SubagentResult"]
