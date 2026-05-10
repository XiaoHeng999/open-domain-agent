"""Tests for individual Prompt Segments."""

from __future__ import annotations

import os

import pytest

from open_agent.prompt import prompt as _p
from open_agent.prompt.segments import (
    ClaudemdSegment,
    CoreIdentitySegment,
    DynamicEnvSegment,
    MemorySegment,
    SegmentType,
    SkillsSegment,
    ToolListSegment,
)
from open_agent.registry import ToolRegistry


class TestCoreIdentitySegment:
    def test_default_identity(self):
        seg = CoreIdentitySegment()
        result = seg.build({})
        assert "<core_identity>" in result
        assert "OpenAgent" in result

    def test_custom_identity(self):
        seg = CoreIdentitySegment(custom_identity="You are DataBot.")
        result = seg.build({})
        assert "DataBot" in result

    def test_is_stable(self):
        seg = CoreIdentitySegment()
        assert seg.is_stable is True


class TestToolListSegment:
    def test_no_tools_returns_empty(self):
        registry = ToolRegistry()
        seg = ToolListSegment(tool_registry=registry)
        result = seg.build({})
        assert result == ""

    def test_with_tools(self):
        registry = ToolRegistry()
        registry.register("read_file", handler=lambda: None, description="Read a file")
        seg = ToolListSegment(tool_registry=registry)
        result = seg.build({})
        assert "<tool_list>" in result
        assert "read_file" in result

    def test_tag_filter(self):
        registry = ToolRegistry()
        registry.register("tool_a", handler=lambda: None, description="A", tags=["coding"])
        registry.register("tool_b", handler=lambda: None, description="B", tags=["web"])
        seg = ToolListSegment(tool_registry=registry, tool_filter=["coding"])
        result = seg.build({})
        assert "tool_a" in result
        assert "tool_b" not in result

    def test_is_dynamic(self):
        seg = ToolListSegment(tool_registry=ToolRegistry())
        assert seg.is_stable is False


class TestSkillsSegment:
    def test_no_skills_returns_empty(self):
        seg = SkillsSegment()
        result = seg.build({})
        assert result == ""

    def test_with_skills(self):
        seg = SkillsSegment()
        result = seg.build({
            "matched_skills": [
                {"name": "code-review", "content": "Review code systematically"},
            ]
        })
        assert "<skills>" in result
        assert "code-review" in result
        assert "Review code systematically" in result

    def test_is_dynamic(self):
        assert SkillsSegment().is_stable is False


class TestMemorySegment:
    def test_empty_memory_returns_empty(self):
        seg = MemorySegment()
        assert seg.build({}) == ""

    def test_with_working_memory(self):
        seg = MemorySegment()
        result = seg.build({"working_memory": "User asked about tests"})
        assert "<memory>" in result
        assert "User asked about tests" in result

    def test_with_all_memory_components(self):
        seg = MemorySegment()
        result = seg.build({
            "working_memory": "Current context",
            "episodic_summary": "Past task summary",
            "user_profile": "Prefers Python",
        })
        assert "Current context" in result
        assert "Past task summary" in result
        assert "Prefers Python" in result

    def test_is_dynamic(self):
        assert MemorySegment().is_stable is False


class TestClaudemdSegment:
    def test_no_claudemd_returns_empty(self, tmp_path):
        seg = ClaudemdSegment(workspace=str(tmp_path))
        result = seg.build({})
        assert result == ""

    def test_with_project_claudemd(self, tmp_path):
        claudemd = tmp_path / "CLAUDE.md"
        claudemd.write_text("Always use type hints.")
        seg = ClaudemdSegment(workspace=str(tmp_path))
        result = seg.build({})
        assert "<claudemd>" in result
        assert "Always use type hints." in result

    def test_with_claude_dir(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "style.md").write_text("Use snake_case.")
        seg = ClaudemdSegment(workspace=str(tmp_path))
        result = seg.build({})
        assert "Use snake_case." in result

    def test_is_dynamic(self):
        assert ClaudemdSegment().is_stable is False


class TestDynamicEnvSegment:
    def test_build_contains_env_info(self):
        seg = DynamicEnvSegment()
        result = seg.build({})
        assert "<dynamic_env>" in result
        assert "Date:" in result
        assert "Platform:" in result
        assert "Working directory:" in result

    def test_is_dynamic(self):
        assert DynamicEnvSegment().is_stable is False

    def test_contains_cwd(self):
        seg = DynamicEnvSegment()
        result = seg.build({})
        assert os.getcwd() in result
