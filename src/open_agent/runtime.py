"""End-to-end Agent Runtime — integrates all modules into a unified lifecycle."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent
from open_agent.config import AgentConfig, load_config
from open_agent.registry import ToolRegistry
from open_agent.trace import SpanKind, Trace, TraceManager
from open_agent.routing.router import RoutingPipeline, RoutingDecision
from open_agent.agent.react import ReActLoop
from open_agent.agent.planner import PlanGenerator
from open_agent.memory.factory import MemoryFactory
from open_agent.memory.working import WorkingMemory
from open_agent.memory.episodic import EpisodicStore
from open_agent.memory.profile import UserProfileState
from open_agent.skills.registry import SkillRegistry, scan_builtin_skills, scan_workspace_skills
from open_agent.skills.matcher import SkillMatcher
from open_agent.safety import SafetyManager
from open_agent.sandbox.factory import SandboxFactory
from open_agent.monitoring.collector import AnomalyDetector, QualityScorer, FeedbackLoop, TraceCollector
from open_agent.checkpoint.manager import CheckpointManager


@dataclass
class AgentResponse:
    """Complete agent response with trace and metadata."""

    output: str
    trace_id: str
    routing: RoutingDecision | None = None
    quality_score: float | None = None
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRuntime(BaseComponent):
    """End-to-end Agent Runtime — unified lifecycle for all modules."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()

        # Core infrastructure
        self.trace_manager = TraceManager()
        self.tool_registry = ToolRegistry()
        self.skill_registry = SkillRegistry()

        # Routing
        self.routing_pipeline = RoutingPipeline(
            complexity_method=self.config.routing.complexity_method,
            fast_path_confidence=self.config.routing.fast_path_confidence,
        )

        # Agent core
        self.react_loop = ReActLoop(tool_registry=self.tool_registry, max_iterations=10)
        self.plan_generator = PlanGenerator()

        # Memory
        self.memory_factory = MemoryFactory(self.config.memory)
        self._working_memory: WorkingMemory | None = None
        self._episodic_store: EpisodicStore | None = None
        self._user_profile: UserProfileState | None = None

        # Safety
        self.safety_manager = SafetyManager(self.config.safety, self.config.workspace)

        # Sandbox
        self.sandbox = SandboxFactory.create(self.config.sandbox)

        # Skills
        self.skill_matcher = SkillMatcher(self.skill_registry)

        # Monitoring
        self.anomaly_detector = AnomalyDetector()
        self.quality_scorer = QualityScorer()
        self.feedback_loop = FeedbackLoop()
        self.trace_collector = TraceCollector(self.trace_manager)

        # Checkpoint
        self.checkpoint_manager: CheckpointManager | None = None

    async def on_start(self) -> None:
        """Initialize all subsystems."""
        await super().on_start()

        # Memory
        self._working_memory = self.memory_factory.create_working_memory()
        self._episodic_store = self.memory_factory.create_episodic_store()
        self._user_profile = self.memory_factory.create_user_profile()

        # Skills
        scan_builtin_skills(self.skill_registry)
        scan_workspace_skills(self.skill_registry, self.config.workspace)

        # Checkpoint
        if self.config.checkpoint.enabled:
            from open_agent.checkpoint.storage import JSONStorage
            from open_agent.checkpoint.manager import CheckpointManager
            storage = JSONStorage(self.config.checkpoint.storage_path)
            self.checkpoint_manager = CheckpointManager(
                storage=storage,
                interval=self.config.checkpoint.interval,
            )

    async def on_stop(self) -> None:
        """Clean up all subsystems."""
        if self.sandbox:
            await self.sandbox.on_stop()
        await super().on_stop()

    async def run(self, user_input: str) -> AgentResponse:
        """Execute a task end-to-end: route → plan → react → respond."""
        start_time = time.time()

        # Create trace
        trace = self.trace_manager.create_trace(metadata={"user_input": user_input})

        # Stage 1: Routing
        routing_decision = await self.routing_pipeline.route(user_input, trace=trace)

        # Stage 2: Skills matching
        matched_skills = self.skill_matcher.get_skills_for_prompt(
            routing_decision.domain.domain, user_input
        )

        # Stage 3: ReAct execution
        response = await self.react_loop.run(
            user_input=user_input,
            routing_decision=routing_decision,
            trace=trace,
        )

        # Stage 4: Monitoring
        anomalies = self.anomaly_detector.detect(trace)
        quality = self.quality_scorer.score(trace)

        # Stage 5: Memory updates
        if self._episodic_store:
            await self._episodic_store.write_after_task({
                "intent": routing_decision.intent.intent,
                "steps_summary": f"Executed {len(trace.spans)} operations",
                "result": response.output,
                "user_feedback": None,
            })

        # Feedback loop
        for alert in anomalies:
            hint = self.feedback_loop.generate_avoidance_hint(
                alert.alert_type, alert.details
            )
            if self._user_profile:
                self._user_profile.update_profile({"avoidance_hints": [hint]})

        # Cleanup skills
        for skill_info in matched_skills:
            self.skill_matcher.cleanup(routing_decision.domain.domain, user_input)

        duration_ms = (time.time() - start_time) * 1000

        return AgentResponse(
            output=response.output,
            trace_id=trace.trace_id,
            routing=routing_decision,
            quality_score=quality.score,
            anomalies=[{"type": a.alert_type, "message": a.message} for a in anomalies],
            duration_ms=duration_ms,
            metadata={"matched_skills": [s["name"] for s in matched_skills]},
        )

    async def run_eval_scenario(self, scenario) -> dict[str, Any]:
        """Run an evaluation scenario and return results."""
        from open_agent.eval.replay import TraceReplayEngine

        response = await self.run(scenario.input)
        trace = self.trace_manager.get_trace(response.trace_id)

        if trace:
            engine = TraceReplayEngine()
            replay_result = engine.replay(trace, scenario)
            return {
                "scenario": scenario.name,
                "passed": replay_result.passed,
                "tool_call_accuracy": replay_result.tool_call_accuracy,
                "quality_score": response.quality_score,
            }

        return {"scenario": scenario.name, "passed": False, "error": "No trace"}
