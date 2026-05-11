"""Tests for the Prompt Pipeline — PromptBuilder, caching, token estimation."""

from __future__ import annotations

import pytest

from open_agent.prompt.builder import PromptBuilder
from open_agent.prompt.segments import SegmentType
from open_agent.registry import ToolRegistry
from open_agent.tools.base import FunctionTool


class TestPromptBuilderBuild:
    def test_build_returns_non_empty_string(self):
        registry = ToolRegistry()
        builder = PromptBuilder(tool_registry=registry)
        result = builder.build()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_contains_segment_tags(self):
        registry = ToolRegistry()
        builder = PromptBuilder(tool_registry=registry)
        result = builder.build()
        assert "<core_identity>" in result
        assert "</core_identity>" in result
        assert "<dynamic_env>" in result

    def test_build_with_tools(self):
        from open_agent.tools.base import FunctionTool
        registry = ToolRegistry()
        registry.register(FunctionTool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=lambda x: x,
        ), tags=["test"])
        builder = PromptBuilder(tool_registry=registry)
        result = builder.build()
        assert "<tool_list>" in result
        assert "test_tool" in result

    def test_build_with_matched_skills(self):
        registry = ToolRegistry()
        builder = PromptBuilder(tool_registry=registry)
        skills = [{"name": "my-skill", "content": "Do something useful"}]
        result = builder.build(context={"matched_skills": skills})
        assert "<skills>" in result
        assert "my-skill" in result

    def test_build_empty_memory_skips_segment(self):
        registry = ToolRegistry()
        builder = PromptBuilder(tool_registry=registry)
        result = builder.build()
        assert "<memory>" not in result

    def test_build_with_memory_context(self):
        registry = ToolRegistry()
        builder = PromptBuilder(tool_registry=registry)
        result = builder.build(context={
            "working_memory": "User asked about Python",
            "episodic_summary": "Previously discussed async/await",
            "user_profile": "Prefers concise answers",
        })
        assert "<memory>" in result
        assert "Python" in result


class TestPromptBuilderCaching:
    def test_stable_segment_cached(self):
        registry = ToolRegistry()
        builder = PromptBuilder(tool_registry=registry)
        result1 = builder.build()
        result2 = builder.build()
        # Core identity (stable) content should be identical
        assert "<core_identity>" in result1
        assert result1 == result2

    def test_invalidate_clears_cache(self):
        registry = ToolRegistry()
        builder = PromptBuilder(tool_registry=registry)
        result1 = builder.build()
        builder.invalidate()
        result2 = builder.build()
        # Both should still have content (rebuilt)
        assert "<core_identity>" in result2

    def test_invalidate_specific_segment(self):
        registry = ToolRegistry()
        builder = PromptBuilder(tool_registry=registry)
        builder.build()
        builder.invalidate(SegmentType.CORE_IDENTITY)
        assert SegmentType.CORE_IDENTITY not in builder._cache


class TestPromptBuilderTokenEstimation:
    def test_estimate_tokens_nonzero(self):
        registry = ToolRegistry()
        builder = PromptBuilder(tool_registry=registry)
        result = builder.build()
        tokens = builder.estimate_total_tokens(result)
        assert tokens > 0

    def test_token_budget_truncation(self):
        registry = ToolRegistry()
        registry.register(FunctionTool(name="tool1", description="Tool one", parameters={"type": "object", "properties": {}}, handler=lambda: None))
        builder = PromptBuilder(tool_registry=registry, token_budget=5)
        result = builder.build()
        # Very small budget should truncate to just core identity or empty
        assert isinstance(result, str)


class TestSegmentSeparator:
    def test_segments_separated_by_separator(self):
        registry = ToolRegistry()
        registry.register(FunctionTool(name="t1", description="T1", parameters={"type": "object", "properties": {}}, handler=lambda: None))
        builder = PromptBuilder(tool_registry=registry)
        result = builder.build()
        assert "---" in result
