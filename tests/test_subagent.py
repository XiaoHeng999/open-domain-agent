"""Tests for sub-agent (agent-as-a-tool) implementation."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from open_agent.config import SubagentConfig, SubagentPresetConfig
from open_agent.registry import ToolRegistry
from open_agent.subagent.manager import SubagentManager
from open_agent.subagent.presets import BUILTIN_PRESETS, merge_presets
from open_agent.subagent.tool import SubagentTool, _TASK_PARAMETERS
from open_agent.subagent.types import SubagentPreset, SubagentResult
from open_agent.tools.base import Tool
from open_agent.trace import SpanKind


# -- Helpers --

class FakeTool(Tool):
    def __init__(self, name: str, read_only: bool = True):
        self._name = name
        self._read_only = read_only

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Fake {self._name}"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    @property
    def read_only(self) -> bool:
        return self._read_only

    async def execute(self, **kwargs) -> str:
        return f"{self._name} executed"


def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for name in ["read_file", "list_dir", "web_search", "web_fetch", "write_file", "edit_file", "exec"]:
        registry.register(FakeTool(name, read_only=name in ("read_file", "list_dir", "web_search", "web_fetch")))
    return registry


def _make_manager(registry: ToolRegistry | None = None, config: SubagentConfig | None = None) -> SubagentManager:
    registry = registry or _make_registry()
    config = config or SubagentConfig()
    return SubagentManager(
        provider=MagicMock(),
        tool_registry=registry,
        config=config,
        workspace=".",
    )


# -- 7.1 SubagentTool parameter schema --

class TestSubagentToolSchema:
    def test_parameters_has_prompt_required(self):
        assert "prompt" in _TASK_PARAMETERS["properties"]
        assert "prompt" in _TASK_PARAMETERS["required"]

    def test_parameters_has_all_fields(self):
        props = _TASK_PARAMETERS["properties"]
        assert "subagent_type" in props
        assert "description" in props
        assert "run_in_background" in props
        assert "max_turns" in props

    def test_tool_name_is_task(self):
        tool = SubagentTool(manager=MagicMock())
        assert tool.name == "task"

    def test_description_contains_spawn(self):
        tool = SubagentTool(manager=MagicMock())
        assert "sub-agent" in tool.description.lower() or "spawn" in tool.description.lower()

    def test_to_schema_output(self):
        tool = SubagentTool(manager=MagicMock())
        schema = tool.to_schema()
        assert schema["name"] == "task"
        assert "input_schema" in schema


# -- 7.2 Preset lookup --

class TestPresetLookup:
    def test_builtin_presets_exist(self):
        assert "explore" in BUILTIN_PRESETS
        assert "plan" in BUILTIN_PRESETS
        assert "general" in BUILTIN_PRESETS

    def test_get_preset_known(self):
        mgr = _make_manager()
        preset = mgr.get_preset("explore")
        assert preset.name == "explore"
        assert "read-only" in preset.system_prompt.lower() or "read only" in preset.system_prompt.lower()

    def test_get_preset_unknown_falls_back_to_general(self):
        mgr = _make_manager()
        preset = mgr.get_preset("nonexistent")
        assert preset.name == "general"

    def test_get_preset_general(self):
        mgr = _make_manager()
        preset = mgr.get_preset("general")
        assert preset.name == "general"


# -- 7.3 Restricted ToolRegistry --

class TestRestrictedRegistry:
    def test_explore_has_readonly_tools_only(self):
        mgr = _make_manager()
        registry = mgr._build_restricted_registry(BUILTIN_PRESETS["explore"])
        names = {t.name for t in registry.list_tools()}
        assert "read_file" in names
        assert "list_dir" in names
        assert "web_search" in names
        assert "web_fetch" in names

    def test_explore_excludes_write_and_exec(self):
        mgr = _make_manager()
        registry = mgr._build_restricted_registry(BUILTIN_PRESETS["explore"])
        names = {t.name for t in registry.list_tools()}
        assert "write_file" not in names
        assert "edit_file" not in names
        assert "exec" not in names

    def test_task_tool_excluded(self):
        registry = _make_registry()
        registry.register(SubagentTool(manager=MagicMock()))
        mgr = _make_manager(registry=registry)
        restricted = mgr._build_restricted_registry(BUILTIN_PRESETS["general"])
        names = {t.name for t in restricted.list_tools()}
        assert "task" not in names

    def test_general_has_all_except_task(self):
        registry = _make_registry()
        registry.register(SubagentTool(manager=MagicMock()))
        mgr = _make_manager(registry=registry)
        restricted = mgr._build_restricted_registry(BUILTIN_PRESETS["general"])
        names = {t.name for t in restricted.list_tools()}
        assert "read_file" in names
        assert "write_file" in names
        assert "exec" in names
        assert "task" not in names


# -- 7.4 Concurrency control --

class TestConcurrencyControl:
    @pytest.mark.asyncio
    async def test_within_limits_succeeds(self):
        mgr = _make_manager(config=SubagentConfig(max_concurrent=2))
        # Should be able to acquire a slot
        await mgr._acquire_slot()
        mgr._release_slot()

    @pytest.mark.asyncio
    async def test_max_concurrent_limits(self):
        mgr = _make_manager(config=SubagentConfig(max_concurrent=1))
        await mgr._acquire_slot()
        # Second acquire should block — verify by checking it doesn't complete immediately
        got_it = False

        async def try_acquire():
            nonlocal got_it
            await mgr._acquire_slot()
            got_it = True
            mgr._release_slot()

        task = asyncio.create_task(try_acquire())
        await asyncio.sleep(0.05)
        assert not got_it
        mgr._release_slot()
        await asyncio.sleep(0.05)
        assert got_it
        await task


# -- 7.5 Cascading stop --

class TestCascadingStop:
    @pytest.mark.asyncio
    async def test_stop_all_cancels_active(self):
        mgr = _make_manager()
        # Create a real asyncio.Task that sleeps forever
        async def _hang():
            await asyncio.sleep(1000)

        task = asyncio.create_task(_hang())

        from open_agent.subagent.manager import _ActiveSubagent
        mgr._active["test-1"] = _ActiveSubagent(
            agent_id="test-1",
            task=task,
            preset=BUILTIN_PRESETS["general"],
        )

        await mgr.stop_all(timeout=1.0)
        assert task.cancelled() or task.done()
        assert len(mgr._active) == 0

    @pytest.mark.asyncio
    async def test_stop_all_empty(self):
        mgr = _make_manager()
        await mgr.stop_all()  # Should not raise


# -- 7.6 Sync execution flow --

class TestSyncExecution:
    @pytest.mark.asyncio
    async def test_run_subagent_returns_answer(self):
        mgr = _make_manager()

        # Mock the ReActLoop to return a fixed answer
        with patch("open_agent.subagent.manager.ReActLoop") as MockLoop:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.answer = "Found 3 API endpoints"
            mock_instance.run = AsyncMock(return_value=mock_response)
            MockLoop.return_value = mock_instance

            result = await mgr.run_subagent(
                prompt="Find all API endpoints",
                subagent_type="explore",
            )

        assert result.success is True
        assert "API endpoints" in result.answer


# -- 7.7 Async execution flow --

class TestAsyncExecution:
    @pytest.mark.asyncio
    async def test_background_returns_id_immediately(self):
        mgr = _make_manager()

        # Override _create_react_loop to return a mock loop
        mock_loop = AsyncMock()
        mock_response = MagicMock()
        mock_response.answer = "Background result"
        mock_loop.run = AsyncMock(return_value=mock_response)
        mgr._create_react_loop = MagicMock(return_value=mock_loop)

        agent_id = await mgr.start_background(
            prompt="Search for patterns",
            subagent_type="explore",
        )

        assert agent_id is not None
        assert len(agent_id) == 12

        # Wait for background task to complete
        await asyncio.sleep(0.3)

        result = mgr.get_result(agent_id)
        assert result["status"] == "completed"
        assert result["answer"] == "Background result"

    @pytest.mark.asyncio
    async def test_background_result_running(self):
        mgr = _make_manager()

        with patch("open_agent.subagent.manager.ReActLoop") as MockLoop:
            async def slow_run(**kwargs):
                await asyncio.sleep(10)
                return MagicMock(answer="done")

            mock_instance = AsyncMock()
            mock_instance.run = slow_run
            MockLoop.return_value = mock_instance

            agent_id = await mgr.start_background(prompt="Slow task")

        result = mgr.get_result(agent_id)
        assert result["status"] in ("running", "completed")

        # Cleanup
        await mgr.stop_all()

    @pytest.mark.asyncio
    async def test_get_result_not_found(self):
        mgr = _make_manager()
        result = mgr.get_result("nonexistent")
        assert result["status"] == "not_found"


# -- 7.8 Runtime integration --

class TestRuntimeIntegration:
    def test_subagent_registered_in_tool_registry(self):
        """Verify that the task tool can be registered to a ToolRegistry."""
        registry = _make_registry()
        mgr = _make_manager(registry=registry)
        tool = SubagentTool(manager=mgr)
        registry.register(tool)
        assert registry.has("task")

    def test_subagent_not_in_restricted_registry(self):
        """Verify that task tool is excluded from sub-agent registries."""
        registry = _make_registry()
        mgr = _make_manager(registry=registry)
        tool = SubagentTool(manager=mgr)
        registry.register(tool)

        restricted = mgr._build_restricted_registry(BUILTIN_PRESETS["general"])
        assert not restricted.has("task")


# -- Preset merge --

class TestPresetMerge:
    def test_override_builtin(self):
        custom = [{"name": "explore", "system_prompt": "Custom explorer", "allowed_tools": ["read_file"]}]
        merged = merge_presets(custom)
        assert merged["explore"].system_prompt == "Custom explorer"
        assert merged["explore"].allowed_tools == ["read_file"]

    def test_add_custom_preset(self):
        custom = [{"name": "code-review", "system_prompt": "Review code", "allowed_tools": ["read_file"], "description": "Code review"}]
        merged = merge_presets(custom)
        assert "code-review" in merged
        assert merged["code-review"].description == "Code review"

    def test_empty_presets_keeps_builtins(self):
        merged = merge_presets([])
        assert len(merged) == 3
        assert "explore" in merged
        assert "plan" in merged
        assert "general" in merged


# -- Config --

class TestSubagentConfig:
    def test_defaults(self):
        cfg = SubagentConfig()
        assert cfg.enabled is True
        assert cfg.max_concurrent == 5
        assert cfg.max_children == 3
        assert cfg.default_max_turns == 10
        assert cfg.presets == []

    def test_custom_values(self):
        cfg = SubagentConfig(max_concurrent=3, max_children=2)
        assert cfg.max_concurrent == 3
        assert cfg.max_children == 2


# -- Trace --

class TestSubagentSpanKind:
    def test_subagent_span_kind_exists(self):
        assert SpanKind.SUBAGENT == "subagent"
