"""Eval dataset versioning — versioned storage, loading, filtering."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from open_agent.eval.scenario import Scenario


@dataclass
class DatasetVersion:
    """A versioned snapshot of an eval dataset."""

    version: str
    scenarios: list[Scenario] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class EvalDataset:
    """Versioned evaluation dataset management."""

    def __init__(self, storage_dir: str | Path) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._versions: dict[str, DatasetVersion] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing version files."""
        for vf in self._dir.glob("v_*.json"):
            version_name = vf.stem[2:]  # strip "v_"
            data = json.loads(vf.read_text(encoding="utf-8"))
            scenarios = [self._dict_to_scenario(s) for s in data.get("scenarios", [])]
            self._versions[version_name] = DatasetVersion(
                version=version_name,
                scenarios=scenarios,
                metadata=data.get("metadata", {}),
            )

    def save_version(self, version: str, scenarios: list[Scenario], metadata: dict[str, Any] | None = None) -> None:
        """Save a new version of the dataset."""
        data = {
            "version": version,
            "scenarios": [s.to_dict() for s in scenarios],
            "metadata": metadata or {},
        }
        path = self._dir / f"v_{version}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._versions[version] = DatasetVersion(
            version=version,
            scenarios=list(scenarios),
            metadata=metadata or {},
        )

    def load_version(self, version: str) -> DatasetVersion | None:
        return self._versions.get(version)

    def list_versions(self) -> list[str]:
        return sorted(self._versions.keys())

    def filter_scenarios(self, version: str, domain: str | None = None) -> list[Scenario]:
        """Filter scenarios by domain."""
        v = self._versions.get(version)
        if not v:
            return []
        if domain:
            return [s for s in v.scenarios if s.domain == domain]
        return v.scenarios

    def sample(self, version: str, n: int) -> list[Scenario]:
        """Sample n scenarios from a version."""
        v = self._versions.get(version)
        if not v:
            return []
        return v.scenarios[:n]

    def compare_versions(self, v1: str, v2: str) -> dict[str, Any]:
        """Compare two dataset versions."""
        ver1 = self._versions.get(v1)
        ver2 = self._versions.get(v2)
        return {
            "v1": {"version": v1, "count": len(ver1.scenarios) if ver1 else 0},
            "v2": {"version": v2, "count": len(ver2.scenarios) if ver2 else 0},
            "diff": (len(ver2.scenarios) if ver2 else 0) - (len(ver1.scenarios) if ver1 else 0),
        }

    def _dict_to_scenario(self, data: dict[str, Any]) -> Scenario:
        from open_agent.eval.scenario import StepAssertion
        assertions = [
            StepAssertion(
                step=a.get("step", 0),
                type=a.get("type", ""),
                tool=a.get("tool"),
                params_contain=a.get("params_contain"),
                expected_value=a.get("expected_value"),
            )
            for a in data.get("step_assertions", [])
        ]
        return Scenario(
            name=data.get("name", ""),
            input=data.get("input", ""),
            expected_tool_calls=data.get("expected_tool_calls", []),
            expected_output=data.get("expected_output", ""),
            step_assertions=assertions,
            domain=data.get("domain", "general"),
        )


def trace_to_eval_case(trace: "Trace") -> Scenario:
    """Convert an execution trace into an editable eval scenario."""
    from open_agent.trace import SpanKind

    tool_calls = []
    for span in trace.spans:
        if span.kind == SpanKind.TOOL_CALL:
            tool_calls.append(span.attributes.get("tool_name", "unknown"))

    final_output = ""
    for span in reversed(trace.spans):
        if span.kind == SpanKind.AGENT_LOOP:
            final_output = span.attributes.get("output", "")
            break

    return Scenario(
        name=f"trace_{trace.trace_id[:8]}",
        input=trace.metadata.get("user_input", ""),
        expected_tool_calls=tool_calls,
        expected_output=final_output,
        step_assertions=[],
        metadata={"trace_id": trace.trace_id},
    )
