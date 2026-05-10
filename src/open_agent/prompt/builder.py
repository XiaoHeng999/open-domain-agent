"""PromptBuilder — assembles the full system prompt from segments."""

from __future__ import annotations

import logging
from typing import Any

from open_agent.prompt import prompt as _p
from open_agent.prompt.segments import (
    ClaudemdSegment,
    CoreIdentitySegment,
    DynamicEnvSegment,
    MemorySegment,
    PromptSegment,
    SegmentType,
    SkillsSegment,
    ToolListSegment,
)

logger = logging.getLogger("open_agent")


class PromptBuilder:
    """Assembles a complete system prompt from ordered segments.

    Stable segments are cached after first build and only regenerated
    on explicit ``invalidate()``.  Dynamic segments are rebuilt every call.
    """

    def __init__(
        self,
        tool_registry: Any,
        agent_name: str = "OpenAgent",
        custom_identity: str | None = None,
        workspace: str = ".",
        global_claudemd_path: str | None = None,
        tool_filter: list[str] | None = None,
        token_budget: int = 0,
    ) -> None:
        self._segments: list[PromptSegment] = [
            CoreIdentitySegment(agent_name=agent_name, custom_identity=custom_identity),
            ToolListSegment(tool_registry=tool_registry, tool_filter=tool_filter),
            SkillsSegment(),
            MemorySegment(),
            ClaudemdSegment(workspace=workspace, global_claudemd_path=global_claudemd_path),
            DynamicEnvSegment(),
        ]
        self._token_budget = token_budget
        self._cache: dict[SegmentType, str] = {}

    # ── public API ──

    def build(self, context: dict[str, Any] | None = None) -> str:
        """Build the full system prompt string."""
        ctx = context or {}
        parts: list[str] = []

        for seg in self._segments:
            if seg.is_stable and seg.segment_type in self._cache:
                text = self._cache[seg.segment_type]
            else:
                text = seg.build(ctx)
                if seg.is_stable and text:
                    self._cache[seg.segment_type] = text

            if text:
                parts.append(text)

        result = _p.SEGMENT_SEPARATOR.join(parts)

        if self._token_budget > 0:
            estimated = self.estimate_total_tokens(result)
            if estimated > self._token_budget:
                result = self._truncate(result, ctx)

        return result

    def invalidate(self, segment_type: str | SegmentType | None = None) -> None:
        """Clear cached content. If *segment_type* is None, clear all."""
        if segment_type is None:
            self._cache.clear()
        else:
            st = SegmentType(segment_type) if isinstance(segment_type, str) else segment_type
            self._cache.pop(st, None)

    def estimate_total_tokens(self, text: str | None = None) -> int:
        """Estimate total tokens for the current (or given) prompt text."""
        if text is None:
            text = self.build()
        return max(1, len(text) // 4)

    # ── internals ──

    def _truncate(self, full_text: str, context: dict[str, Any]) -> str:
        """Truncate by removing lowest-priority segments."""
        priority_order = [
            SegmentType.MEMORY,
            SegmentType.CLAUDEMD,
            SegmentType.DYNAMIC_ENV,
            SegmentType.SKILLS,
            SegmentType.TOOL_LIST,
            SegmentType.CORE_IDENTITY,
        ]
        for st in priority_order:
            if self.estimate_total_tokens(full_text) <= self._token_budget:
                break
            tag = st.value
            import re
            full_text = re.sub(
                rf"<{tag}>.*?</{tag}>",
                "",
                full_text,
                flags=re.DOTALL,
            ).strip()
        return full_text
