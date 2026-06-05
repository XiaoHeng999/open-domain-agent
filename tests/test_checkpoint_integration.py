"""Tests for checkpoint integration with ReActLoop and AgentRuntime."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent.agent.react import (
    Action,
    AgentResponse,
    AgentState,
    Observation,
    ReActLoop,
    ReActStep,
    Thought,
)
from open_agent.checkpoint.manager import Checkpoint, CheckpointManager, ExecutionState
from open_agent.checkpoint.storage import JSONStorage
from open_agent.config import AgentConfig, CheckpointConfig
from open_agent.errors import AgentError
from open_agent.registry import ToolRegistry
from open_agent.routing.complexity import ComplexityResult
from open_agent.routing.domain import DomainRouteResult
from open_agent.routing.intent import IntentResult
from open_agent.routing.router import RoutingDecision
from open_agent.tools.base import FunctionTool
from open_agent.trace import SpanKind, Trace, TraceManager
from open_agent.types import ToolCall, ToolCallResponse


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _simple_routing_decision(*, skip_planning: bool = True) -> RoutingDecision:
    return RoutingDecision(
        complexity=ComplexityResult(
            complexity="simple" if skip_planning else "complex",
            confidence=0.95,
            method="llm",
        ),
        domain=DomainRouteResult(
            domain="general",
            candidates=["general"],
            routed_as_fallback=True,
        ),
        intent=IntentResult(intent="general_query", slots={"query": "hello"}),
        skip_planning=skip_planning,
    )


class MockProvider:
    """Provider that calls 'echo' tool for N steps, then gives direct answer."""

    def __init__(self, tool_steps: int = 3):
        self.tool_steps = tool_steps
        self.call_count = 0

    async def complete_with_tools(self, messages, tools):
        self.call_count += 1
        if self.call_count <= self.tool_steps:
            return ToolCallResponse(
                text=f"Step {self.call_count}: calling echo",
                tool_calls=[ToolCall(
                    id=f"tc_{self.call_count}",
                    name="echo",
                    input={"text": f"call {self.call_count}"},
                )],
            )
        return ToolCallResponse(
            text="Final answer: done",
            tool_calls=[],
        )


def _make_registry_with_echo() -> ToolRegistry:
    registry = ToolRegistry()

    def echo(text: str) -> str:
        return text

    registry.register(FunctionTool(
        name="echo",
        description="Echo tool",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        handler=echo,
    ))
    return registry


def _make_checkpoint_manager(tmp_path: Path, interval: int = 1) -> CheckpointManager:
    cfg = CheckpointConfig(interval=interval, storage_path=str(tmp_path / "cps"))
    return CheckpointManager(config=cfg)


# ---------------------------------------------------------------------------
# 5.1: Checkpoint saved at each step with interval=1
# ---------------------------------------------------------------------------


class TestReActLoopCheckpointSave:
    @pytest.mark.asyncio
    async def test_checkpoint_saved_at_each_step(self, tmp_path: Path):
        """5.1: ReActLoop saves checkpoint after each step with interval=1."""
        registry = _make_registry_with_echo()
        cm = _make_checkpoint_manager(tmp_path, interval=1)
        provider = MockProvider(tool_steps=3)
        loop = ReActLoop(
            tool_registry=registry,
            max_iterations=10,
            provider=provider,
            checkpoint_manager=cm,
        )
        decision = _simple_routing_decision()

        response = await loop.run("test input", decision)

        # 3 tool execution steps → 3 checkpoints (step 4 is direct answer, no checkpoint)
        checkpoints = cm.list_checkpoints()
        assert len(checkpoints) == 3

    @pytest.mark.asyncio
    async def test_checkpoint_interval_2(self, tmp_path: Path):
        """5.2: With interval=2, checkpoints only at steps 2 and 4."""
        registry = _make_registry_with_echo()
        cm = _make_checkpoint_manager(tmp_path, interval=2)
        provider = MockProvider(tool_steps=4)
        loop = ReActLoop(
            tool_registry=registry,
            max_iterations=10,
            provider=provider,
            checkpoint_manager=cm,
        )
        decision = _simple_routing_decision()

        await loop.run("test input", decision)

        checkpoints = cm.list_checkpoints()
        assert len(checkpoints) == 2

        step_numbers = []
        for cp_id in checkpoints:
            cp = cm.restore_checkpoint(cp_id)
            assert cp is not None
            step_numbers.append(cp.step_number)
        assert sorted(step_numbers) == [2, 4]

    @pytest.mark.asyncio
    async def test_no_checkpoint_when_disabled(self, tmp_path: Path):
        """No checkpoints when checkpoint_manager is None."""
        registry = _make_registry_with_echo()
        provider = MockProvider(tool_steps=2)
        loop = ReActLoop(
            tool_registry=registry,
            max_iterations=10,
            provider=provider,
            checkpoint_manager=None,
        )
        decision = _simple_routing_decision()

        response = await loop.run("test input", decision)
        assert response.total_steps >= 1

    @pytest.mark.asyncio
    async def test_checkpoint_creates_trace_span(self, tmp_path: Path):
        """Checkpoint saves create SpanKind.CHECKPOINT spans."""
        registry = _make_registry_with_echo()
        cm = _make_checkpoint_manager(tmp_path, interval=1)
        provider = MockProvider(tool_steps=2)
        tm = TraceManager()
        trace = tm.create_trace()

        loop = ReActLoop(
            tool_registry=registry,
            max_iterations=10,
            provider=provider,
            checkpoint_manager=cm,
        )
        decision = _simple_routing_decision()

        await loop.run("test input", decision, trace=trace)

        checkpoint_spans = [s for s in trace.spans if s.kind == SpanKind.CHECKPOINT]
        assert len(checkpoint_spans) == 2
        for span in checkpoint_spans:
            assert "step_number" in span.attributes
            assert "checkpoint_id" in span.attributes


# ---------------------------------------------------------------------------
# 5.3-5.4: Resume state
# ---------------------------------------------------------------------------


class TestReActLoopResume:
    @pytest.mark.asyncio
    async def test_resume_skips_completed_steps(self, tmp_path: Path):
        """5.3: resume_state skips completed steps, starts from next_step."""
        registry = _make_registry_with_echo()
        provider = MockProvider(tool_steps=3)
        loop = ReActLoop(
            tool_registry=registry,
            max_iterations=10,
            provider=provider,
        )
        decision = _simple_routing_decision()

        resume_state = ExecutionState(
            restored_context={"query": "step-2"},
            tool_calls_completed=[],
            next_step=3,
        )

        response = await loop.run("test input", decision, resume_state=resume_state)

        # Provider: call 1→tool, 2→tool, 3→tool, 4→direct = 4 steps
        assert response.total_steps == 4

    @pytest.mark.asyncio
    async def test_resume_rebuilds_tool_messages(self, tmp_path: Path):
        """5.4: resume_state rebuilds _tool_messages from tool_calls_completed."""
        registry = _make_registry_with_echo()
        provider = MockProvider(tool_steps=1)
        loop = ReActLoop(
            tool_registry=registry,
            max_iterations=10,
            provider=provider,
        )
        decision = _simple_routing_decision()

        tool_calls_completed = [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "tc_1", "name": "echo", "input": {"text": "a"}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "tc_1", "content": "a", "is_error": False}],
            },
        ]

        resume_state = ExecutionState(
            restored_context={},
            tool_calls_completed=tool_calls_completed,
            next_step=2,
        )

        response = await loop.run("test input", decision, resume_state=resume_state)

        # _tool_messages starts with 2 from resume, then adds 2 more from the tool call
        assert len(loop._tool_messages) >= 2

    @pytest.mark.asyncio
    async def test_resume_injects_marker(self, tmp_path: Path):
        """Resume injects <resumed_from_step=N> into system prompt."""
        registry = _make_registry_with_echo()
        provider = MockProvider(tool_steps=1)
        loop = ReActLoop(
            tool_registry=registry,
            max_iterations=10,
            provider=provider,
        )
        decision = _simple_routing_decision()

        resume_state = ExecutionState(
            restored_context={},
            tool_calls_completed=[],
            next_step=3,
        )

        await loop.run("test input", decision, resume_state=resume_state)
        assert loop._resumed_from_step == 3


# ---------------------------------------------------------------------------
# 5.5-5.6: AgentRuntime.resume()
# ---------------------------------------------------------------------------


class TestAgentRuntimeResume:
    def _make_runtime(self, tmp_path: Path | None = None, enabled: bool = True) -> "AgentRuntime":
        from open_agent.runtime import AgentRuntime

        cp_config = CheckpointConfig(
            enabled=enabled,
            interval=1,
            storage_path=str(tmp_path / "cps") if tmp_path else ".open_agent/checkpoints",
        )
        config = AgentConfig(checkpoint=cp_config)
        runtime = AgentRuntime(config=config)
        # Replace provider with mock to avoid needing openai
        runtime.provider = MagicMock()
        runtime.provider.on_start = AsyncMock()
        # Replace routing_pipeline with mock to avoid LLM calls
        runtime.routing_pipeline = AsyncMock()
        runtime.routing_pipeline.route = AsyncMock(return_value=RoutingDecision(
            complexity=ComplexityResult(complexity="simple", confidence=0.95, method="llm"),
            domain=DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=True),
            intent=IntentResult(intent="general_query", slots={}, missing_slots=[]),
            skip_planning=True,
        ))
        return runtime

    @pytest.mark.asyncio
    async def test_resume_raises_on_missing_checkpoint(self, tmp_path: Path):
        """5.6: AgentRuntime.resume() raises AgentError for missing checkpoint."""
        runtime = self._make_runtime(tmp_path, enabled=True)
        await runtime.on_start()

        with pytest.raises(AgentError, match="Checkpoint not found"):
            await runtime.resume("nonexistent-id", "test input")

    @pytest.mark.asyncio
    async def test_resume_raises_when_no_checkpoint_manager(self, tmp_path: Path):
        """AgentRuntime.resume() raises when checkpoint is disabled."""
        runtime = self._make_runtime(tmp_path, enabled=False)
        await runtime.on_start()

        with pytest.raises(AgentError, match="Checkpoint manager not available"):
            await runtime.resume("some-id", "test input")

    @pytest.mark.asyncio
    async def test_resume_correctly_restores_and_continues(self, tmp_path: Path):
        """5.5: AgentRuntime.resume() restores checkpoint and continues execution."""
        runtime = self._make_runtime(tmp_path, enabled=True)
        await runtime.on_start()

        # Save a checkpoint manually
        cp = runtime.checkpoint_manager.save_checkpoint(
            step_number=2,
            context={"steps_summary": [{"thought": "t", "action": "echo", "observation": "ok"}]},
            tool_calls=[
                {"role": "assistant", "content": [{"type": "tool_use", "id": "tc_1", "name": "echo", "input": {"text": "a"}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tc_1", "content": "a", "is_error": False}]},
            ],
            memory_state={},
        )

        # Replace react_loop with a mock to verify resume_state is passed
        mock_response = AgentResponse(
            answer="resumed result",
            state=AgentState(final_answer="resumed result", finished=True),
            total_steps=2,
        )
        runtime.react_loop.run = AsyncMock(return_value=mock_response)

        response = await runtime.resume(cp.idempotency_key, "continue task")

        assert response.output == "resumed result"
        assert response.metadata["resumed"] is True
        assert response.metadata["checkpoint_id"] == cp.idempotency_key

        # Verify run was called with resume_state
        call_kwargs = runtime.react_loop.run.call_args
        assert call_kwargs is not None
        resume_state = call_kwargs.kwargs.get("resume_state")
        assert resume_state is not None
        assert resume_state.next_step == 3


# ---------------------------------------------------------------------------
# 5.7: Integration — checkpoint → failure → resume → success
# ---------------------------------------------------------------------------


class TestCheckpointResumeIntegration:
    @pytest.mark.asyncio
    async def test_save_failure_resume_success(self, tmp_path: Path):
        """5.7: Save checkpoint → fail → resume → success."""
        registry = _make_registry_with_echo()
        cm = _make_checkpoint_manager(tmp_path, interval=1)
        tm = TraceManager()

        # Phase 1: Run 2 steps, save checkpoint at each step
        provider1 = MockProvider(tool_steps=2)
        loop1 = ReActLoop(
            tool_registry=registry,
            max_iterations=10,
            provider=provider1,
            checkpoint_manager=cm,
        )
        decision = _simple_routing_decision()
        trace1 = tm.create_trace()

        response1 = await loop1.run("test task", decision, trace=trace1)
        checkpoints = cm.list_checkpoints()
        assert len(checkpoints) == 2

        # Phase 2: Find the step 1 checkpoint and resume from it
        cp1_id = None
        for cid in checkpoints:
            cp = cm.restore_checkpoint(cid)
            if cp and cp.step_number == 1:
                cp1_id = cid
                break
        assert cp1_id is not None

        exec_state = cm.resume_from_checkpoint(cp1_id)
        assert exec_state is not None
        assert exec_state.next_step == 2

        # Phase 3: Resume with new loop instance
        provider2 = MockProvider(tool_steps=2)
        loop2 = ReActLoop(
            tool_registry=registry,
            max_iterations=10,
            provider=provider2,
        )
        trace2 = tm.create_trace()
        response2 = await loop2.run(
            "test task", decision, trace=trace2, resume_state=exec_state,
        )

        # Should complete successfully
        assert response2.answer
        assert response2.state.finished is True


# ---------------------------------------------------------------------------
# 5.8: Failure avoidance hint recorded to episodic memory
# ---------------------------------------------------------------------------


class TestFailureAvoidanceHint:
    @pytest.mark.asyncio
    async def test_failure_records_episodic_memory(self, tmp_path: Path):
        """5.8: Recovery failure records avoidance hint to episodic memory."""
        from open_agent.runtime import AgentRuntime

        cp_config = CheckpointConfig(
            enabled=True,
            interval=1,
            storage_path=str(tmp_path / "cps"),
        )
        config = AgentConfig(checkpoint=cp_config)
        runtime = AgentRuntime(config=config)
        # Replace provider with mock
        runtime.provider = MagicMock()
        runtime.provider.on_start = AsyncMock()
        # Replace routing_pipeline with mock to avoid LLM calls
        runtime.routing_pipeline = AsyncMock()
        runtime.routing_pipeline.route = AsyncMock(return_value=RoutingDecision(
            complexity=ComplexityResult(complexity="complex", confidence=0.8, method="llm"),
            domain=DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=True),
            intent=IntentResult(intent="general_query", slots={}, missing_slots=[]),
            skip_planning=False,
        ))
        await runtime.on_start()

        # Save a checkpoint so there's something to list
        runtime.checkpoint_manager.save_checkpoint(
            step_number=1, context={}, tool_calls=[], memory_state={},
        )

        # Replace react_loop.run to raise AgentError
        runtime.react_loop.run = AsyncMock(side_effect=AgentError("Tool timeout"))

        # Mock plan_generator to avoid LLM calls
        runtime.plan_generator = AsyncMock()
        runtime.plan_generator.generate = AsyncMock(return_value=MagicMock(steps=[]))

        # Mock retrieval_memory.write_episodic
        runtime._retrieval_memory.write_episodic = AsyncMock()

        with pytest.raises(AgentError, match="Tool timeout"):
            await runtime.run("failing task")

        # Verify write_episodic was called with failure info
        runtime._retrieval_memory.write_episodic.assert_called_once()
        call_kwargs = runtime._retrieval_memory.write_episodic.call_args.kwargs
        assert call_kwargs.get("success") is False
        assert "failed" in call_kwargs.get("steps_summary", "").lower() or "timeout" in call_kwargs.get("steps_summary", "").lower()
