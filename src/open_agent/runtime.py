"""End-to-end Agent Runtime — integrates all modules into a unified lifecycle."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent
from open_agent.config import AgentConfig, load_config
from open_agent.errors import AgentError
from open_agent.registry import ToolRegistry
from open_agent.trace import SpanKind, Trace, TraceManager, setup_structured_logging
from open_agent.routing.router import RoutingPipeline, RoutingDecision
from open_agent.agent.react import ReActLoop
from open_agent.agent.planner import PlanGenerator
from open_agent.model import ProviderFactory
from open_agent.memory.factory import MemoryFactory
from open_agent.memory.runtime import RuntimeMemory
from open_agent.memory.profile import ProfileMemory
from open_agent.memory.retrieval import RetrievalMemory
from open_agent.memory.archive import ArchiveMemory
from open_agent.tools.todo import TodoManager, TODO_TOOL_SCHEMA
from open_agent.skills.registry import SkillRegistry, scan_builtin_skills, scan_workspace_skills
from open_agent.skills.matcher import SkillMatcher
from open_agent.safety import SafetyManager
from open_agent.safety.permission import PermissionGuard
from open_agent.sandbox.factory import SandboxFactory
from open_agent.monitoring.collector import AnomalyDetector, QualityScorer, FeedbackLoop, TraceCollector
from open_agent.checkpoint.manager import CheckpointManager
from open_agent.prompt.builder import PromptBuilder
from open_agent.hooks import HookEvent, HookManager
from open_agent.hooks.builtin import welcome_hook, pre_check_hook, audit_hook
from open_agent.mcp_integration import MCPServerManager, ServerConfig, TransportType
from open_agent.subagent.manager import SubagentManager
from open_agent.tools.subagent import SubagentTool

logger = logging.getLogger("open_agent")


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
        super().__init__()
        self.config = config or AgentConfig()

        # Core infrastructure
        self.trace_manager = TraceManager()
        self.tool_registry = ToolRegistry()
        self.skill_registry = SkillRegistry()

        # Prompt pipeline
        self.prompt_builder = PromptBuilder(
            tool_registry=self.tool_registry,
            workspace=self.config.workspace,
        )

        # Model provider
        self.provider = ProviderFactory.create(self.config.model)

        # Routing provider — independent lightweight model for routing, or reuse main
        routing_cfg = self.config.routing
        if routing_cfg.routing_provider or routing_cfg.routing_name:
            from open_agent.config import ModelConfig
            routing_model_cfg = ModelConfig(
                provider=routing_cfg.routing_provider or self.config.model.provider,
                name=routing_cfg.routing_name or self.config.model.name,
                temperature=0.0,
                max_tokens=200,
                api_key=routing_cfg.routing_api_key or self.config.model.api_key,
                base_url=routing_cfg.routing_base_url or self.config.model.base_url,
            )
            self._routing_provider = ProviderFactory.create(routing_model_cfg)
        else:
            self._routing_provider = self.provider

        # Routing
        self.routing_pipeline = RoutingPipeline(
            complexity_method=self.config.routing.complexity_method,
            fast_path_confidence=self.config.routing.fast_path_confidence,
            domains=self.config.routing.domains,
            routing_provider=self._routing_provider,
        )

        # Memory — 4-layer architecture
        self.memory_factory = MemoryFactory(self.config.memory)
        self._runtime_memory: RuntimeMemory | None = None
        self._profile_memory: ProfileMemory | None = None
        self._retrieval_memory: RetrievalMemory | None = None
        self._archive_memory: ArchiveMemory | None = None
        self._todo_manager: TodoManager | None = None

        # Agent core — will be wired in on_start after memory init
        self.react_loop = ReActLoop(
            tool_registry=self.tool_registry,
            max_iterations=10,
            provider=self.provider,
            prompt_builder=self.prompt_builder,
        )
        self.plan_generator = PlanGenerator(provider=self.provider)

        # Safety
        self.safety_manager = SafetyManager(self.config.safety, self.config.workspace)

        # Permission guard
        self.permission_guard = PermissionGuard(
            config=self.config.permissions,
            hitl=self.safety_manager.hitl,
        )

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

        # MCP server manager
        self._mcp_manager: MCPServerManager | None = None

        # Sub-agent manager
        self._subagent_manager: SubagentManager | None = None

    async def on_start(self) -> None:
        """Initialize all subsystems."""
        await super().on_start()

        # Activate structured logging
        self._logger = setup_structured_logging()

        # Provider
        await self.provider.on_start()

        # Memory — create 4 layers
        self._runtime_memory = self.memory_factory.create_runtime_memory()
        self._profile_memory = self.memory_factory.create_profile_memory()
        self._retrieval_memory = self.memory_factory.create_retrieval_memory()
        self._archive_memory = self.memory_factory.create_archive_memory()
        self._todo_manager = TodoManager()

        # Register all built-in tools via scan_builtin_tools
        from open_agent.registry import scan_builtin_tools
        self.tool_registry = ToolRegistry(
            safety_manager=self.safety_manager,
            max_tool_result_tokens=self.config.memory.max_tool_result_tokens,
            permission_guard=self.permission_guard,
            runtime_memory=self._runtime_memory,
        )
        scan_builtin_tools(
            self.tool_registry, self.config,
            react_loop=self.react_loop,
            runtime=self,
            sandbox=self.sandbox,
        )

        # Replace ExecTool with sandbox-injected version
        await self._inject_sandbox_to_exec_tool()

        # Wire todo manager into the TodoTool instance
        from open_agent.tools.todo import TodoTool
        todo_tool = self.tool_registry.get("todo")
        if isinstance(todo_tool, TodoTool):
            todo_tool._todo_manager = self._todo_manager

        # Re-create prompt builder with new registry
        from open_agent.prompt.builder import PromptBuilder
        self.prompt_builder = PromptBuilder(
            tool_registry=self.tool_registry,
            workspace=self.config.workspace,
        )

        # Wire memory + todo into ReActLoop
        self.react_loop._registry = self.tool_registry
        self.react_loop._runtime_memory = self._runtime_memory
        self.react_loop._todo_manager = self._todo_manager
        self.react_loop._staleness_rounds = self.config.memory.todo_staleness_rounds
        self.react_loop._prompt_builder = self.prompt_builder
        self.react_loop._profile_memory = self._profile_memory

        # Hooks — create HookManager and register built-in hooks
        if self.config.hooks.enabled:
            self._hook_manager = HookManager(enabled=True)
            if self.config.hooks.welcome_enabled:
                self._hook_manager.register(
                    HookEvent.SESSION_START, welcome_hook, priority=10,
                )
            self._hook_manager.register(
                HookEvent.TOOL_BEFORE, pre_check_hook, priority=10,
            )
            self._hook_manager.register(
                HookEvent.TOOL_AFTER, audit_hook, priority=10,
            )
            self.react_loop._hook_manager = self._hook_manager

            # Fire SESSION_START — inject welcome text into system prompt
            session_results = await self._hook_manager.fire(
                HookEvent.SESSION_START, {},
            )
            welcome_parts = [
                hr.content for hr in session_results if hr.content
            ]
            if welcome_parts:
                self._session_welcome = "\n".join(welcome_parts)
                self.react_loop._session_welcome = self._session_welcome
            else:
                self._session_welcome = ""
        else:
            self._hook_manager = None
            self._session_welcome = ""

        # Skills
        scan_builtin_skills(self.skill_registry)
        scan_workspace_skills(self.skill_registry, self.config.workspace)

        # Checkpoint
        if self.config.checkpoint.enabled:
            from open_agent.checkpoint.storage import JSONStorage
            from open_agent.checkpoint.manager import CheckpointManager
            storage = JSONStorage(self.config.checkpoint.storage_path)
            self.checkpoint_manager = CheckpointManager(
                config=self.config.checkpoint,
                storage=storage,
            )
            self.react_loop._checkpoint_manager = self.checkpoint_manager

        # MCP — start servers if configured
        mcp_config = self.config.mcp
        if mcp_config.servers:
            self._mcp_manager = MCPServerManager(self.tool_registry)
            import asyncio as _asyncio
            import logging as _logging
            _logger = _logging.getLogger("open_agent")

            async def _start_mcp_server(srv_cfg):
                server_config = ServerConfig(
                    server_id=srv_cfg.server_id,
                    transport=TransportType(srv_cfg.transport),
                    command=srv_cfg.command,
                    url=srv_cfg.url,
                    headers=srv_cfg.headers,
                    health_check_interval=srv_cfg.health_check_interval,
                )
                await self._mcp_manager.register_server(server_config)
                try:
                    await _asyncio.wait_for(
                        self._mcp_manager.start_server(srv_cfg.server_id),
                        timeout=mcp_config.connect_timeout,
                    )
                except _asyncio.TimeoutError:
                    _logger.warning("MCP server %s connect timeout", srv_cfg.server_id)
                except Exception as exc:
                    _logger.warning("MCP server %s start failed: %s", srv_cfg.server_id, exc)

            await _asyncio.gather(
                *[_start_mcp_server(srv) for srv in mcp_config.servers],
                return_exceptions=True,
            )

        # Register MCPClientTool if MCP manager is available
        if self._mcp_manager is not None:
            from open_agent.tools.mcp_client import MCPClientTool
            if not self.tool_registry.has("mcp_client"):
                self.tool_registry.register(MCPClientTool(mcp_manager=self._mcp_manager))

        # Sub-agent: initialize manager and register SubagentTool
        subagent_cfg = self.config.subagent
        if subagent_cfg.enabled:
            self._subagent_manager = SubagentManager(
                provider=self.provider,
                tool_registry=self.tool_registry,
                config=subagent_cfg,
                prompt_builder=self.prompt_builder,
                workspace=self.config.workspace,
            )
            subagent_tool = SubagentTool(
                manager=self._subagent_manager,
            )
            self.tool_registry.register(subagent_tool)

    async def _inject_sandbox_to_exec_tool(self) -> None:
        """Replace ExecTool with a sandbox-injected version, with fallback."""
        import logging
        from open_agent.tools.shell import ExecTool
        from open_agent.sandbox.factory import SubprocessSandbox

        sandbox = self.sandbox
        if sandbox is not None:
            try:
                if hasattr(sandbox, "on_start"):
                    await sandbox.on_start()
            except Exception as exc:
                logger = logging.getLogger("open_agent")
                logger.warning(
                    "Sandbox startup failed (%s), falling back to subprocess: %s",
                    type(sandbox).__name__, exc,
                )
                sandbox = SubprocessSandbox()

        if self.tool_registry.has("exec"):
            workspace = self.config.workspace
            old_tool = self.tool_registry.get("exec")
            self.tool_registry.unregister("exec")
            self.tool_registry.register(ExecTool(
                workspace=workspace,
                timeout=old_tool._timeout if hasattr(old_tool, "_timeout") else 30,
                max_output_chars=old_tool._max_output_chars if hasattr(old_tool, "_max_output_chars") else 10000,
                sandbox=sandbox,
            ))

    async def on_stop(self) -> None:
        """Clean up all subsystems."""
        # Cascading stop: terminate all active sub-agents
        if self._subagent_manager:
            await self._subagent_manager.stop_all()
        if self._mcp_manager:
            for server_info in self._mcp_manager.list_servers():
                await self._mcp_manager.stop_server(server_info["server_id"])
        if self._profile_memory:
            self._profile_memory.close()
        if self.sandbox:
            await self.sandbox.on_stop()
        await super().on_stop()

    async def run(self, user_input: str) -> AgentResponse:
        """Execute a task end-to-end: route → plan → react → respond."""
        start_time = time.time()

        # Create trace
        trace = self.trace_manager.create_trace(metadata={"user_input": user_input})

        # Archive: record user message
        if self._archive_memory:
            self._archive_memory.write_record({
                "type": "message",
                "role": "user",
                "content": user_input,
            })

        # Stage 1: Routing
        # Build routing history from runtime_memory (last 4 messages ≈ 2 turns)
        routing_history: list[dict[str, str]] | None = None
        if self._runtime_memory and self._runtime_memory._messages:
            recent = self._runtime_memory._messages[-4:]
            routing_history = [{"role": m.role, "content": m.content} for m in recent]

        routing_decision = await self.routing_pipeline.route(
            user_input, trace=trace, history=routing_history,
        )

        # 5.3 Missing slots clarification — short-circuit only for simple tasks
        # For medium/complex tasks, missing_slots is injected as context hint (see below)
        if routing_decision.intent.missing_slots and routing_decision.complexity.complexity == "simple":
            from open_agent.routing.intent import IntentParser
            parser = IntentParser()
            clarification = parser.generate_clarification(routing_decision.intent.missing_slots)
            duration_ms = (time.time() - start_time) * 1000
            return AgentResponse(
                output=clarification,
                trace_id=trace.trace_id,
                routing=routing_decision,
                duration_ms=duration_ms,
                metadata={"clarification": True, "missing_slots": routing_decision.intent.missing_slots},
            )

        # Stage 2: Skills matching
        matched_skills = self.skill_matcher.get_skills_for_prompt(
            routing_decision.domain.domain, user_input
        )
        self.react_loop._matched_skills = matched_skills

        # Stage 3: Build prompt context with all memory layers
        prompt_context: dict[str, Any] = {
            "matched_skills": matched_skills,
        }

        # Inject session welcome text from hooks
        if getattr(self, "_session_welcome", ""):
            prompt_context["session_welcome"] = self._session_welcome

        # 5.1 Inject domain system_prompt into prompt context
        if routing_decision.domain.system_prompt:
            prompt_context["domain_system_prompt"] = routing_decision.domain.system_prompt
        if self._profile_memory:
            profile_text = self._profile_memory.get_injection_text()
            if profile_text:
                prompt_context["user_profile"] = profile_text
        if self._todo_manager:
            plan_text = self._todo_manager.render()
            if plan_text:
                prompt_context["todo_plan"] = plan_text
        if self._retrieval_memory:
            retrieval_results = await self._retrieval_memory.query(user_input)
            if retrieval_results:
                formatted = "\n".join(
                    f"- [{r['metadata'].get('layer', '')}] {r['text']} (score: {r['score']:.2f})"
                    for r in retrieval_results
                )
                prompt_context["retrieval_results"] = formatted

        # 5.2 Planning: generate plan for complex tasks
        if not routing_decision.skip_planning:
            plan = await self.plan_generator.generate(user_input, trace=trace)
            if plan.steps:
                plan_text = "Generated plan:\n" + "\n".join(
                    f"{i+1}. {step}" for i, step in enumerate(plan.steps)
                )
                prompt_context["plan"] = plan_text

        # Stage 4: ReAct execution
        # Pass missing_slots hint to ReActLoop for non-simple tasks
        if routing_decision.intent.missing_slots and routing_decision.complexity.complexity != "simple":
            slot_list = ", ".join(routing_decision.intent.missing_slots)
            self.react_loop._missing_slots_hint = (
                f"路由层检测到以下参数可能缺失: {slot_list}。"
                "如果可以通过工具或常识合理推断，请直接执行任务。"
                "如果确实无法推断，请向用户追问。"
            )
        else:
            self.react_loop._missing_slots_hint = ""

        try:
            response = await self.react_loop.run(
                user_input=user_input,
                routing_decision=routing_decision,
                trace=trace,
            )
        except AgentError as exc:
            # Record failure pattern to episodic memory if checkpoint exists
            if self.checkpoint_manager and self._retrieval_memory:
                checkpoints = self.checkpoint_manager.list_checkpoints()
                if checkpoints:
                    tools_used = list({
                        block["name"]
                        for s in self.react_loop._tool_messages
                        if s.get("role") == "assistant"
                        for block in s.get("content", [])
                        if block.get("type") == "tool_use"
                    }) if self.react_loop._tool_messages else []
                    await self._retrieval_memory.write_episodic(
                        intent=routing_decision.intent.intent if routing_decision else "unknown",
                        steps_summary=f"Failed: {exc}. Tools used: {', '.join(tools_used)}",
                        result="failure",
                        success=False,
                    )
            raise

        # Update runtime memory with this turn
        if self._runtime_memory:
            await self._runtime_memory.add_message("user", user_input)
            await self._runtime_memory.add_message("assistant", response.answer)

        # Archive: record assistant response
        if self._archive_memory:
            self._archive_memory.write_record({
                "type": "message",
                "role": "assistant",
                "content": response.answer,
            })

        # Stage 5: Monitoring
        anomalies = self.anomaly_detector.detect(trace)
        quality = self.quality_scorer.score(trace)

        # Stage 6: Memory updates — episodic + profile
        if self._retrieval_memory:
            await self._retrieval_memory.write_episodic(
                intent=routing_decision.intent.intent,
                steps_summary=f"Executed {len(trace.spans)} operations",
                result=response.answer,
                success=True,
            )

        # Feedback loop → profile avoidance hints
        for alert in anomalies:
            hint = self.feedback_loop.generate_avoidance_hint(
                alert.alert_type, alert.details
            )
            if self._profile_memory:
                await self._profile_memory.add_avoidance_hint(hint["hint"])

        # Cleanup skills
        for skill_info in matched_skills:
            self.skill_matcher.cleanup(routing_decision.domain.domain, user_input)

        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "runtime.done trace_id=%s domain=%s intent=%s steps=%d duration=%.0fms",
            trace.trace_id,
            routing_decision.domain.domain,
            routing_decision.intent.intent,
            response.total_steps,
            duration_ms,
        )

        return AgentResponse(
            output=response.answer,
            trace_id=trace.trace_id,
            routing=routing_decision,
            quality_score=quality.score,
            anomalies=[{"type": a.alert_type, "message": a.message} for a in anomalies],
            duration_ms=duration_ms,
            metadata={
                "matched_skills": [s["name"] for s in matched_skills],
                "total_steps": response.total_steps,
                "steps": [
                    {
                        "thought": step.thought.content if step.thought else None,
                        "action": f"{step.action.tool_name}({step.action.args})" if step.action else None,
                        "observation": step.observation.content if step.observation else None,
                    }
                    for step in response.state.steps
                ],
            },
        )

    async def resume(self, checkpoint_id: str, user_input: str) -> AgentResponse:
        """Resume execution from a saved checkpoint."""
        start_time = time.time()

        if self.checkpoint_manager is None:
            raise AgentError("Checkpoint manager not available")

        execution_state = self.checkpoint_manager.resume_from_checkpoint(checkpoint_id)
        if execution_state is None:
            raise AgentError(f"Checkpoint not found: {checkpoint_id}")

        trace = self.trace_manager.create_trace(
            metadata={"user_input": user_input, "resumed_from": checkpoint_id},
        )

        # Rebuild routing decision
        routing_decision = await self.routing_pipeline.route(user_input, trace=trace)

        response = await self.react_loop.run(
            user_input=user_input,
            routing_decision=routing_decision,
            trace=trace,
            resume_state=execution_state,
        )

        duration_ms = (time.time() - start_time) * 1000

        return AgentResponse(
            output=response.answer,
            trace_id=trace.trace_id,
            routing=routing_decision,
            duration_ms=duration_ms,
            metadata={"resumed": True, "checkpoint_id": checkpoint_id},
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
