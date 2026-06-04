"""Eval trend analysis — compare multiple eval runs for regressions."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TrendComparison:
    """Comparison between two eval runs."""

    current_pass_rate: float
    previous_pass_rate: float
    pass_rate_delta: float
    current_tool_accuracy: float
    previous_tool_accuracy: float
    tool_accuracy_delta: float
    regressions: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)


def load_eval_results(
    suite: str,
    results_dir: Path | str = ".open_agent/eval_results",
    latest: int = 2,
) -> list[dict[str, Any]]:
    """Load the latest N eval result JSON files for a suite."""
    results_dir = Path(results_dir)
    if not results_dir.exists():
        return []

    files = sorted(results_dir.glob(f"{suite}_*.json"), reverse=True)
    loaded = []
    for f in files[:latest]:
        try:
            loaded.append(json.loads(f.read_text()))
        except Exception:
            continue
    return loaded


def compare_trends(
    results: list[dict[str, Any]],
) -> TrendComparison | None:
    """Compare the two most recent eval runs for regressions."""
    if len(results) < 2:
        return None

    current = results[0]
    previous = results[1]

    def pass_rate(report: dict[str, Any]) -> float:
        summary = report.get("summary", {})
        total = summary.get("total", 0)
        if total == 0:
            return 0.0
        return summary.get("passed", 0) / total

    def tool_accuracy(report: dict[str, Any]) -> float:
        metrics = report.get("metrics", {})
        return metrics.get("tool_call_success_rate", 0.0)

    cur_pr = pass_rate(current)
    prev_pr = pass_rate(previous)
    cur_ta = tool_accuracy(current)
    prev_ta = tool_accuracy(previous)

    # Identify regressions and improvements
    cur_scenarios = {r["name"]: r for r in current.get("results", [])}
    prev_scenarios = {r["name"]: r for r in previous.get("results", [])}

    regressions = []
    improvements = []
    for name in cur_scenarios:
        if name in prev_scenarios:
            cur_pass = cur_scenarios[name].get("status") == "pass"
            prev_pass = prev_scenarios[name].get("status") == "pass"
            if prev_pass and not cur_pass:
                regressions.append(name)
            elif cur_pass and not prev_pass:
                improvements.append(name)

    return TrendComparison(
        current_pass_rate=cur_pr,
        previous_pass_rate=prev_pr,
        pass_rate_delta=cur_pr - prev_pr,
        current_tool_accuracy=cur_ta,
        previous_tool_accuracy=prev_ta,
        tool_accuracy_delta=cur_ta - prev_ta,
        regressions=regressions,
        improvements=improvements,
    )
