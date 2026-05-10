"""Evaluation metrics — Intent Accuracy, Tool Call Success Rate, Task Completion, Avg Turns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from open_agent.eval.replay import ReplayResult


@dataclass
class EvalMetrics:
    """Computed evaluation metrics."""

    intent_accuracy: float = 0.0
    tool_call_success_rate: float = 0.0
    task_completion_rate: float = 0.0
    avg_turns: float = 0.0
    per_scenario: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_accuracy": self.intent_accuracy,
            "tool_call_success_rate": self.tool_call_success_rate,
            "task_completion_rate": self.task_completion_rate,
            "avg_turns": self.avg_turns,
            "per_scenario": self.per_scenario,
        }


def compute_metrics(results: list[ReplayResult]) -> EvalMetrics:
    """Compute aggregate metrics from replay results."""
    if not results:
        return EvalMetrics()

    total = len(results)
    tool_rates = []
    completed = 0
    total_steps = 0

    per_scenario: dict[str, dict[str, float]] = {}

    for r in results:
        tool_rates.append(r.tool_call_accuracy)
        if r.passed:
            completed += 1
        total_steps += len(r.step_comparisons)

        per_scenario[r.scenario_name] = {
            "tool_call_accuracy": r.tool_call_accuracy,
            "assertion_pass_rate": r.assertion_pass_rate,
            "passed": 1.0 if r.passed else 0.0,
        }

    return EvalMetrics(
        tool_call_success_rate=sum(tool_rates) / total,
        task_completion_rate=completed / total,
        avg_turns=total_steps / total,
        per_scenario=per_scenario,
    )
