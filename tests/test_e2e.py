"""End-to-end integration tests and examples."""

from __future__ import annotations

import asyncio
import pytest

from open_agent.config import AgentConfig, CheckpointConfig
from open_agent.registry import ToolRegistry
from open_agent.trace import SpanKind, TraceManager
from open_agent.routing.router import RoutingPipeline
from open_agent.agent.react import ReActLoop
from open_agent.decorators import tool_schema
from open_agent.eval.scenario import Scenario, StepAssertion
from open_agent.eval.replay import TraceReplayEngine
from open_agent.eval.metrics import compute_metrics
from open_agent.eval.dataset import EvalDataset, trace_to_eval_case
from open_agent.safety import SafetyManager
from open_agent.safety.command import CommandSafetyChecker
from open_agent.safety.ssrf import SSRFProtector
from open_agent.skills.registry import SkillRegistry, scan_builtin_skills
from open_agent.monitoring.collector import AnomalyDetector, QualityScorer
from open_agent.memory.factory import MemoryFactory
from open_agent.memory.working import WorkingMemory


# --- 12.2: Minimal runnable example ---

class TestMinimalRun:
    @pytest.mark.asyncio
    async def test_hello_task(self):
        """CLI `agent run "hello"` -> route -> ReAct -> return."""
        registry = ToolRegistry()
        pipeline = RoutingPipeline()
        loop = ReActLoop(tool_registry=registry, max_iterations=3)

        decision = await pipeline.route("hello")
        assert decision.skip_planning  # simple task

        response = await loop.run(
            user_input="hello",
            routing_decision=decision,
        )
        assert response.answer  # got some output
        assert response.total_steps >= 1

    @pytest.mark.asyncio
    async def test_with_tool(self):
        """Simple task using a registered tool."""
        registry = ToolRegistry()

        @tool_schema(name="greet")
        async def greet(name: str) -> str:
            """Greet someone.
            Args:
                name: Person's name
            """
            return f"Hello, {name}!"

        registry.register("greet", handler=greet)

        pipeline = RoutingPipeline()
        decision = await pipeline.route("greet John")
        loop = ReActLoop(tool_registry=registry, max_iterations=3)

        response = await loop.run(
            user_input="greet John",
            routing_decision=decision,
        )
        assert response.answer


# --- 12.3: Complex task example ---

class TestComplexTask:
    @pytest.mark.asyncio
    async def test_complex_routing_and_plan(self):
        """Three-stage routing -> Planning -> ReAct."""
        registry = ToolRegistry()
        pipeline = RoutingPipeline()
        loop = ReActLoop(tool_registry=registry, max_iterations=5)

        decision = await pipeline.route("搜索竞品A数据，搜索竞品B数据，对比分析，生成报告")
        assert not decision.skip_planning  # complex task

        from open_agent.agent.planner import PlanGenerator
        generator = PlanGenerator()
        plan = await generator.generate("搜索竞品A数据，搜索竞品B数据，对比分析，生成报告")

        assert len(plan.steps) >= 1  # has a plan

        response = await loop.run(
            user_input="搜索竞品A数据，搜索竞品B数据，对比分析，生成报告",
            routing_decision=decision,
        )
        assert response.answer


# --- 12.4: Error recovery example ---

class TestErrorRecovery:
    @pytest.mark.asyncio
    async def test_error_recovery_integration(self):
        """Tool error recovery with different error types."""
        from open_agent.recovery.classifier import ErrorClassifier, ToolErrorType
        from open_agent.recovery.engine import RecoveryPolicyRegistry

        classifier = ErrorClassifier()
        from open_agent.errors import ParameterError, ServiceError

        # Classify errors
        assert classifier.classify(ParameterError("bad param")) == ToolErrorType.ParameterError
        assert classifier.classify(ServiceError("timeout")) == ToolErrorType.ServiceError

        # Custom strategy
        registry = RecoveryPolicyRegistry()
        from open_agent.recovery.strategies import RecoveryStrategy, RecoveryResult

        class CustomStrategy(RecoveryStrategy):
            async def execute(self, error, context):
                return RecoveryResult(status="recovered", strategy="custom")

        registry.register(ToolErrorType.ServiceError, CustomStrategy())
        chain = registry.get_chain(ToolErrorType.ServiceError)
        assert len(chain.strategies) >= 1


# --- 12.5: Skills usage example ---

class TestSkillsIntegration:
    def test_builtin_skills_loaded(self):
        """Built-in skills loaded and matchable."""
        reg = SkillRegistry()
        count = scan_builtin_skills(reg)
        assert count >= 3

        matched = reg.match_skills("coding", "review my code")
        assert len(matched) >= 1
        assert any(s.meta.name == "code-review" for s in matched)

    def test_skill_content_loading(self):
        """Skills lazy-load content on match."""
        reg = SkillRegistry()
        scan_builtin_skills(reg)

        matched = reg.match_skills("search", "search and analyze data")
        if matched:
            assert matched[0]._content_loaded
            assert matched[0].content  # has content


# --- 12.6: Security example ---

class TestSecurityIntegration:
    def test_command_blocking(self):
        """HITL interaction and command blocking."""
        checker = CommandSafetyChecker()
        assert not checker.check("rm -rf /").safe
        assert not checker.check("mkfs /dev/sda").safe
        assert checker.check("ls -la").safe

    def test_ssrf_blocking(self):
        """SSRF blocking."""
        protector = SSRFProtector()
        assert not protector.check_url("http://127.0.0.1/admin").safe
        assert not protector.check_url("http://169.254.169.254/meta-data").safe
        assert protector.check_url("https://api.example.com/data").safe

    def test_safety_manager_levels(self):
        from open_agent.config import SafetyConfig

        # Strict blocks dangerous
        strict = SafetyManager(SafetyConfig(safety_level="strict"))
        assert not strict.check_command("rm -rf /").safe

        # Off allows all
        off = SafetyManager(SafetyConfig(safety_level="off"))
        assert off.check_command("rm -rf /").safe


# --- 12.7: Evaluation suite example ---

class TestEvalSuite:
    @pytest.mark.asyncio
    async def test_eval_suite(self, tmp_path):
        """10+ scenario evaluation suite with metrics."""
        scenarios = [
            Scenario(name="s1", input="hello", expected_tool_calls=[], domain="general"),
            Scenario(name="s2", input="debug my code", expected_tool_calls=[], domain="coding"),
            Scenario(name="s3", input="search for AI papers", expected_tool_calls=[], domain="search"),
            Scenario(name="s4", input="browse website", expected_tool_calls=[], domain="web"),
            Scenario(name="s5", input="write a function", expected_tool_calls=[], domain="coding"),
            Scenario(name="s6", input="analyze data", expected_tool_calls=[], domain="search"),
            Scenario(name="s7", input="refactor this code", expected_tool_calls=[], domain="coding"),
            Scenario(name="s8", input="review my code", expected_tool_calls=[], domain="coding"),
            Scenario(name="s9", input="what is Python", expected_tool_calls=[], domain="general"),
            Scenario(name="s10", input="scrape this page", expected_tool_calls=[], domain="web"),
            Scenario(name="s11", input="对比分析", expected_tool_calls=[], domain="general"),
            Scenario(name="s12", input="how are you", expected_tool_calls=[], domain="general"),
        ]

        # Save dataset
        ds = EvalDataset(tmp_path / "datasets")
        ds.save_version("1.0", scenarios, metadata={"description": "Smoke test suite"})
        loaded = ds.load_version("1.0")
        assert loaded is not None
        assert len(loaded.scenarios) >= 10

        # Run routing eval
        pipeline = RoutingPipeline()
        test_set = [
            {"input": s.input, "expected_domain": s.domain}
            for s in scenarios
        ]
        results = await pipeline.evaluate(test_set)
        assert 0.0 <= results["domain_accuracy"] <= 1.0


# --- 12.8: Smoke test ---

class TestSmokeTest:
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """Verify all modules work together: route -> react -> trace -> eval."""
        # Setup
        trace_mgr = TraceManager()
        registry = ToolRegistry()
        pipeline = RoutingPipeline()

        @tool_schema(name="echo")
        def echo(text: str) -> str:
            """Echo text back.
            Args:
                text: Text to echo
            """
            return text

        registry.register("echo", handler=echo)

        # Execute
        trace = trace_mgr.create_trace(metadata={"user_input": "test pipeline"})
        decision = await pipeline.route("echo hello", trace=trace)

        loop = ReActLoop(tool_registry=registry, max_iterations=3)
        response = await loop.run(
            user_input="echo hello",
            routing_decision=decision,
            trace=trace,
        )

        # Verify trace
        assert len(trace.spans) > 0
        assert any(s.kind == SpanKind.ROUTING for s in trace.spans)

        # Verify monitoring
        scorer = QualityScorer()
        quality = scorer.score(trace)
        assert 0 <= quality.score <= 100

        # Verify memory
        config = AgentConfig()
        factory = MemoryFactory(config.memory)
        wm = factory.create_working_memory()
        await wm.add_message("user", "hello")
        ctx = await wm.get_context()
        assert len(ctx) > 0

        # Verify eval
        scenario = Scenario(
            name="smoke_test",
            input="echo hello",
            expected_tool_calls=["echo"],
        )
        engine = TraceReplayEngine()
        replay_result = engine.replay(trace, scenario)
        assert isinstance(replay_result.passed, bool)

        # Verify trace-to-eval conversion
        eval_case = trace_to_eval_case(trace)
        assert eval_case.name.startswith("trace_")

    @pytest.mark.asyncio
    async def test_checkpoint_in_pipeline(self, tmp_path):
        """Checkpoint + resume in the pipeline."""
        from open_agent.checkpoint.manager import CheckpointManager
        from open_agent.checkpoint.storage import JSONStorage

        storage = JSONStorage(str(tmp_path / "checkpoints"))
        ckpt_config = CheckpointConfig(interval=1, storage_path=str(tmp_path / "checkpoints"))
        mgr = CheckpointManager(config=ckpt_config, storage=storage)

        await mgr.on_start()

        # Save checkpoint
        ckpt = mgr.save_checkpoint(
            step_number=1,
            context={"input": "test"},
            tool_calls=[{"tool": "echo", "args": {"text": "hi"}}],
            memory_state={"working": "context"},
            idempotency_key="step-1",
        )
        assert ckpt is not None

        # Resume
        state = mgr.resume_from_checkpoint(ckpt.idempotency_key or str(ckpt.step_number))
        assert state is not None
        assert state.next_step == 2
        assert state.restored_context["input"] == "test"

        await mgr.on_stop()
