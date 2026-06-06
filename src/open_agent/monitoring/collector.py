"""Online monitoring — trace collection, anomaly detection, quality scoring."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from open_agent.trace import SpanKind, Trace, TraceManager


@dataclass
class AnomalyAlert:
    """An anomaly detected during execution."""

    alert_type: str  # tool_loop, repeated_error, token_anomaly, timeout
    severity: str = "warning"  # warning, critical
    details: dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass
class QualityScore:
    """Quality score (0-100) for an execution."""

    score: float
    task_completed: float  # 0 or 1
    tool_efficiency: float  # 0-1
    token_efficiency: float  # 0-1
    no_errors: float  # 0-1
    breakdown: dict[str, float] = field(default_factory=dict)


class TraceCollector:
    """Collect complete traces across all modules."""

    def __init__(self, trace_manager: TraceManager) -> None:
        self._trace_manager = trace_manager

    def collect_trace(self, trace_id: str) -> Trace | None:
        """Get complete trace by ID."""
        return self._trace_manager.get_trace(trace_id)

    def query_live_spans(self, trace_id: str, kind: SpanKind | None = None) -> list[dict[str, Any]]:
        """Query partial trace for real-time monitoring."""
        trace = self._trace_manager.get_trace(trace_id)
        if not trace:
            return []
        spans = trace.spans
        if kind:
            spans = [s for s in spans if s.kind == kind]
        return [s.to_dict() for s in spans]


class AnomalyDetector:
    """Detect anomalies in execution traces."""

    def detect(self, trace: Trace) -> list[AnomalyAlert]:
        """Run all anomaly detectors on a trace."""
        alerts: list[AnomalyAlert] = []
        alerts.extend(self._detect_tool_loops(trace))
        alerts.extend(self._detect_repeated_errors(trace))
        alerts.extend(self._detect_timeouts(trace))
        return alerts

    def _detect_tool_loops(self, trace: Trace) -> list[AnomalyAlert]:
        """Detect tool call loops — 3+ calls to same tool with similar params."""
        alerts = []
        tool_calls: dict[str, list[dict[str, Any]]] = {}

        for span in trace.spans:
            if span.kind == SpanKind.TOOL_CALL:
                tool_name = span.attributes.get("tool_name", "unknown")
                if tool_name not in tool_calls:
                    tool_calls[tool_name] = []
                tool_calls[tool_name].append(span.to_dict())

        for tool_name, calls in tool_calls.items():
            if len(calls) >= 3:
                alerts.append(AnomalyAlert(
                    alert_type="tool_loop",
                    severity="warning",
                    message=f"Tool '{tool_name}' called {len(calls)} times — possible loop",
                    details={"tool": tool_name, "count": len(calls)},
                ))

        return alerts

    def _detect_repeated_errors(self, trace: Trace) -> list[AnomalyAlert]:
        """Detect repeated errors of the same type."""
        alerts = []
        errors: dict[str, int] = {}

        for span in trace.spans:
            if span.status.value == "error" and span.error_message:
                error_type = span.error_message.split(":")[0]
                errors[error_type] = errors.get(error_type, 0) + 1

        for error_type, count in errors.items():
            if count >= 2:
                alerts.append(AnomalyAlert(
                    alert_type="repeated_error",
                    severity="critical" if count >= 3 else "warning",
                    message=f"Error '{error_type}' occurred {count} times",
                    details={"error_type": error_type, "count": count},
                ))

        return alerts

    def _detect_timeouts(self, trace: Trace) -> list[AnomalyAlert]:
        """Detect execution timeouts — spans over 60s."""
        alerts = []
        for span in trace.spans:
            if span.duration_ms and span.duration_ms > 60000:
                alerts.append(AnomalyAlert(
                    alert_type="timeout",
                    severity="warning",
                    message=f"Operation '{span.operation}' took {span.duration_ms:.0f}ms",
                    details={"operation": span.operation, "duration_ms": span.duration_ms},
                ))
        return alerts


class QualityScorer:
    """Compute quality score for an execution trace.

    Real-time quality scoring for the agent loop. For post-hoc evaluation
    metrics, see eval.metrics.compute_metrics().
    """

    def score(self, trace: Trace) -> QualityScore:
        """Calculate weighted quality score.

        Formula: task_completed(40%) + tool_efficiency(30%) + token_efficiency(20%) + no_errors(10%)
        """
        task_completed = self._calc_task_completed(trace)
        tool_efficiency = self._calc_tool_efficiency(trace)
        token_efficiency = self._calc_token_efficiency(trace)
        no_errors = self._calc_no_errors(trace)

        raw = (
            task_completed * 40
            + tool_efficiency * 30
            + token_efficiency * 20
            + no_errors * 10
        )

        return QualityScore(
            score=min(100.0, raw),
            task_completed=task_completed,
            tool_efficiency=tool_efficiency,
            token_efficiency=token_efficiency,
            no_errors=no_errors,
            breakdown={
                "task_completed": task_completed,
                "tool_efficiency": tool_efficiency,
                "token_efficiency": token_efficiency,
                "no_errors": no_errors,
            },
        )

    def _calc_task_completed(self, trace: Trace) -> float:
        # Check if there's an agent_loop span with OK status at the end
        for span in reversed(trace.spans):
            if span.kind == SpanKind.AGENT_LOOP and span.status.value == "ok":
                return 1.0
        return 0.0

    def _calc_tool_efficiency(self, trace: Trace) -> float:
        tool_spans = [s for s in trace.spans if s.kind == SpanKind.TOOL_CALL]
        if not tool_spans:
            return 1.0
        successful = sum(1 for s in tool_spans if s.status.value == "ok")
        return successful / len(tool_spans)

    def _calc_token_efficiency(self, trace: Trace) -> float:
        # Fewer spans = more efficient
        span_count = len(trace.spans)
        if span_count <= 3:
            return 1.0
        if span_count <= 6:
            return 0.8
        if span_count <= 10:
            return 0.6
        return 0.4

    def _calc_no_errors(self, trace: Trace) -> float:
        total = len(trace.spans)
        if total == 0:
            return 1.0
        errors = sum(1 for s in trace.spans if s.status.value == "error")
        return 1.0 - (errors / total)


class FeedbackLoop:
    """Route monitoring findings back into execution."""

    def generate_avoidance_hint(self, error_pattern: str, context: dict[str, Any]) -> dict[str, Any]:
        """Generate an avoidance hint from an error pattern."""
        return {
            "pattern": error_pattern,
            "context": context,
            "hint": f"Avoid: {error_pattern} in similar contexts",
            "created_at": time.time(),
        }

    def suggest_eval_case(self, trace: Trace, quality_score: QualityScore) -> dict[str, Any] | None:
        """Suggest eval case from high-quality trace."""
        if quality_score.score < 80:
            return None

        return {
            "suggestion_type": "eval_case",
            "trace_id": trace.trace_id,
            "quality_score": quality_score.score,
            "reason": f"High-quality execution (score: {quality_score.score:.0f}) — good eval candidate",
        }
