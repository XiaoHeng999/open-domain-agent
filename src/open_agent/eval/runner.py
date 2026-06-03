"""Eval runner — loads YAML scenarios and executes against AgentRuntime."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("open_agent.eval")


class EvalRunner:
    """Loads YAML test scenarios and executes them against AgentRuntime."""

    def __init__(
        self,
        scenarios_dir: Path | str | None = None,
        runtime: Any = None,
    ) -> None:
        self._scenarios_dir = Path(scenarios_dir) if scenarios_dir else Path("evals")
        self._runtime = runtime

    def load_suite(self, suite_name: str) -> list[dict[str, Any]]:
        """Load all YAML scenarios from a suite directory."""
        suite_dir = self._scenarios_dir / suite_name
        if not suite_dir.exists():
            return []

        scenarios: list[dict[str, Any]] = []
        for path in sorted(suite_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text())
            if data and "name" in data and "input" in data:
                scenarios.append(data)
        return scenarios

    async def run_suite(self, suite_name: str) -> list[dict[str, Any]]:
        """Execute all scenarios in a suite and return results."""
        scenarios = self.load_suite(suite_name)
        results: list[dict[str, Any]] = []

        for scenario in scenarios:
            result = await self._run_scenario(scenario)
            results.append(result)

        return results

    async def _run_scenario(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """Run a single scenario and check expectations."""
        try:
            response = await self._execute_scenario(scenario["input"])
        except Exception as exc:
            return {
                "name": scenario["name"],
                "status": "error",
                "error": str(exc),
            }

        checks = self._check_expectations(scenario, response)
        status = "pass" if all(c["passed"] for c in checks) else "fail"

        return {
            "name": scenario["name"],
            "status": status,
            "checks": checks,
            "output": response.output if response else "",
        }

    async def _execute_scenario(self, user_input: str) -> Any:
        """Execute a scenario against the runtime. Override or set runtime."""
        if self._runtime is not None:
            return await self._runtime.run(user_input)
        raise NotImplementedError("No runtime configured for EvalRunner")

    def _check_expectations(
        self,
        scenario: dict[str, Any],
        response: Any,
    ) -> list[dict[str, Any]]:
        """Check scenario expectations against the response."""
        checks: list[dict[str, Any]] = []

        # Check expected_tools — look for tool names in step actions
        expected_tools = scenario.get("expected_tools", [])
        if expected_tools:
            steps = response.metadata.get("steps", []) if response and response.metadata else []
            used_tools = set()
            for step in steps:
                action = step.get("action", "") or ""
                for tool in expected_tools:
                    if tool in action:
                        used_tools.add(tool)

            for tool in expected_tools:
                passed = tool in used_tools
                checks.append({
                    "type": "expected_tool",
                    "tool": tool,
                    "passed": passed,
                })

        # Check expected_outcome — substring match in output
        expected_outcome = scenario.get("expected_outcome")
        if expected_outcome:
            output = response.output if response else ""
            passed = expected_outcome.lower() in output.lower()
            checks.append({
                "type": "expected_outcome",
                "expected": expected_outcome,
                "passed": passed,
            })

        # If no expectations defined, pass by default
        if not checks:
            checks.append({"type": "no_expectations", "passed": True})

        return checks
