"""Prompt segment base class and six concrete segment implementations."""

from __future__ import annotations

import abc
import datetime
import json
import logging
import os
import platform
from enum import Enum
from pathlib import Path
from typing import Any

from open_agent.prompt import prompt as _p

logger = logging.getLogger("open_agent")


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class SegmentType(str, Enum):
    CORE_IDENTITY = _p.SEGMENT_TAG_CORE_IDENTITY
    TOOL_LIST = _p.SEGMENT_TAG_TOOL_LIST
    SKILLS = _p.SEGMENT_TAG_SKILLS
    MEMORY = _p.SEGMENT_TAG_MEMORY
    CLAUDEMD = _p.SEGMENT_TAG_CLAUDEMD
    DYNAMIC_ENV = _p.SEGMENT_TAG_DYNAMIC_ENV


class PromptSegment(abc.ABC):
    """Base class for a single prompt segment."""

    segment_type: SegmentType
    is_stable: bool

    @abc.abstractmethod
    def build(self, context: dict[str, Any]) -> str:
        """Build the segment content. Return empty string to skip."""

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate (~4 chars per token)."""
        return max(1, len(text) // 4)


def _wrap(tag: str, content: str) -> str:
    """Wrap content with XML-style tags."""
    return f"<{tag}>\n{content}\n</{tag}>"


# ---------------------------------------------------------------------------
# 1. Core Identity — stable
# ---------------------------------------------------------------------------


class CoreIdentitySegment(PromptSegment):
    segment_type = SegmentType.CORE_IDENTITY
    is_stable = True

    def __init__(self, agent_name: str = "OpenAgent", custom_identity: str | None = None) -> None:
        self._agent_name = agent_name
        self._custom_identity = custom_identity

    def build(self, context: dict[str, Any]) -> str:
        if self._custom_identity:
            content = _p.CORE_IDENTITY_CUSTOM_TEMPLATE.format(
                custom_identity=self._custom_identity,
            )
        else:
            content = _p.CORE_IDENTITY_TEMPLATE.format(
                agent_name=self._agent_name,
            )
        return _wrap(_p.SEGMENT_TAG_CORE_IDENTITY, content)


# ---------------------------------------------------------------------------
# 2. Tool List — dynamic
# ---------------------------------------------------------------------------


class ToolListSegment(PromptSegment):
    segment_type = SegmentType.TOOL_LIST
    is_stable = False

    def __init__(self, tool_registry: Any, tool_filter: list[str] | None = None) -> None:
        self._registry = tool_registry
        self._tool_filter = tool_filter

    def build(self, context: dict[str, Any]) -> str:
        if self._tool_filter:
            tools = self._registry.filter_by_tags(self._tool_filter)
        else:
            tools = self._registry.list_tools()

        if not tools:
            return ""

        entries: list[str] = []
        for tool in tools:
            schema = tool.schema
            params = schema.get("inputSchema", schema).get("properties", {})
            param_str = json.dumps(params, ensure_ascii=False) if params else "none"
            entries.append(
                _p.TOOL_ENTRY_TEMPLATE.format(
                    name=tool.name,
                    description=tool.description or "(no description)",
                    parameters=param_str,
                )
            )

        content = _p.TOOL_LIST_HEADER + "\n" + "\n".join(entries)
        return _wrap(_p.SEGMENT_TAG_TOOL_LIST, content)


# ---------------------------------------------------------------------------
# 3. Skills — dynamic
# ---------------------------------------------------------------------------


class SkillsSegment(PromptSegment):
    segment_type = SegmentType.SKILLS
    is_stable = False

    def build(self, context: dict[str, Any]) -> str:
        skills: list[dict[str, Any]] = context.get("matched_skills", [])
        if not skills:
            return ""

        entries: list[str] = []
        for skill in skills:
            entries.append(
                _p.SKILL_ENTRY_TEMPLATE.format(
                    name=skill.get("name", ""),
                    content=skill.get("content", ""),
                )
            )

        content = _p.SKILLS_HEADER + "\n" + "\n\n".join(entries)
        return _wrap(_p.SEGMENT_TAG_SKILLS, content)


# ---------------------------------------------------------------------------
# 4. Memory — dynamic
# ---------------------------------------------------------------------------


class MemorySegment(PromptSegment):
    segment_type = SegmentType.MEMORY
    is_stable = False

    def build(self, context: dict[str, Any]) -> str:
        parts: list[str] = []

        working = context.get("working_memory")
        if working:
            parts.append(
                _p.MEMORY_WORKING_TEMPLATE.format(working_memory=working)
            )

        episodic = context.get("episodic_summary")
        if episodic:
            parts.append(
                _p.MEMORY_EPISODIC_TEMPLATE.format(episodic_summary=episodic)
            )

        profile = context.get("user_profile")
        if profile:
            parts.append(
                _p.MEMORY_PROFILE_TEMPLATE.format(user_profile=profile)
            )

        if not parts:
            return ""

        content = _p.MEMORY_HEADER + "\n" + "\n".join(parts)
        return _wrap(_p.SEGMENT_TAG_MEMORY, content)


# ---------------------------------------------------------------------------
# 5. CLAUDE.md — mixed (stable base + dynamic project)
# ---------------------------------------------------------------------------


class ClaudemdSegment(PromptSegment):
    segment_type = SegmentType.CLAUDEMD
    is_stable = False  # treated as dynamic since project CLAUDE.md can change

    def __init__(self, workspace: str = ".", global_claudemd_path: str | None = None) -> None:
        self._workspace = workspace
        self._global_path = global_claudemd_path

    def build(self, context: dict[str, Any]) -> str:
        directives: list[str] = []

        # Global CLAUDE.md
        if self._global_path:
            p = Path(self._global_path)
            if p.exists():
                directives.append(p.read_text(encoding="utf-8"))

        # Project CLAUDE.md
        project_claudemd = Path(self._workspace) / "CLAUDE.md"
        if project_claudemd.exists():
            directives.append(project_claudemd.read_text(encoding="utf-8"))

        # .claude/ directory
        claude_dir = Path(self._workspace) / ".claude"
        if claude_dir.is_dir():
            for f in sorted(claude_dir.glob("*.md")):
                directives.append(f.read_text(encoding="utf-8"))

        if not directives:
            return ""

        content = _p.CLAUDEMD_HEADER + "\n" + "\n\n".join(directives)
        return _wrap(_p.SEGMENT_TAG_CLAUDEMD, content)


# ---------------------------------------------------------------------------
# 6. Dynamic Environment — dynamic
# ---------------------------------------------------------------------------


class DynamicEnvSegment(PromptSegment):
    segment_type = SegmentType.DYNAMIC_ENV
    is_stable = False

    def build(self, context: dict[str, Any]) -> str:
        content = _p.DYNAMIC_ENV_TEMPLATE.format(
            date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            platform=platform.platform(),
            workdir=os.getcwd(),
        )
        return _wrap(_p.SEGMENT_TAG_DYNAMIC_ENV, content)
