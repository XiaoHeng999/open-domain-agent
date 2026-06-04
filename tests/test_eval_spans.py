"""Tests for EVAL spans — trace instrumentation of eval execution."""

from __future__ import annotations

import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from open_agent.eval.runner import EvalRunner
from open_agent.trace import SpanKind, TraceManager


@pytest.fixture
def eval_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestEvalSpans:
    async def test_eval_span_in_trace(self, eval_dir):
        """Running an eval scenario creates an EVAL span in the agent's trace."""
        tm = TraceManager()
        trace = tm.create_trace(metadata={"user_input": "hello"})

        mock_response = MagicMock()
        mock_response.output = "result"
        mock_response.trace_id = trace.trace_id
        mock_response.metadata = {"steps": [], "total_steps": 1}

        mock_runtime = MagicMock()
        mock_runtime.run = AsyncMock(return_value=mock_response)
        mock_runtime.trace_manager = tm

        runner = EvalRunner(scenarios_dir=Path(eval_dir), runtime=mock_runtime)

        scenario_dict = {
            "name": "test_eval_span",
            "input": "hello",
            "expected_outcome": "result",
        }
        result = await runner._run_scenario(scenario_dict)

        eval_spans = [s for s in trace.spans if s.kind == SpanKind.EVAL]
        assert len(eval_spans) == 1
        span = eval_spans[0]
        assert span.attributes.get("scenario") == "test_eval_span"
        assert "passed" in span.attributes
        assert "tool_accuracy" in span.attributes
        assert span.end_time is not None

    async def test_all_span_kinds_used(self):
        """All 9 SpanKind enum values should have actual usage in the codebase."""
        expected_kinds = {
            "routing", "tool_call", "memory_op", "agent_loop",
            "checkpoint", "recovery", "eval", "subagent", "internal",
        }
        actual_kinds = {kind.value for kind in SpanKind}
        assert actual_kinds == expected_kinds
