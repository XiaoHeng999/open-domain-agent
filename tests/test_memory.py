"""Tests for the memory subsystem: working, episodic, profile, factory, and lifecycle."""

from __future__ import annotations

import asyncio
import pytest

from open_agent.base import BaseComponent, MemoryManager
from open_agent.config import MemoryConfig

from open_agent.memory import (
    EpisodicStore,
    EpisodicSummary,
    InMemorySemanticKB,
    MemoryFactory,
    Message,
    SemanticKB,
    UserProfile,
    UserProfileState,
    WorkingMemory,
)


# ---------- helpers ----------

def run(coro):
    """Run an async coroutine synchronously in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# =====================================================================
# Working Memory
# =====================================================================


class TestWorkingMemory:
    def test_add_and_get_context(self):
        wm = WorkingMemory()
        run(wm.add_message("user", "Hello"))
        run(wm.add_message("assistant", "Hi there!"))
        ctx = run(wm.get_context())
        assert len(ctx) == 2
        assert ctx[0]["role"] == "user"
        assert ctx[0]["content"] == "Hello"
        assert ctx[1]["role"] == "assistant"

    def test_write_delegates_to_add_message(self):
        wm = WorkingMemory()
        run(wm.write({"role": "user", "content": "Write this"}))
        ctx = run(wm.get_context())
        assert len(ctx) == 1
        assert ctx[0]["content"] == "Write this"

    def test_read_returns_context(self):
        wm = WorkingMemory()
        run(wm.add_message("system", "You are helpful"))
        ctx = run(wm.read())
        assert len(ctx) == 1

    def test_compression_triggers_on_threshold(self):
        # Use the minimum allowed limit (100) with low threshold
        cfg = MemoryConfig(
            working_memory_token_limit=100,
            compression_threshold=0.3,
            keep_recent_turns=1,
        )
        wm = WorkingMemory(config=cfg)
        # Each message is ~40 chars => ~10 tokens.  Add enough to exceed 30 tokens (100 * 0.3).
        for i in range(10):
            run(wm.add_message(
                "user",
                f"Message number {i} with some extra padding text here to consume tokens",
            ))

        ctx = run(wm.get_context())
        # After compression we should have: [summary_prefix, recent_turn]
        roles = [m["role"] for m in ctx]
        assert "system" in roles  # summary prefix
        # The last message should still be present
        assert ctx[-1]["content"].startswith("Message number 9")

    def test_forced_compress_context(self):
        cfg = MemoryConfig(keep_recent_turns=2)
        wm = WorkingMemory(config=cfg)
        for i in range(6):
            run(wm.add_message("user", f"Turn {i}"))

        run(wm.compress_context())
        # Only 2 messages kept + a summary prefix
        ctx = run(wm.get_context())
        non_summary = [m for m in ctx if m["role"] != "system"]
        assert len(non_summary) == 2

    def test_clear(self):
        wm = WorkingMemory()
        run(wm.add_message("user", "hello"))
        run(wm.add_message("assistant", "hi"))
        run(wm.clear())
        ctx = run(wm.get_context())
        assert len(ctx) == 0

    def test_token_estimation(self):
        msg = Message(role="user", content="a" * 100)
        assert msg.tokens == 25  # 100 / 4


# =====================================================================
# Episodic Store
# =====================================================================


class TestEpisodicStore:
    def test_write_and_retrieve(self):
        store = EpisodicStore()
        summary = EpisodicSummary(
            intent="search code",
            steps_summary="Searched for 'MemoryManager' in src/",
            result="Found 3 files",
        )
        run(store.write_episodic_summary(summary))

        results = run(store.retrieve_episodic("search code"))
        assert len(results) == 1
        assert results[0].intent == "search code"

    def test_write_after_task_trigger(self):
        store = EpisodicStore()
        s = run(store.write_after_task(
            intent="refactor module",
            steps_summary="Moved classes to separate files",
            result="All tests pass",
        ))
        assert s.intent == "refactor module"
        results = run(store.retrieve_episodic("refactor"))
        assert len(results) == 1

    def test_write_after_reflection_trigger(self):
        store = EpisodicStore()
        s = run(store.write_after_reflection(
            intent="debug error",
            steps_summary="Checked logs, found null pointer",
            result="Fixed",
        ))
        assert "debug" in s.intent

    def test_write_after_checkpoint_trigger(self):
        store = EpisodicStore()
        s = run(store.write_after_checkpoint(
            intent="checkpoint save",
            steps_summary="Saved state",
            result="OK",
        ))
        assert s.result == "OK"

    def test_top_k_limit(self):
        store = EpisodicStore()
        for i in range(10):
            run(store.write_after_task(
                intent=f"task {i}",
                steps_summary=f"did step {i}",
                result=f"result {i}",
            ))
        results = run(store.retrieve_episodic("task", top_k=3))
        assert len(results) == 3

    def test_empty_query_returns_recent(self):
        store = EpisodicStore()
        for i in range(5):
            run(store.write_after_task(
                intent=f"task {i}",
                steps_summary=f"step {i}",
                result=f"result {i}",
            ))
        results = run(store.retrieve_episodic("", top_k=2))
        assert len(results) == 2
        # Most recent first
        assert results[0].intent == "task 4"

    def test_write_via_memory_manager_interface(self):
        store = EpisodicStore()
        run(store.write({
            "intent": "via write",
            "steps_summary": "used base class write",
            "result": "ok",
        }))
        results = run(store.read("via write"))
        assert len(results) == 1


# =====================================================================
# User Profile
# =====================================================================


class TestUserProfile:
    def test_load_empty_profile(self):
        state = UserProfileState()
        profile = run(state.load_user_profile())
        assert profile.preferences == {}
        assert profile.habits == []
        assert profile.avoidance_hints == []

    def test_update_preferences(self):
        state = UserProfileState()
        run(state.load_user_profile())
        profile = run(state.update_user_profile(
            preferences={"language": "python", "editor": "vim"},
        ))
        assert profile.preferences["language"] == "python"

    def test_update_habits_no_duplicates(self):
        state = UserProfileState()
        run(state.load_user_profile())
        run(state.update_user_profile(habits=["runs tests often"]))
        run(state.update_user_profile(habits=["runs tests often", "commits frequently"]))
        profile = state.profile
        assert profile.habits == ["runs tests often", "commits frequently"]

    def test_avoidance_hints(self):
        state = UserProfileState()
        run(state.load_user_profile())
        run(state.add_avoidance_hint("Do not delete user files"))
        run(state.add_avoidance_hint("Do not delete user files"))  # duplicate
        assert state.profile.avoidance_hints == ["Do not delete user files"]

    def test_record_error_pattern(self):
        state = UserProfileState()
        run(state.load_user_profile())
        run(state.record_error_pattern("nil dereference in handler"))
        assert any("nil dereference" in h for h in state.profile.avoidance_hints)

    def test_record_user_correction(self):
        state = UserProfileState()
        run(state.load_user_profile())
        run(state.record_user_correction("Use snake_case not camelCase"))
        assert any("snake_case" in h for h in state.profile.avoidance_hints)

    def test_write_and_read_via_base_interface(self):
        state = UserProfileState()
        run(state.write({"preferences": {"theme": "dark"}}))
        profile = run(state.read())
        assert profile.preferences["theme"] == "dark"

    def test_write_string_as_avoidance_hint(self):
        state = UserProfileState()
        run(state.write("Avoid using eval()"))
        assert "Avoid using eval()" in state.profile.avoidance_hints


# =====================================================================
# Semantic KB
# =====================================================================


class TestSemanticKB:
    def test_in_memory_stub_returns_empty(self):
        kb = InMemorySemanticKB()
        run(kb.write("key1", "Some value"))
        results = run(kb.query("anything", top_k=3))
        assert results == []

    def test_delete_existing(self):
        kb = InMemorySemanticKB()
        run(kb.write("key1", "val"))
        deleted = run(kb.delete("key1"))
        assert deleted is True
        deleted2 = run(kb.delete("key1"))
        assert deleted2 is False

    def test_abc_not_instantiable(self):
        with pytest.raises(TypeError):
            SemanticKB()


# =====================================================================
# Factory
# =====================================================================


class TestMemoryFactory:
    def test_create_working_memory(self):
        factory = MemoryFactory()
        wm = factory.create_working_memory()
        assert isinstance(wm, WorkingMemory)

    def test_create_episodic_store(self):
        factory = MemoryFactory()
        es = factory.create_episodic_store()
        assert isinstance(es, EpisodicStore)

    def test_create_user_profile(self):
        factory = MemoryFactory()
        up = factory.create_user_profile()
        assert isinstance(up, UserProfileState)

    def test_create_semantic_kb(self):
        factory = MemoryFactory()
        kb = factory.create_semantic_kb()
        assert isinstance(kb, InMemorySemanticKB)

    def test_factory_passes_config(self):
        cfg = MemoryConfig(working_memory_token_limit=2000)
        factory = MemoryFactory(config=cfg)
        wm = factory.create_working_memory()
        assert wm._config.working_memory_token_limit == 2000


# =====================================================================
# Lifecycle hooks
# =====================================================================


class TestLifecycleHooks:
    @pytest.mark.asyncio
    async def test_working_memory_lifecycle(self):
        wm = WorkingMemory()
        assert not wm._registered
        assert not wm._started
        await wm.on_register()
        assert wm._registered
        await wm.on_start()
        assert wm._started
        await wm.on_stop()
        assert not wm._started

    @pytest.mark.asyncio
    async def test_episodic_store_lifecycle(self):
        es = EpisodicStore()
        await es.on_register()
        await es.on_start()
        assert es._registered
        assert es._started

    @pytest.mark.asyncio
    async def test_user_profile_lifecycle(self):
        up = UserProfileState()
        await up.on_register()
        await up.on_start()
        assert up._registered
        assert up._started

    @pytest.mark.asyncio
    async def test_on_error_hook(self):
        wm = WorkingMemory()
        # on_error should not raise
        await wm.on_error(RuntimeError("test"))

    @pytest.mark.asyncio
    async def test_is_base_component(self):
        wm = WorkingMemory()
        es = EpisodicStore()
        up = UserProfileState()
        assert isinstance(wm, BaseComponent)
        assert isinstance(es, BaseComponent)
        assert isinstance(up, BaseComponent)

    @pytest.mark.asyncio
    async def test_is_memory_manager(self):
        wm = WorkingMemory()
        es = EpisodicStore()
        up = UserProfileState()
        assert isinstance(wm, MemoryManager)
        assert isinstance(es, MemoryManager)
        assert isinstance(up, MemoryManager)
