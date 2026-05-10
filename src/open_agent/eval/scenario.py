"""Scenario definition for evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepAssertion:
    """An assertion on a specific step of execution."""

    step: int
    type: str  # tool_called_with, output_matches, output_contains, state_equals
    tool: str | None = None
    params_contain: dict[str, Any] | None = None
    expected_value: Any = None
    description: str = ""


@dataclass
class Scenario:
    """A test scenario for agent evaluation."""

    name: str
    input: str
    expected_tool_calls: list[str] = field(default_factory=list)
    expected_output: str = ""
    step_assertions: list[StepAssertion] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    domain: str = "general"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "input": self.input,
            "expected_tool_calls": self.expected_tool_calls,
            "expected_output": self.expected_output,
            "step_assertions": [
                {
                    "step": a.step,
                    "type": a.type,
                    "tool": a.tool,
                    "params_contain": a.params_contain,
                    "expected_value": a.expected_value,
                }
                for a in self.step_assertions
            ],
            "domain": self.domain,
        }
