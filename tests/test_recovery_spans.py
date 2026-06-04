"""Tests for RECOVERY spans — trace instrumentation of recovery chain."""

from __future__ import annotations

import pytest

from open_agent.errors import ToolError
from open_agent.trace import SpanKind, TraceManager
from open_agent.recovery.engine import RecoveryChain
from open_agent.recovery.classifier import ToolErrorType
from open_agent.recovery.strategies import (
    RecoveryResult,
    RecoveryStatus,
    RecoveryStrategy,
)


class SuccessfulStrategy(RecoveryStrategy):
    """A recovery strategy that always succeeds."""

    name = "test_success"

    async def execute(self, error, context):
        return RecoveryResult(
            status=RecoveryStatus.SUCCESS,
            error_type="service",
            strategy_name="test_success",
            message="recovered",
        )


class FailingStrategy(RecoveryStrategy):
    """A recovery strategy that always fails."""

    name = "test_fail"

    async def execute(self, error, context):
        return RecoveryResult(
            status=RecoveryStatus.FAILED,
            error_type="service",
            strategy_name="test_fail",
            message="still broken",
        )


class TestRecoveryChainSpans:
    async def test_execute_creates_recovery_span(self):
        tm = TraceManager()
        trace = tm.create_trace()
        chain = RecoveryChain(
            error_type=ToolErrorType.ServiceError,
            strategies=[SuccessfulStrategy()],
        )

        error = ToolError("tool failed")
        context = {"_trace_manager": tm, "_current_trace_id": trace.trace_id}
        await chain.execute(error, context)

        recovery_spans = [s for s in trace.spans if s.kind == SpanKind.RECOVERY]
        assert len(recovery_spans) == 1
        span = recovery_spans[0]
        assert span.attributes.get("error_type") == "service_error"
        assert span.attributes.get("strategy_count") == 1
        assert span.attributes.get("final_status") == "success"
        assert span.end_time is not None

    async def test_execute_exhausted_chain_span(self):
        tm = TraceManager()
        trace = tm.create_trace()
        chain = RecoveryChain(
            error_type=ToolErrorType.ParameterError,
            strategies=[FailingStrategy(), FailingStrategy()],
        )

        error = ToolError("bad params")
        context = {"_trace_manager": tm, "_current_trace_id": trace.trace_id}
        await chain.execute(error, context)

        recovery_spans = [s for s in trace.spans if s.kind == SpanKind.RECOVERY]
        assert len(recovery_spans) == 1
        span = recovery_spans[0]
        assert span.attributes.get("strategy_count") == 2
        assert span.attributes.get("final_status") == "escalate"

    async def test_no_span_without_tracing(self):
        chain = RecoveryChain(
            error_type=ToolErrorType.ServiceError,
            strategies=[SuccessfulStrategy()],
        )

        error = ToolError("tool failed")
        # No trace context — should work without error
        result = await chain.execute(error, {})
        assert result.final_status == RecoveryStatus.SUCCESS
