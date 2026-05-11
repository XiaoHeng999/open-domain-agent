"""Tests for the 4-layer memory architecture: Runtime, Todo, Profile, Retrieval, Archive."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

from open_agent.config import MemoryConfig
from open_agent.memory.models import Message, TaskState
from open_agent.memory.token_utils import estimate_tokens
from open_agent.memory.runtime import RuntimeMemory
from open_agent.memory.profile import ProfileMemory
from open_agent.memory.archive import ArchiveMemory
from open_agent.memory.factory import MemoryFactory
from open_agent.tools.todo import TodoManager, TodoItem, todo_handler


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# =====================================================================
# 9.1 RuntimeMemory
# =====================================================================


class TestRuntimeMemory:
    def test_add_message(self):
        rm = RuntimeMemory()
        run(rm.add_message("user", "Hello"))
        run(rm.add_message("assistant", "Hi"))
        ctx = run(rm.get_context())
        assert len(ctx) == 2
        assert ctx[0]["role"] == "user"
        assert ctx[1]["role"] == "assistant"

    def test_message_token_tracking(self):
        msg = Message(role="user", content="a" * 100)
        assert msg.tokens == 25

    def test_task_state_increment(self):
        ts = TaskState()
        assert ts.current_step == 0
        ts.increment_step()
        assert ts.current_step == 1
        assert ts.rounds_since_todo_update == 1

    def test_task_state_finished(self):
        ts = TaskState()
        ts.mark_finished("direct_answer")
        assert ts.finished
        assert "direct_answer" in ts.termination_flags

    def test_task_state_todo_reset(self):
        ts = TaskState()
        ts.increment_step()
        ts.increment_step()
        assert ts.rounds_since_todo_update == 2
        ts.reset_todo_counter()
        assert ts.rounds_since_todo_update == 0

    def test_compression_normal_level(self):
        rm = RuntimeMemory()
        assert rm.compression_level == "normal"

    def test_compression_triggers_rolling_summary(self):
        cfg = MemoryConfig(
            runtime_token_budget=200,
            compression_threshold=0.5,
            aggressive_threshold=0.9,
            keep_recent_turns=2,
        )
        rm = RuntimeMemory(config=cfg)
        # Add enough messages to trigger compression
        for i in range(20):
            run(rm.add_message("user", f"Message {i} with enough padding to consume tokens"))
            run(rm.add_message("assistant", f"Response {i} with padding too"))

        # Should have rolling summary now
        assert rm.rolling_summary != ""
        ctx = run(rm.get_context())
        assert any(m["role"] == "system" for m in ctx)

    def test_tool_cache(self):
        rm = RuntimeMemory()
        assert rm.cache_get("search", {"q": "test"}) is None
        rm.cache_put("search", {"q": "test"}, "result1")
        assert rm.cache_get("search", {"q": "test"}) == "result1"

    def test_tool_cache_lru_eviction(self):
        cfg = MemoryConfig(tool_cache_max_entries=2)
        rm = RuntimeMemory(config=cfg)
        rm.cache_put("a", {}, "1")
        rm.cache_put("b", {}, "2")
        rm.cache_put("c", {}, "3")
        assert rm.cache_get("a", {}) is None  # evicted
        assert rm.cache_get("c", {}) == "3"

    def test_clear(self):
        rm = RuntimeMemory()
        run(rm.add_message("user", "hi"))
        run(rm.clear())
        ctx = run(rm.get_context())
        assert len(ctx) == 0

    def test_write_dict_interface(self):
        rm = RuntimeMemory()
        run(rm.write({"role": "user", "content": "test"}))
        ctx = run(rm.get_context())
        assert len(ctx) == 1


# =====================================================================
# 9.2 TodoManager
# =====================================================================


class TestTodoManager:
    def test_update_and_render(self):
        tm = TodoManager()
        result = tm.update([
            {"content": "Step 1", "status": "completed"},
            {"content": "Step 2", "status": "in_progress"},
            {"content": "Step 3", "status": "pending"},
        ])
        assert "[x] Step 1" in result
        assert "[>] Step 2" in result
        assert "[ ] Step 3" in result

    def test_in_progress_uniqueness(self):
        tm = TodoManager()
        with pytest.raises(ValueError, match="Only one item"):
            tm.update([
                {"content": "A", "status": "in_progress"},
                {"content": "B", "status": "in_progress"},
            ])

    def test_empty_plan_renders_empty(self):
        tm = TodoManager()
        assert tm.render() == ""

    def test_active_form_display(self):
        tm = TodoManager()
        result = tm.update([
            {"content": "Analyze data", "status": "in_progress", "activeForm": "Analyzing data..."},
        ])
        assert "Analyzing data..." in result

    def test_whole_list_replacement(self):
        tm = TodoManager()
        tm.update([{"content": "Old task", "status": "pending"}])
        tm.update([{"content": "New task", "status": "pending"}])
        assert len(tm.items) == 1
        assert tm.items[0].content == "New task"

    def test_has_unfinished(self):
        tm = TodoManager()
        assert not tm.has_unfinished()
        tm.update([{"content": "Task", "status": "pending"}])
        assert tm.has_unfinished()
        tm.update([{"content": "Task", "status": "completed"}])
        assert not tm.has_unfinished()

    def test_invalid_status_defaults_to_pending(self):
        tm = TodoManager()
        tm.update([{"content": "Task", "status": "invalid"}])
        assert tm.items[0].status == "pending"

    def test_todo_handler_with_manager(self):
        tm = TodoManager()
        result = todo_handler(
            items=[{"content": "Test", "status": "pending"}],
            _todo_manager=tm,
        )
        assert "[ ] Test" in result

    def test_todo_handler_without_manager_raises(self):
        with pytest.raises(RuntimeError):
            todo_handler(items=[], _todo_manager=None)


# =====================================================================
# 9.3 ProfileMemory
# =====================================================================


class TestProfileMemory:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "profile.sqlite")
        self.config = MemoryConfig(profile_db_path=db_path)
        self.pm = ProfileMemory(config=self.config)

    def teardown_method(self):
        self.pm.close()

    def test_load_empty_profile(self):
        profile = self.pm.load()
        assert profile["preferences"] == {}
        assert profile["constraints"] == []
        assert profile["avoidance_hints"] == []

    def test_update_preferences(self):
        run(self.pm.update_preferences({"language": "python"}))
        profile = self.pm.load()
        assert profile["preferences"]["language"] == "python"

    def test_update_constraints(self):
        run(self.pm.update_constraints(["no external APIs"]))
        profile = self.pm.load()
        assert "no external APIs" in profile["constraints"]

    def test_update_tech_stack(self):
        run(self.pm.update_tech_stack(["Python", "React"]))
        run(self.pm.update_tech_stack(["Python", "Docker"]))
        profile = self.pm.load()
        assert "Python" in profile["tech_stack"]
        assert "Docker" in profile["tech_stack"]
        # No duplicates
        assert profile["tech_stack"].count("Python") == 1

    def test_avoidance_hints_dedup(self):
        run(self.pm.add_avoidance_hint("Don't use eval()"))
        run(self.pm.add_avoidance_hint("Don't use eval()"))
        profile = self.pm.load()
        assert profile["avoidance_hints"].count("Don't use eval()") == 1

    def test_avoidance_hints_substring_dedup(self):
        run(self.pm.add_avoidance_hint("Don't use eval() in user inputs"))
        run(self.pm.add_avoidance_hint("Don't use eval()"))
        profile = self.pm.load()
        assert len(profile["avoidance_hints"]) == 1

    def test_injection_text_empty(self):
        assert self.pm.get_injection_text() == ""

    def test_injection_text_with_data(self):
        run(self.pm.update_preferences({"format": "table"}))
        text = self.pm.get_injection_text()
        assert "format: table" in text
        assert "User profile" in text

    def test_read_write_via_base_interface(self):
        run(self.pm.write({"preferences": {"theme": "dark"}}))
        profile = run(self.pm.read())
        assert profile["preferences"]["theme"] == "dark"

    def test_write_string_as_avoidance(self):
        run(self.pm.write("Avoid using print()"))
        profile = self.pm.load()
        assert "Avoid using print()" in profile["avoidance_hints"]

    def test_persistence_across_instances(self):
        run(self.pm.update_preferences({"key": "value"}))
        self.pm.close()

        pm2 = ProfileMemory(config=self.config)
        profile = pm2.load()
        assert profile["preferences"]["key"] == "value"
        pm2.close()


# =====================================================================
# 9.4 RetrievalMemory
# =====================================================================


class TestRetrievalMemory:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = MemoryConfig(
            retrieval_store_dir=os.path.join(self.tmpdir, "retrieval"),
            retrieval_top_k=5,
            retrieval_max_inject_tokens=1500,
            retrieval_score_threshold=0.1,  # low threshold for tests
        )

    def test_write_and_query_episodic(self):
        rm = MemoryFactory(self.config).create_retrieval_memory()
        run(rm.write_episodic(
            intent="search files",
            steps_summary="searched for *.py",
            result="found 10 files",
            success=True,
        ))
        results = run(rm.query("search files"))
        assert len(results) >= 1
        assert any("search" in r["text"].lower() for r in results)

    def test_write_and_query_semantic(self):
        rm = MemoryFactory(self.config).create_retrieval_memory()
        run(rm.write_semantic(
            text="Test files are in the tests/ directory",
            category="project_structure",
        ))
        results = run(rm.query("where are tests"))
        assert len(results) >= 1

    def test_layer_filtering(self):
        rm = MemoryFactory(self.config).create_retrieval_memory()
        run(rm.write_episodic(intent="task 1", steps_summary="s1", result="r1"))
        run(rm.write_semantic(text="semantic rule 1", category="general"))

        ep_results = run(rm.query("task", layer="episodic"))
        sem_results = run(rm.query("rule", layer="semantic"))

        for r in ep_results:
            assert r["metadata"]["layer"] == "episodic"
        for r in sem_results:
            assert r["metadata"]["layer"] == "semantic"

    def test_token_truncation(self):
        rm = MemoryFactory(self.config).create_retrieval_memory()
        # Write many entries
        for i in range(10):
            run(rm.write_episodic(
                intent=f"task {i}",
                steps_summary=f"steps for task {i} with lots of detail " * 5,
                result=f"result {i}",
            ))
        # Query with very limited token budget
        results = run(rm.query("task", max_inject_tokens=50))
        total_tokens = sum(estimate_tokens(r["text"]) for r in results)
        assert total_tokens <= 50

    def test_empty_query_returns_nothing(self):
        rm = MemoryFactory(self.config).create_retrieval_memory()
        results = run(rm.query(""))
        assert len(results) == 0

    def test_persistence(self):
        rm1 = MemoryFactory(self.config).create_retrieval_memory()
        run(rm1.write_episodic(intent="persist test", steps_summary="s", result="r"))
        # Create new instance pointing to same dir
        rm2 = MemoryFactory(self.config).create_retrieval_memory()
        results = run(rm2.query("persist"))
        assert len(results) >= 1


# =====================================================================
# 9.5 ArchiveMemory
# =====================================================================


class TestArchiveMemory:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = MemoryConfig(archive_dir=os.path.join(self.tmpdir, "archive"))

    def test_write_and_query(self):
        am = ArchiveMemory(config=self.config, session_id="test1")
        am.write_record({"type": "message", "role": "user", "content": "hello"})
        results = am.query("test1")
        assert len(results) == 1
        assert results[0]["content"] == "hello"

    def test_type_filtering(self):
        am = ArchiveMemory(config=self.config, session_id="test2")
        am.write_record({"type": "message", "role": "user", "content": "hi"})
        am.write_record({"type": "tool_call", "tool": "search", "args": {}})
        messages = am.query("test2", type="message")
        assert len(messages) == 1
        assert messages[0]["type"] == "message"

    def test_session_isolation(self):
        am1 = ArchiveMemory(config=self.config, session_id="s1")
        am2 = ArchiveMemory(config=self.config, session_id="s2")
        am1.write_record({"type": "message", "content": "session 1"})
        am2.write_record({"type": "message", "content": "session 2"})
        assert len(am1.query("s1")) == 1
        assert am1.query("s1")[0]["content"] == "session 1"
        assert len(am2.query("s2")) == 1

    def test_replay(self):
        am = ArchiveMemory(config=self.config, session_id="replay_test")
        am.write_record({"type": "message", "content": "first"})
        am.write_record({"type": "message", "content": "second"})
        records = am.replay("replay_test")
        assert len(records) == 2

    def test_auto_timestamp(self):
        am = ArchiveMemory(config=self.config, session_id="ts_test")
        am.write_record({"type": "message", "content": "ts"})
        records = am.query("ts_test")
        assert "ts" in records[0]

    def test_limit(self):
        am = ArchiveMemory(config=self.config, session_id="limit_test")
        for i in range(10):
            am.write_record({"type": "message", "content": f"msg {i}"})
        results = am.query("limit_test", limit=3)
        assert len(results) == 3

    def test_nonexistent_session(self):
        am = ArchiveMemory(config=self.config)
        assert am.query("nonexistent") == []

    def test_write_via_base_interface(self):
        am = ArchiveMemory(config=self.config, session_id="base_test")
        run(am.write({"type": "message", "content": "via base"}))
        results = run(am.read("test", session_id="base_test"))
        assert len(results) == 1


# =====================================================================
# 9.6 MemoryFactory
# =====================================================================


class TestNewMemoryFactory:
    def test_create_runtime_memory(self):
        factory = MemoryFactory()
        rm = factory.create_runtime_memory()
        assert isinstance(rm, RuntimeMemory)

    def test_create_profile_memory(self):
        tmpdir = tempfile.mkdtemp()
        cfg = MemoryConfig(profile_db_path=os.path.join(tmpdir, "test.sqlite"))
        factory = MemoryFactory(config=cfg)
        pm = factory.create_profile_memory()
        assert isinstance(pm, ProfileMemory)
        pm.close()

    def test_create_retrieval_memory(self):
        tmpdir = tempfile.mkdtemp()
        cfg = MemoryConfig(retrieval_store_dir=os.path.join(tmpdir, "ret"))
        factory = MemoryFactory(config=cfg)
        rm = factory.create_retrieval_memory()
        assert hasattr(rm, "query")

    def test_create_archive_memory(self):
        tmpdir = tempfile.mkdtemp()
        cfg = MemoryConfig(archive_dir=os.path.join(tmpdir, "arc"))
        factory = MemoryFactory(config=cfg)
        am = factory.create_archive_memory(session_id="test")
        assert isinstance(am, ArchiveMemory)

    def test_backward_compat_create_working_memory(self):
        factory = MemoryFactory()
        wm = factory.create_working_memory()
        from open_agent.memory.working import WorkingMemory
        assert isinstance(wm, WorkingMemory)

    def test_backward_compat_create_user_profile(self):
        tmpdir = tempfile.mkdtemp()
        cfg = MemoryConfig(profile_db_path=os.path.join(tmpdir, "bc.sqlite"))
        factory = MemoryFactory(config=cfg)
        up = factory.create_user_profile()
        assert isinstance(up, ProfileMemory)
        up.close()


# =====================================================================
# 9.7 Integration tests
# =====================================================================


class TestIntegration:
    def test_runtime_memory_as_conversation_history(self):
        """RuntimeMemory replaces _conversation_history."""
        rm = RuntimeMemory()
        run(rm.add_message("user", "What is Python?"))
        run(rm.add_message("assistant", "Python is a programming language."))
        ctx = run(rm.get_context())
        assert len(ctx) == 2
        assert ctx[0]["content"] == "What is Python?"

    def test_todo_staleness_detection(self):
        """Todo staleness triggers reminder after N rounds."""
        from open_agent.registry import ToolRegistry
        from open_agent.agent.react import ReActLoop
        from open_agent.tools.todo import TodoManager

        rm = RuntimeMemory()
        tm = TodoManager()
        tm.update([{"content": "Task A", "status": "pending"}])

        registry = ToolRegistry()
        loop = ReActLoop(
            tool_registry=registry,
            runtime_memory=rm,
            todo_manager=tm,
            staleness_rounds=3,
        )

        # Simulate 3 rounds without todo update
        for _ in range(3):
            rm.task_state.increment_step()

        reminder = loop._check_staleness()
        assert "reminder" in reminder.lower()

    def test_todo_staleness_resets_on_update(self):
        rm = RuntimeMemory()
        tm = TodoManager()
        tm.update([{"content": "Task A", "status": "pending"}])

        rm.task_state.increment_step()
        rm.task_state.increment_step()
        rm.task_state.reset_todo_counter()

        assert rm.task_state.rounds_since_todo_update == 0

    def test_memory_segment_rendering(self):
        """MemorySegment renders all layers correctly."""
        from open_agent.prompt.segments import MemorySegment

        seg = MemorySegment()
        context = {
            "todo_plan": "[>] Working on task\n[ ] Next task",
            "user_profile": "Preferences: table output",
            "retrieval_results": "- [episodic] Previous task result (score: 0.85)",
        }
        result = seg.build(context)
        assert "Current plan" in result
        assert "User preferences" in result
        assert "Retrieved memories" in result

    def test_memory_segment_empty_context(self):
        from open_agent.prompt.segments import MemorySegment
        seg = MemorySegment()
        assert seg.build({}) == ""

    def test_end_to_end_memory_flow(self):
        """Full flow: write to all layers, query back."""
        tmpdir = tempfile.mkdtemp()
        cfg = MemoryConfig(
            profile_db_path=os.path.join(tmpdir, "profile.sqlite"),
            retrieval_store_dir=os.path.join(tmpdir, "retrieval"),
            archive_dir=os.path.join(tmpdir, "archive"),
        )
        factory = MemoryFactory(config=cfg)

        # Create all layers
        runtime = factory.create_runtime_memory()
        profile = factory.create_profile_memory()
        retrieval = factory.create_retrieval_memory()
        archive = factory.create_archive_memory(session_id="e2e_test")

        # Write to all layers
        run(runtime.add_message("user", "Find Python files"))
        run(profile.update_preferences({"language": "python"}))
        run(retrieval.write_episodic(
            intent="find files", steps_summary="searched *.py", result="found 5"
        ))
        archive.write_record({"type": "message", "content": "Find Python files"})

        # Query all layers
        ctx = run(runtime.get_context())
        assert len(ctx) >= 1

        profile_text = profile.get_injection_text()
        assert "python" in profile_text

        results = run(retrieval.query("find files"))
        assert len(results) >= 1

        records = archive.query("e2e_test")
        assert len(records) >= 1

        # Cleanup
        profile.close()

    def test_todo_tool_registered_and_callable(self):
        """Todo tool can be registered and called through ToolRegistry."""
        from open_agent.registry import ToolRegistry
        from open_agent.tools.todo import TodoTool, TodoManager

        tm = TodoManager()
        registry = ToolRegistry()
        registry.register(TodoTool(todo_manager=tm))

        tool = registry.get("todo")
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            tool.execute(items=[{"content": "Step 1", "status": "pending"}])
        )
        assert "[ ] Step 1" in result
