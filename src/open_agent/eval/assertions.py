"""Assertion types for eval — tool_called_with, output_matches, output_contains, state_equals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from open_agent.eval.scenario import StepAssertion


@dataclass
class AssertionResult:
    """Result of checking a single assertion."""

    passed: bool
    assertion: StepAssertion
    actual_value: Any = None
    message: str = ""


def check_assertion(assertion: StepAssertion, actual_data: dict[str, Any]) -> AssertionResult:
    """Check a single assertion against actual execution data."""
    checkers = {
        "tool_called_with": _check_tool_called_with,
        "output_matches": _check_output_matches,
        "output_contains": _check_output_contains,
        "state_equals": _check_state_equals,
    }
    checker = checkers.get(assertion.type)
    if not checker:
        return AssertionResult(
            passed=False,
            assertion=assertion,
            message=f"Unknown assertion type: {assertion.type}",
        )
    return checker(assertion, actual_data)


def _check_tool_called_with(assertion: StepAssertion, actual: dict[str, Any]) -> AssertionResult:
    """Check that a tool was called with expected parameters."""
    tool_calls = actual.get("tool_calls", [])
    for tc in tool_calls:
        if tc.get("tool") == assertion.tool:
            if assertion.params_contain:
                for key, value in assertion.params_contain.items():
                    if tc.get("arguments", {}).get(key) != value:
                        return AssertionResult(
                            passed=False,
                            assertion=assertion,
                            actual_value=tc,
                            message=f"Parameter mismatch: {key}",
                        )
            return AssertionResult(passed=True, assertion=assertion, actual_value=tc)

    return AssertionResult(
        passed=False,
        assertion=assertion,
        message=f"Tool '{assertion.tool}' not called",
    )


def _check_output_matches(assertion: StepAssertion, actual: dict[str, Any]) -> AssertionResult:
    """Check that output exactly matches expected value."""
    output = actual.get("output", "")
    expected = assertion.expected_value or ""
    passed = output == expected
    return AssertionResult(
        passed=passed,
        assertion=assertion,
        actual_value=output,
        message="" if passed else f"Output mismatch: got '{output[:100]}'",
    )


def _check_output_contains(assertion: StepAssertion, actual: dict[str, Any]) -> AssertionResult:
    """Check that output contains expected substring."""
    output = actual.get("output", "")
    expected = str(assertion.expected_value or "")
    passed = expected in output
    return AssertionResult(
        passed=passed,
        assertion=assertion,
        actual_value=output[:200],
        message="" if passed else f"Output does not contain '{expected}'",
    )


def _check_state_equals(assertion: StepAssertion, actual: dict[str, Any]) -> AssertionResult:
    """Check that a state value equals expected."""
    state = actual.get("state", {})
    expected = assertion.expected_value
    # Navigate nested keys if needed
    actual_value = state
    passed = actual_value == expected
    return AssertionResult(
        passed=passed,
        assertion=assertion,
        actual_value=actual_value,
        message="" if passed else f"State mismatch",
    )
