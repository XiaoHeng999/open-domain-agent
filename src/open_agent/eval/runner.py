"""Eval runner — loads YAML scenarios and executes against AgentRuntime."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from open_agent.eval.judge import LLMJudge
from open_agent.eval.metrics import compute_metrics
from open_agent.eval.replay import ReplayResult, TraceReplayEngine
from open_agent.eval.scenario import Scenario, StepAssertion
from open_agent.trace import SpanKind

logger = logging.getLogger("open_agent.eval")


def _enforce_retention(path: Path, max_retention: int) -> None:
    """Keep only the last *max_retention* lines in a JSONL file."""
    if not path.exists():
        return
    lines = path.read_text().splitlines()
    if len(lines) <= max_retention:
        return
    kept = lines[-max_retention:]
    path.write_text("\n".join(kept) + "\n")


def extract_trajectory_from_jsonl(jsonl_path: Path, trace_id: str) -> dict | None:
    """Find a trajectory by trace_id in a JSONL file."""
    if not jsonl_path.exists():
        return None
    for line in jsonl_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if data.get("trace_id") == trace_id:
                return data
        except Exception:
            continue
    return None


class EvalRunner:
    """Loads YAML test scenarios and executes them against AgentRuntime."""

    def __init__(
        self,
        scenarios_dir: Path | str | None = None,
        runtime: Any = None,
    ) -> None:
        self._scenarios_dir = Path(scenarios_dir) if scenarios_dir else Path("evals")
        self._runtime = runtime
        self._replay_engine = TraceReplayEngine()
        self._judge = LLMJudge()

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

    def _yaml_to_scenario(self, yaml_data: dict[str, Any]) -> Scenario:
        """Convert a YAML dict to a Scenario dataclass."""
        assertions: list[StepAssertion] = []
        for raw_assert in yaml_data.get("assertions", []):
            assertions.append(StepAssertion(
                step=raw_assert.get("step", 0),
                type=raw_assert["type"],
                tool=raw_assert.get("tool"),
                params_contain=raw_assert.get("params_contain"),
                expected_value=raw_assert.get("expected_value"),
                description=raw_assert.get("description", ""),
            ))

        expected_outcome = yaml_data.get("expected_outcome")
        if expected_outcome:
            assertions.append(StepAssertion(
                step=0,
                type="output_contains",
                expected_value=expected_outcome,
            ))

        expected_tool_calls = yaml_data.get("expected_tools", yaml_data.get("expected_tool_calls", []))

        return Scenario(
            name=yaml_data["name"],
            input=yaml_data["input"],
            expected_tool_calls=expected_tool_calls,
            expected_output=yaml_data.get("expected_outcome", ""),
            step_assertions=assertions,
            metadata=yaml_data.get("metadata", {}),
            domain=yaml_data.get("domain", "general"),
        )

    async def run_suite(self, suite_name: str) -> list[dict[str, Any]]:
        """Execute all scenarios in a suite, compute metrics, persist results."""
        scenarios = self.load_suite(suite_name)
        results: list[dict[str, Any]] = []
        replay_results: list[ReplayResult] = []

        for scenario in scenarios:
            result = await self._run_scenario(scenario)
            results.append(result)
            if "replay_result" in result:
                replay_results.append(result["replay_result"])

        # Compute aggregate metrics from ReplayResults
        metrics = compute_metrics(replay_results)

        self._save_results(suite_name, results, metrics)

        return results

    def _save_results(
        self,
        suite_name: str,
        results: list[dict[str, Any]],
        metrics: Any = None,
    ) -> None:
        """Persist eval results + metrics + trajectories."""
        output_dir = Path(".open_agent") / "eval_results"
        output_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)

        passed = sum(1 for r in results if r["status"] == "pass")
        failed = len(results) - passed

        model_info: dict[str, str] = {}
        if self._runtime is not None:
            try:
                cfg = self._runtime.config
                model_info = {"provider": cfg.model.provider, "name": cfg.model.name}
            except Exception:
                pass

        # Remove transient fields before serialization
        clean_results = []
        for r in results:
            clean = {k: v for k, v in r.items() if k != "replay_result"}
            clean_results.append(clean)

        report = {
            "suite": suite_name,
            "timestamp": now.isoformat(),
            "model": model_info,
            "results": clean_results,
            "metrics": metrics.to_dict() if metrics else {},
            "summary": {"total": len(results), "passed": passed, "failed": failed},
        }

        # Append to JSONL
        jsonl_path = output_dir / f"{suite_name}.jsonl"
        with open(jsonl_path, "a") as f:
            f.write(json.dumps(report, ensure_ascii=False) + "\n")

        # Enforce retention
        retention = 100
        if self._runtime is not None:
            try:
                val = self._runtime.config.eval.results_retention
                if isinstance(val, int):
                    retention = val
            except Exception:
                pass
        _enforce_retention(jsonl_path, retention)

        # Persist trajectories
        self._save_trajectories(output_dir, results, suite_name=suite_name)

    def _save_trajectories(
        self,
        output_dir: Path,
        results: list[dict[str, Any]],
        suite_name: str = "unknown",
    ) -> None:
        """Append trajectory data to {suite}_trajectories.jsonl."""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return

        jsonl_path = output_dir / f"{suite_name}_trajectories.jsonl"
        for r in results:
            trace_id = r.get("trace_id")
            name = r.get("name", "unknown")
            trace_json = r.get("trace_json")
            if trace_id and trace_json:
                try:
                    entry = json.dumps({
                        "name": name,
                        "trace_id": trace_id,
                        "trace": trace_json,
                    }, ensure_ascii=False)
                    with open(jsonl_path, "a") as f:
                        f.write(entry + "\n")
                except Exception:
                    pass

        # Enforce retention
        retention = 200
        if self._runtime is not None:
            try:
                val = self._runtime.config.eval.trajectories_retention
                if isinstance(val, int):
                    retention = val
            except Exception:
                pass
        _enforce_retention(jsonl_path, retention)

    async def _run_scenario(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """Run a single scenario using TraceReplayEngine for evaluation."""
        try:
            response = await self._execute_scenario(scenario["input"])
        except Exception as exc:
            return {
                "name": scenario["name"],
                "status": "error",
                "error": str(exc),
            }

        if response is None:
            return {
                "name": scenario["name"],
                "status": "error",
                "error": "No response from runtime",
            }

        scenario_obj = self._yaml_to_scenario(scenario)

        # Get trace from runtime's trace manager
        trace = None
        trace_json = None
        if self._runtime is not None and hasattr(self._runtime, "trace_manager"):
            try:
                tm = self._runtime.trace_manager
                trace = tm.get_trace(response.trace_id)
                if trace and type(trace).__name__ == "Trace":
                    trace_json = trace.to_dict()
            except Exception:
                trace = None

        result: dict[str, Any] = {
            "name": scenario["name"],
            "trace_id": response.trace_id,
            "output": response.output,
        }

        if trace_json:
            result["trace_json"] = trace_json

        # Only use TraceReplayEngine when we have a real Trace object
        if trace is not None and type(trace).__name__ == "Trace":
            replay_result = self._replay_engine.replay(trace, scenario_obj)
            status = "pass" if replay_result.passed else "fail"

            # Create EVAL span in the agent's trace
            eval_span = trace.create_span("eval_scenario", kind=SpanKind.EVAL)
            eval_span.set_attribute("scenario", scenario["name"])
            eval_span.set_attribute("passed", replay_result.passed)
            eval_span.set_attribute("tool_accuracy", replay_result.tool_call_accuracy)
            eval_span.set_attribute("assertion_rate", replay_result.assertion_pass_rate)
            eval_span.finish()

            checks = []
            for comp in replay_result.step_comparisons:
                checks.append({
                    "type": "tool_match",
                    "step": comp.step_number,
                    "actual": comp.actual_tool,
                    "expected": comp.expected_tool,
                    "passed": comp.match,
                })
            for comp in replay_result.step_comparisons:
                for ar in comp.assertion_results:
                    checks.append({
                        "type": ar.assertion.type,
                        "step": comp.step_number,
                        "passed": ar.passed,
                        "message": ar.message,
                    })

            if not checks:
                checks.append({"type": "no_expectations", "passed": True})

            # Run LLMJudge for quality scoring
            expected_desc = scenario.get("expected_outcome", scenario_obj.expected_output)
            judge_score = self._judge._rule_based_judge(response.output, expected_desc)

            result.update({
                "status": status,
                "checks": checks,
                "tool_call_accuracy": replay_result.tool_call_accuracy,
                "assertion_pass_rate": replay_result.assertion_pass_rate,
                "quality_score": judge_score.score,
                "quality_reasoning": judge_score.reasoning,
                "replay_result": replay_result,
            })
            return result

        # Fallback: no trace available, use basic substring matching
        checks = self._check_expectations_fallback(scenario, response)
        status = "pass" if all(c["passed"] for c in checks) else "fail"

        result.update({
            "status": status,
            "checks": checks,
            "tool_call_accuracy": 0.0,
            "assertion_pass_rate": 0.0,
        })
        return result

    async def _execute_scenario(self, user_input: str) -> Any:
        """Execute a scenario against the runtime. Override or set runtime."""
        if self._runtime is not None:
            return await self._runtime.run(user_input)
        raise NotImplementedError("No runtime configured for EvalRunner")

    def _check_expectations_fallback(
        self,
        scenario: dict[str, Any],
        response: Any,
    ) -> list[dict[str, Any]]:
        """Fallback: check expectations via substring matching when no trace."""
        checks: list[dict[str, Any]] = []

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

        expected_outcome = scenario.get("expected_outcome")
        if expected_outcome:
            output = response.output if response else ""
            passed = expected_outcome.lower() in output.lower()
            checks.append({
                "type": "expected_outcome",
                "expected": expected_outcome,
                "passed": passed,
            })

        if not checks:
            checks.append({"type": "no_expectations", "passed": True})

        return checks
