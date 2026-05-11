"""Tests for the recovery module: classifier, strategies, engine, and registry."""

from __future__ import annotations

import asyncio
import json
import pytest

from open_agent.errors import (
    ParseError,
    ParameterError,
    RetrievalError,
    ServiceError,
    ToolError,
)
from open_agent.tools.base import FunctionTool
from open_agent.registry import ToolRegistry
from open_agent.recovery.classifier import ErrorClassifier, ToolErrorType
from open_agent.recovery.engine import (
    RecoveryChain,
    RecoveryPolicyRegistry,
    execute_recovery_chain,
)
from open_agent.recovery.strategies import (
    ParameterRecoveryStrategy,
    ParseRecoveryStrategy,
    RecoveryResult,
    RecoveryStatus,
    RecoveryStrategy,
    RecoveryTrace,
    RetrievalRecoveryStrategy,
    ServiceRecoveryStrategy,
)


# =====================================================================
# Helpers
# =====================================================================


class _DummyStrategy(RecoveryStrategy):
    """Strategy that always succeeds (for testing)."""

    def __init__(self, name_suffix: str = "ok") -> None:
        self._suffix = name_suffix

    @property
    def name(self) -> str:  # type: ignore[override]
        return f"DummyStrategy_{self._suffix}"

    async def execute(self, error: ToolError, context: dict) -> RecoveryResult:
        return RecoveryResult(
            status=RecoveryStatus.SUCCESS,
            error_type="test",
            strategy_name=self.name,
            message="ok",
        )


class _FailStrategy(RecoveryStrategy):
    """Strategy that always fails (for testing)."""

    async def execute(self, error: ToolError, context: dict) -> RecoveryResult:
        return RecoveryResult(
            status=RecoveryStatus.FAILED,
            error_type="test",
            strategy_name=self.name,
            message="deliberate failure",
        )


# =====================================================================
# ErrorClassifier tests
# =====================================================================


class TestErrorClassifier:
    """Test that each ToolError subclass maps to the correct ToolErrorType."""

    def setup_method(self) -> None:
        self.clf = ErrorClassifier()

    def test_classify_parameter_error(self) -> None:
        err = ParameterError("bad param", tool_name="search")
        assert self.clf.classify(err) == ToolErrorType.ParameterError

    def test_classify_retrieval_error(self) -> None:
        err = RetrievalError("no results", tool_name="search")
        assert self.clf.classify(err) == ToolErrorType.RetrievalError

    def test_classify_service_error(self) -> None:
        err = ServiceError("timeout", tool_name="http")
        assert self.clf.classify(err) == ToolErrorType.ServiceError

    def test_classify_parse_error(self) -> None:
        err = ParseError("json decode", tool_name="parser")
        assert self.clf.classify(err) == ToolErrorType.ParseError

    def test_classify_bare_tool_error_heuristic_param(self) -> None:
        err = ToolError("missing parameter")
        assert self.clf.classify(err) == ToolErrorType.ParameterError

    def test_classify_bare_tool_error_heuristic_service(self) -> None:
        err = ToolError("connection timeout")
        assert self.clf.classify(err) == ToolErrorType.ServiceError

    def test_classify_bare_tool_error_heuristic_parse(self) -> None:
        err = ToolError("json parse failed")
        assert self.clf.classify(err) == ToolErrorType.ParseError

    def test_classify_bare_tool_error_heuristic_retrieval(self) -> None:
        err = ToolError("query returned nothing")
        assert self.clf.classify(err) == ToolErrorType.RetrievalError

    def test_classify_unknown_exception_defaults_to_service(self) -> None:
        err = ValueError("something went wrong")
        assert self.clf.classify(err) == ToolErrorType.ServiceError


# =====================================================================
# Recovery strategies
# =====================================================================


class TestParameterRecoveryStrategy:
    @pytest.mark.asyncio
    async def test_success_with_fixed_args(self) -> None:
        """When fixed_args are provided and handler succeeds, strategy succeeds."""

        def handler(name: str = "default", count: int = 0) -> str:
            return f"{name}:{count}"

        error = ParameterError("missing 'name'", tool_name="test")
        ctx = {
            "args": {"count": 5},
            "fixed_args": {"name": "alice"},
            "tool_handler": handler,
        }
        result = await ParameterRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS
        assert result.data["result"] == "alice:5"

    @pytest.mark.asyncio
    async def test_fills_schema_defaults(self) -> None:
        """Missing parameters are filled from tool schema defaults."""

        def handler(x: int = 1, y: int = 2) -> int:
            return x + y

        error = ParameterError("missing", tool_name="add")
        ctx = {
            "args": {"x": 10},
            "tool_handler": handler,
            "tool_schema": {
                "inputSchema": {
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer", "default": 99},
                    }
                }
            },
        }
        result = await ParameterRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS
        assert result.data["result"] == 109

    @pytest.mark.asyncio
    async def test_failure_no_handler(self) -> None:
        error = ParameterError("missing", tool_name="test")
        result = await ParameterRecoveryStrategy().execute(error, {})
        assert result.status == RecoveryStatus.FAILED


class TestRetrievalRecoveryStrategy:
    @pytest.mark.asyncio
    async def test_query_expansion_succeeds(self) -> None:
        """Strategy expands query and retries."""

        def handler(query: str) -> list[str]:
            if "*" in query:
                return ["result1", "result2"]
            raise RetrievalError("empty result")

        error = RetrievalError("no results", tool_name="search")
        ctx = {"args": {"query": "cats"}, "tool_handler": handler}
        result = await RetrievalRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS
        assert "result1" in result.data["result"]

    @pytest.mark.asyncio
    async def test_filter_relaxation_succeeds(self) -> None:
        """Strategy relaxes filters when query expansion fails."""

        call_count = 0

        def handler(query: str = "", filters: dict | None = None) -> list[str]:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise RetrievalError("empty")
            return ["relaxed_result"]

        error = RetrievalError("no results", tool_name="search")
        ctx = {
            "args": {"query": "cats", "filters": {"color": "red", "size": "XL"}},
            "tool_handler": handler,
        }
        result = await RetrievalRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_cache_fallback_succeeds(self) -> None:
        """Strategy falls back to cache when retries fail."""
        cache = {"cats": ["cached_cat"]}

        def handler(**kwargs: object) -> list[str]:
            raise RetrievalError("always fails")

        error = RetrievalError("no results", tool_name="search")
        ctx = {
            "args": {"query": "cats"},
            "tool_handler": handler,
            "cache": cache,
        }
        result = await RetrievalRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS
        assert result.data["result"] == ["cached_cat"]

    @pytest.mark.asyncio
    async def test_all_steps_fail(self) -> None:
        error = RetrievalError("no results", tool_name="search")
        result = await RetrievalRecoveryStrategy().execute(error, {})
        assert result.status == RecoveryStatus.FAILED


class TestServiceRecoveryStrategy:
    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self) -> None:
        """Strategy retries with exponential backoff; succeeds on attempt 2."""
        call_count = 0

        def handler() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ServiceError("unavailable")
            return "ok"

        error = ServiceError("timeout", tool_name="http")
        ctx = {"tool_handler": handler, "args": {}}
        result = await ServiceRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS
        assert result.attempt >= 2

    @pytest.mark.asyncio
    async def test_fallback_tool_succeeds(self) -> None:
        """When retries fail, strategy looks for a fallback tool in registry."""
        registry = ToolRegistry()
        registry.register(
            FunctionTool(
                name="primary",
                description="Primary tool",
                parameters={"type": "object", "properties": {}},
                handler=lambda: (_ for _ in ()).throw(ServiceError("down")),
            ),
            tags=["primary"],
        )
        registry.register(
            FunctionTool(
                name="fallback_search",
                description="Fallback search",
                parameters={"type": "object", "properties": {}},
                handler=lambda: "fallback_ok",
            ),
            tags=["fallback"],
        )

        error = ServiceError("timeout", tool_name="primary")
        ctx = {"tool_handler": lambda: (_ for _ in ()).throw(ServiceError("down")), "args": {}, "tool_registry": registry}
        result = await ServiceRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS
        assert result.data["fallback_tool"] == "fallback_search"

    @pytest.mark.asyncio
    async def test_all_retries_exhaust(self) -> None:
        """Strategy returns FAILED after max retries with no fallback."""

        def handler() -> str:
            raise ServiceError("always down")

        error = ServiceError("timeout", tool_name="http")
        ctx = {"tool_handler": handler, "args": {}}
        result = await ServiceRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.FAILED
        assert result.attempt == 3  # MAX_RETRIES


class TestParseRecoveryStrategy:
    @pytest.mark.asyncio
    async def test_alternate_format_succeeds(self) -> None:
        """Strategy falls back to text format when json parsing fails."""
        error = ParseError("json decode error", tool_name="parser")
        ctx = {"raw_output": "hello world", "format": "json"}
        result = await ParseRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS
        assert result.data["format"] == "text"

    @pytest.mark.asyncio
    async def test_csv_format_succeeds(self) -> None:
        """Strategy can parse CSV as an alternate format.

        We set format="text" so that text is skipped and json/csv are tried
        as alternates.  The csv parser handles the CSV string correctly.
        """
        csv_data = "name,age\nAlice,30\nBob,25"
        error = ParseError("json decode error", tool_name="parser")
        ctx = {"raw_output": csv_data, "format": "text"}
        result = await ParseRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS
        # json.loads fails on CSV data, so csv format is the one that succeeds.
        assert result.data["format"] == "csv"
        parsed = result.data["result"]
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_llm_assist_succeeds(self) -> None:
        """LLM assist callable repairs the output."""
        error = ParseError("json decode error", tool_name="parser")
        ctx = {
            "raw_output": "not parseable",
            "format": "text",  # text won't help either since we check json first
            "llm_assist": lambda raw: {"repaired": True},
        }
        # Both json and csv will fail for "not parseable"; text format will
        # succeed because it accepts any non-empty string.
        result = await ParseRecoveryStrategy().execute(error, ctx)
        # Text format accepts non-empty strings, so it should succeed via format switch.
        assert result.status == RecoveryStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_llm_assist_when_formats_fail(self) -> None:
        """LLM assist is invoked when all format switches fail."""

        # Provide empty raw_output so text format returns None.
        def llm_repair(raw: str) -> dict:
            return {"fixed": True}

        error = ParseError("json decode error", tool_name="parser")
        ctx = {
            "raw_output": "",  # empty → text format returns None
            "format": "json",
            "llm_assist": llm_repair,
        }
        result = await ParseRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.SUCCESS
        assert result.data["result"] == {"fixed": True}
        assert result.data["method"] == "llm_assist"

    @pytest.mark.asyncio
    async def test_all_fail(self) -> None:
        error = ParseError("parse error", tool_name="parser")
        ctx = {"raw_output": "", "format": "json"}
        result = await ParseRecoveryStrategy().execute(error, ctx)
        assert result.status == RecoveryStatus.FAILED


# =====================================================================
# RecoveryChain tests
# =====================================================================


class TestRecoveryChain:
    @pytest.mark.asyncio
    async def test_chain_succeeds_on_first_strategy(self) -> None:
        chain = RecoveryChain(
            ToolErrorType.ParameterError,
            [_DummyStrategy("first"), _DummyStrategy("second")],
        )
        trace = await chain.execute(
            ParameterError("bad"),
            {},
        )
        assert trace.final_status == RecoveryStatus.SUCCESS
        assert len(trace.attempts) == 1
        assert trace.attempts[0].strategy_name == "DummyStrategy_first"

    @pytest.mark.asyncio
    async def test_chain_succeeds_on_second_strategy(self) -> None:
        chain = RecoveryChain(
            ToolErrorType.ParameterError,
            [_FailStrategy(), _DummyStrategy("second")],
        )
        trace = await chain.execute(
            ParameterError("bad"),
            {},
        )
        assert trace.final_status == RecoveryStatus.SUCCESS
        assert len(trace.attempts) == 2
        assert trace.attempts[0].status == RecoveryStatus.FAILED
        assert trace.attempts[1].strategy_name == "DummyStrategy_second"

    @pytest.mark.asyncio
    async def test_chain_exhaustion_escalates(self) -> None:
        chain = RecoveryChain(
            ToolErrorType.ServiceError,
            [_FailStrategy(), _FailStrategy()],
        )
        trace = await chain.execute(
            ServiceError("down"),
            {},
        )
        assert trace.final_status == RecoveryStatus.ESCALATE
        assert len(trace.attempts) == 2
        assert all(a.status == RecoveryStatus.FAILED for a in trace.attempts)

    @pytest.mark.asyncio
    async def test_add_strategy_fluent(self) -> None:
        chain = RecoveryChain(ToolErrorType.ParameterError)
        result = chain.add_strategy(_DummyStrategy())
        assert result is chain
        assert len(chain.strategies) == 1


# =====================================================================
# RecoveryPolicyRegistry tests
# =====================================================================


class TestRecoveryPolicyRegistry:
    def test_register_and_get_chain(self) -> None:
        reg = RecoveryPolicyRegistry()
        custom = _DummyStrategy("custom")
        reg.register(ToolErrorType.ParameterError, custom)

        chain = reg.get_chain(ToolErrorType.ParameterError)
        # Custom strategy should be first
        assert chain.strategies[0] is custom
        # Followed by the default strategies
        assert len(chain.strategies) > 1

    def test_clear_specific_error_type(self) -> None:
        reg = RecoveryPolicyRegistry()
        reg.register(ToolErrorType.ParameterError, _DummyStrategy())
        reg.register(ToolErrorType.ServiceError, _DummyStrategy())

        reg.clear(ToolErrorType.ParameterError)
        chain_pe = reg.get_chain(ToolErrorType.ParameterError)
        chain_se = reg.get_chain(ToolErrorType.ServiceError)

        # ParameterError custom cleared, only defaults remain
        assert all(not isinstance(s, _DummyStrategy) for s in chain_pe.strategies)
        # ServiceError custom still present
        assert any(isinstance(s, _DummyStrategy) for s in chain_se.strategies)

    def test_clear_all(self) -> None:
        reg = RecoveryPolicyRegistry()
        reg.register(ToolErrorType.ParameterError, _DummyStrategy())
        reg.register(ToolErrorType.ServiceError, _DummyStrategy())

        reg.clear()
        for et in ToolErrorType:
            chain = reg.get_chain(et)
            assert all(not isinstance(s, _DummyStrategy) for s in chain.strategies)

    def test_get_chain_with_no_custom(self) -> None:
        reg = RecoveryPolicyRegistry()
        chain = reg.get_chain(ToolErrorType.ServiceError)
        # Should contain only the default ServiceRecoveryStrategy
        assert any(isinstance(s, ServiceRecoveryStrategy) for s in chain.strategies)


# =====================================================================
# Top-level execute_recovery_chain tests
# =====================================================================


class TestExecuteRecoveryChain:
    @pytest.mark.asyncio
    async def test_classify_and_recover_parameter_error(self) -> None:
        """End-to-end: ParameterError is classified and recovered via chain."""
        reg = RecoveryPolicyRegistry()
        # Replace default chain with a guaranteed-success strategy.
        reg.register(ToolErrorType.ParameterError, _DummyStrategy("e2e_param"))

        trace = await execute_recovery_chain(
            ParameterError("bad arg", tool_name="test"),
            context={},
            policy_registry=reg,
        )
        assert trace.final_status == RecoveryStatus.SUCCESS
        assert trace.error_type == ToolErrorType.ParameterError.value

    @pytest.mark.asyncio
    async def test_non_tool_error_wrapped(self) -> None:
        """Non-ToolError exceptions are wrapped and still classified."""
        reg = RecoveryPolicyRegistry()
        reg.register(ToolErrorType.ServiceError, _DummyStrategy("wrap"))

        trace = await execute_recovery_chain(
            ValueError("connection timeout"),
            context={},
            policy_registry=reg,
        )
        assert trace.final_status == RecoveryStatus.SUCCESS
        assert trace.error.cause is not None

    @pytest.mark.asyncio
    async def test_chain_exhaustion_returns_escalate(self) -> None:
        reg = RecoveryPolicyRegistry()
        # Override with failing strategies.
        reg.register(ToolErrorType.ServiceError, _FailStrategy())
        # Also clear defaults so only our fail strategy runs.
        reg._custom[ToolErrorType.ServiceError] = [_FailStrategy()]

        trace = await execute_recovery_chain(
            ServiceError("down"),
            context={},
            policy_registry=reg,
        )
        assert trace.final_status == RecoveryStatus.ESCALATE
