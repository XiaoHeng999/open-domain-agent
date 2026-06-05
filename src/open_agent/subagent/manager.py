"""SubagentManager — lifecycle, concurrency, and result management."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from open_agent.agent.react import ReActLoop
from open_agent.config import SubagentConfig
from open_agent.prompt.builder import PromptBuilder
from open_agent.registry import ToolRegistry
from open_agent.subagent.presets import merge_presets
from open_agent.subagent.types import SubagentPreset, SubagentResult
from open_agent.tools.base import Tool

logger = logging.getLogger("open_agent")


@dataclass
class _ActiveSubagent:
    """Tracks a running sub-agent."""

    agent_id: str
    task: asyncio.Task
    preset: SubagentPreset
    start_time: float = field(default_factory=time.time)


class SubagentManager:
    """Manages sub-agent lifecycle: presets, concurrency, results, cascading stop."""

    def __init__(
        self,
        provider: Any,
        tool_registry: ToolRegistry,
        config: SubagentConfig,
        prompt_builder: PromptBuilder | None = None,
        workspace: str = ".",
    ) -> None:
        self._provider = provider
        self._parent_registry = tool_registry
        self._config = config
        self._prompt_builder = prompt_builder
        self._workspace = workspace

        # Build merged presets: built-in + user overrides
        user_preset_dicts = [p.model_dump() for p in config.presets]
        self._presets = merge_presets(user_preset_dicts)

        # Active sub-agents: agent_id -> _ActiveSubagent
        self._active: dict[str, _ActiveSubagent] = {}

        # Completed results: agent_id -> SubagentResult
        self._results: dict[str, SubagentResult] = {}

        # Per-parent child tracking: parent_id -> set of active child agent_ids
        self._children_by_parent: dict[str, set[str]] = {}

        # Concurrency semaphore
        self._semaphore = asyncio.Semaphore(config.max_concurrent)

    # -- Preset lookup (3.2) -----------------------------------------------

    def get_preset(self, subagent_type: str) -> SubagentPreset:
        """Look up a preset by name, falling back to 'explore'."""
        preset = self._presets.get(subagent_type)
        if preset is None:
            logger.warning("Unknown subagent_type '%s', falling back to 'explore'", subagent_type)
            preset = self._presets["explore"]
        return preset

    # -- Restricted ToolRegistry (3.3) -------------------------------------

    def _build_restricted_registry(self, preset: SubagentPreset) -> ToolRegistry:
        """Build a ToolRegistry containing only the preset's allowed tools.

        Empty allowed_tools means all tools except 'task'.
        """
        registry = ToolRegistry(
            safety_manager=self._parent_registry._safety_manager,
            max_tool_result_tokens=self._parent_registry._max_tool_result_tokens,
            permission_guard=self._parent_registry._permission_guard,
        )

        for tool in self._parent_registry.list_tools():
            # Always exclude 'task' to prevent nested spawning
            if tool.name == "task":
                continue
            # Empty list = all tools (except task)
            if not preset.allowed_tools or tool.name in preset.allowed_tools:
                registry.register(tool)

        return registry

    # -- Create sub-agent ReActLoop (3.4) ----------------------------------

    def _create_react_loop(
        self,
        preset: SubagentPreset,
        max_turns: int,
        restricted_registry: ToolRegistry,
    ) -> ReActLoop:
        """Create an isolated ReActLoop for the sub-agent."""
        pb = PromptBuilder(
            tool_registry=restricted_registry,
            workspace=self._workspace,
        )

        return ReActLoop(
            tool_registry=restricted_registry,
            max_iterations=max_turns,
            provider=self._provider,
            prompt_builder=pb,
        )

    # -- Concurrency control (3.5) -----------------------------------------

    @property
    def active_count(self) -> int:
        return len(self._active)

    async def _acquire_slot(self) -> None:
        """Wait for an available concurrency slot."""
        await self._semaphore.acquire()

    def _release_slot(self) -> None:
        self._semaphore.release()

    # -- Agent ID generation (3.6) -----------------------------------------

    def _generate_agent_id(self) -> str:
        return uuid.uuid4().hex[:12]

    # -- Core execution ----------------------------------------------------

    async def run_subagent(
        self,
        prompt: str,
        subagent_type: str = "explore",
        max_turns: int | None = None,
        trace: Any = None,
        agent_id: str | None = None,
        parent_id: str | None = None,
    ) -> SubagentResult:
        """Create and run a sub-agent synchronously (awaitable)."""
        preset = self.get_preset(subagent_type)
        effective_max_turns = max_turns or preset.max_turns or self._config.default_max_turns

        # Enforce max_children per parent
        if parent_id is not None:
            children = self._children_by_parent.setdefault(parent_id, set())
            if len(children) >= self._config.max_children:
                return SubagentResult(
                    agent_id=agent_id or self._generate_agent_id(),
                    answer=f"Per-parent subagent limit (max_children={self._config.max_children}) reached for parent {parent_id}",
                    success=False,
                    duration_ms=0,
                )

        await self._acquire_slot()
        if agent_id is None:
            agent_id = self._generate_agent_id()
        start_time = time.time()

        # Register child under parent
        if parent_id is not None:
            self._children_by_parent.setdefault(parent_id, set()).add(agent_id)

        restricted_registry = self._build_restricted_registry(preset)
        loop = self._create_react_loop(preset, effective_max_turns, restricted_registry)

        # Override system prompt if preset has one
        if preset.system_prompt:
            loop._domain_system_prompt = preset.system_prompt

        active = _ActiveSubagent(
            agent_id=agent_id,
            task=asyncio.current_task(),
            preset=preset,
            start_time=start_time,
        )
        self._active[agent_id] = active

        try:
            from open_agent.routing.router import RoutingDecision
            from open_agent.routing.domain import DomainRouteResult
            from open_agent.routing.intent import IntentResult
            from open_agent.routing.complexity import ComplexityResult

            complexity = ComplexityResult(complexity="simple", confidence=1.0, method="llm")
            domain_result = DomainRouteResult(domain="general", candidates=["general"], routed_as_fallback=False)
            intent_result = IntentResult(intent="subagent_task")
            routing = RoutingDecision(
                complexity=complexity,
                domain=domain_result,
                intent=intent_result,
                skip_planning=True,
            )

            response = await loop.run(
                user_input=prompt,
                routing_decision=routing,
                trace=trace,
            )

            duration_ms = (time.time() - start_time) * 1000
            result = SubagentResult(
                agent_id=agent_id,
                answer=response.answer,
                success=True,
                duration_ms=duration_ms,
            )
        except asyncio.CancelledError:
            duration_ms = (time.time() - start_time) * 1000
            result = SubagentResult(
                agent_id=agent_id,
                answer="Subagent was cancelled",
                success=False,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("Subagent %s failed: %s", agent_id, exc)
            result = SubagentResult(
                agent_id=agent_id,
                answer=f"Subagent error: {exc}",
                success=False,
                duration_ms=duration_ms,
            )
        finally:
            self._active.pop(agent_id, None)
            self._results[agent_id] = result
            self._release_slot()

            # Remove child from parent tracking
            if parent_id is not None and parent_id in self._children_by_parent:
                self._children_by_parent[parent_id].discard(agent_id)
                if not self._children_by_parent[parent_id]:
                    del self._children_by_parent[parent_id]

        return result

    async def start_background(
        self,
        prompt: str,
        subagent_type: str = "explore",
        max_turns: int | None = None,
        trace: Any = None,
    ) -> str:
        """Start a sub-agent in the background. Returns agent_id immediately."""
        agent_id = self._generate_agent_id()

        async def _run():
            await self.run_subagent(
                prompt, subagent_type, max_turns, trace,
                agent_id=agent_id,
            )

        task = asyncio.create_task(_run())
        # Pre-register in active so stop_all can cancel it immediately
        preset = self.get_preset(subagent_type)
        self._active[agent_id] = _ActiveSubagent(
            agent_id=agent_id, task=task, preset=preset,
        )

        return agent_id

    # -- Cascading stop (3.7) ----------------------------------------------

    async def stop_all(self, timeout: float = 5.0) -> None:
        """Cancel all active sub-agents with timeout."""
        # Always clear child tracking regardless of active state
        self._children_by_parent.clear()

        if not self._active:
            return

        tasks = [entry.task for entry in self._active.values()]
        for task in tasks:
            task.cancel()

        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("stop_all: some sub-agents did not cancel within timeout")

        self._active.clear()

    # -- Result query (3.8) ------------------------------------------------

    def get_result(self, agent_id: str) -> dict[str, Any]:
        """Query sub-agent result by agent_id."""
        if agent_id in self._results:
            r = self._results[agent_id]
            return {
                "status": "completed",
                "answer": r.answer,
                "success": r.success,
                "duration_ms": r.duration_ms,
            }
        if agent_id in self._active:
            return {"status": "running"}
        return {"status": "not_found"}
