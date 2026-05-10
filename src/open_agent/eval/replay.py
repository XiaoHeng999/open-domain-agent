"""Trace replay engine — step-by-step comparison of actual vs expected."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from open_agent.eval.assertions import AssertionResult, check_assertion
from open_agent.eval.scenario import Scenario, StepAssertion
from open_agent.trace import SpanKind, Trace


@dataclass
class StepComparison:
    """Comparison result for a single step."""

    step_number: int
    actual_tool: str | None = None
    expected_tool: str | None = None
    match: bool = False
    assertion_results: list[AssertionResult] = field(default_factory=list)


@dataclass
class ReplayResult:
    """Result of trace replay against a scenario."""

    scenario_name: str
    passed: bool
    step_comparisons: list[StepComparison] = field(default_factory=list)
    tool_call_accuracy: float = 0.0
    assertion_pass_rate: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class TraceReplayEngine:
    """Replay execution trace and compare against scenario expectations."""

    def replay(self, trace: Trace, scenario: Scenario) -> ReplayResult:
        """Replay trace against scenario, checking each step."""
        tool_calls = self._extract_tool_calls(trace)
        step_comparisons: list[StepComparison] = []
        total_assertions = 0
        passed_assertions = 0

        # Compare tool calls
        max_steps = max(len(tool_calls), len(scenario.expected_tool_calls))
        for i in range(max_steps):
            actual = tool_calls[i] if i < len(tool_calls) else None
            expected = scenario.expected_tool_calls[i] if i < len(scenario.expected_tool_calls) else None

            step = StepComparison(
                step_number=i,
                actual_tool=actual.get("tool") if actual else None,
                expected_tool=expected,
                match=(actual.get("tool") if actual else None) == expected,
            )
            step_comparisons.append(step)

        # Check assertions
        actual_data = {
            "tool_calls": tool_calls,
            "output": self._extract_final_output(trace),
            "state": {},
        }
        for assertion in scenario.step_assertions:
            result = check_assertion(assertion, actual_data)
            total_assertions += 1
            if result.passed:
                passed_assertions += 1
            # Attach to matching step comparison
            if assertion.step < len(step_comparisons):
                step_comparisons[assertion.step].assertion_results.append(result)

        # Calculate metrics
        tool_matches = sum(1 for s in step_comparisons if s.match)
        tool_accuracy = tool_matches / max(len(step_comparisons), 1)
        assertion_rate = passed_assertions / max(total_assertions, 1)

        overall_passed = tool_accuracy >= 0.8 and (assertion_rate >= 0.8 if total_assertions > 0 else True)

        return ReplayResult(
            scenario_name=scenario.name,
            passed=overall_passed,
            step_comparisons=step_comparisons,
            tool_call_accuracy=tool_accuracy,
            assertion_pass_rate=assertion_rate,
        )

    def _extract_tool_calls(self, trace: Trace) -> list[dict[str, Any]]:
        """Extract ordered tool calls from trace spans."""
        calls = []
        for span in trace.spans:
            if span.kind == SpanKind.TOOL_CALL:
                calls.append({
                    "tool": span.attributes.get("tool_name", ""),
                    "arguments": span.attributes.get("arguments", {}),
                    "output": span.attributes.get("output", ""),
                })
        return calls

    def _extract_final_output(self, trace: Trace) -> str:
        """Extract final output from the last agent loop span."""
        for span in reversed(trace.spans):
            if span.kind == SpanKind.AGENT_LOOP:
                return span.attributes.get("output", "")
        return ""
