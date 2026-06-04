"""Recovery Engine — Strategy Chain of Responsibility + policy registry.

The engine groups strategies by error type and runs them in order until
one succeeds or the chain is exhausted (at which point it escalates).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from open_agent.errors import ToolError
from open_agent.trace import SpanKind

from .classifier import ErrorClassifier, ToolErrorType
from .strategies import (
    RecoveryResult,
    RecoveryStatus,
    RecoveryStrategy,
    RecoveryTrace,
    ServiceRecoveryStrategy,
    ParseRecoveryStrategy,
    ParameterRecoveryStrategy,
    RetrievalRecoveryStrategy,
)

logger = logging.getLogger("open_agent.recovery")


# ---------------------------------------------------------------------------
# Default strategy chains
# ---------------------------------------------------------------------------

DEFAULT_CHAINS: dict[ToolErrorType, list[RecoveryStrategy]] = {
    ToolErrorType.ParameterError: [ParameterRecoveryStrategy()],
    ToolErrorType.RetrievalError: [RetrievalRecoveryStrategy()],
    ToolErrorType.ServiceError: [ServiceRecoveryStrategy()],
    ToolErrorType.ParseError: [ParseRecoveryStrategy()],
}


# ---------------------------------------------------------------------------
# RecoveryChain
# ---------------------------------------------------------------------------


class RecoveryChain:
    """Ordered sequence of strategies for a single error type.

    Strategies are executed in list order.  The first strategy that
    returns ``RecoveryStatus.SUCCESS`` terminates the chain.  If every
    strategy fails, the chain reports exhaustion.
    """

    def __init__(
        self,
        error_type: ToolErrorType,
        strategies: list[RecoveryStrategy] | None = None,
    ) -> None:
        self.error_type = error_type
        self.strategies: list[RecoveryStrategy] = strategies or []

    def add_strategy(self, strategy: RecoveryStrategy) -> "RecoveryChain":
        """Append *strategy* to the chain. Returns self for fluent API."""
        self.strategies.append(strategy)
        return self

    async def execute(
        self,
        error: ToolError,
        context: dict[str, Any],
    ) -> RecoveryTrace:
        """Run every strategy in order; stop at first success."""
        span = _start_recovery_span(context, self.error_type.value, len(self.strategies))
        overall_start = time.monotonic()
        trace = RecoveryTrace(
            error=error,
            error_type=self.error_type.value,
        )

        for attempt_idx, strategy in enumerate(self.strategies):
            result = await strategy.execute(error, context)
            result.attempt = attempt_idx + 1
            trace.attempts.append(result)

            if result.status == RecoveryStatus.SUCCESS:
                trace.final_status = RecoveryStatus.SUCCESS
                trace.total_duration_ms = (time.monotonic() - overall_start) * 1000
                _finish_recovery_span(span, "success")
                logger.info(
                    "Recovery succeeded: %s (attempt %d) for %s",
                    strategy.name,
                    result.attempt,
                    self.error_type.value,
                )
                return trace

        # Exhausted ----------------------------------------------------------
        trace.final_status = RecoveryStatus.ESCALATE
        trace.total_duration_ms = (time.monotonic() - overall_start) * 1000
        _finish_recovery_span(span, "escalate")
        logger.warning(
            "Recovery chain exhausted for %s — escalating to agent.",
            self.error_type.value,
        )
        self._report_to_agent(trace)
        return trace

    @staticmethod
    def _report_to_agent(trace: RecoveryTrace) -> None:
        """Escalation hook — called when the entire chain fails.

        In production this would emit an event / notification to the
        agent loop so the agent can replan.  For now we log and store
        the trace on the object for downstream inspection.
        """
        logger.error(
            "Escalation: all recovery strategies failed for error type '%s'. "
            "Attempts: %s",
            trace.error_type,
            ", ".join(
                f"{a.strategy_name}({a.status.value})" for a in trace.attempts
            ),
        )


# ---------------------------------------------------------------------------
# RecoveryPolicyRegistry
# ---------------------------------------------------------------------------


class RecoveryPolicyRegistry:
    """Register custom strategies per error type.

    Provides ``register`` to add a strategy for a given
    ``ToolErrorType``.  The registered strategies are merged with (and
    take priority over) the defaults when building a ``RecoveryChain``.
    """

    def __init__(self) -> None:
        self._custom: dict[ToolErrorType, list[RecoveryStrategy]] = {}

    def register(
        self,
        error_type: ToolErrorType,
        strategy: RecoveryStrategy,
    ) -> None:
        """Register *strategy* for *error_type* (prepended to chain)."""
        self._custom.setdefault(error_type, []).insert(0, strategy)

    def get_chain(self, error_type: ToolErrorType) -> RecoveryChain:
        """Build a ``RecoveryChain`` merging custom + default strategies."""
        custom = self._custom.get(error_type, [])
        defaults = DEFAULT_CHAINS.get(error_type, [])
        return RecoveryChain(error_type, custom + list(defaults))

    def clear(self, error_type: ToolErrorType | None = None) -> None:
        """Remove custom strategies.  If *error_type* is None, clear all."""
        if error_type is None:
            self._custom.clear()
        else:
            self._custom.pop(error_type, None)


# ---------------------------------------------------------------------------
# Top-level convenience function
# ---------------------------------------------------------------------------

_default_classifier = ErrorClassifier()
_default_registry = RecoveryPolicyRegistry()


async def execute_recovery_chain(
    error: Exception,
    context: dict[str, Any] | None = None,
    *,
    classifier: ErrorClassifier | None = None,
    policy_registry: RecoveryPolicyRegistry | None = None,
) -> RecoveryTrace:
    """Classify *error*, look up the appropriate chain, and run it.

    This is the main entry-point callers should use.

    Parameters
    ----------
    error:
        The exception to recover from.
    context:
        Arbitrary dict passed to each strategy (tool_handler, args, etc.).
    classifier:
        Optional override for the default ``ErrorClassifier``.
    policy_registry:
        Optional override for the default ``RecoveryPolicyRegistry``.

    Returns
    -------
    RecoveryTrace
        Full audit trail of the recovery attempt.
    """
    ctx = context or {}
    clf = classifier or _default_classifier
    reg = policy_registry or _default_registry

    error_type = clf.classify(error)

    # Wrap non-ToolError exceptions so strategies have a uniform type.
    if not isinstance(error, ToolError):
        wrapped = ToolError(str(error), cause=error)
    else:
        wrapped = error

    chain = reg.get_chain(error_type)
    return await chain.execute(wrapped, ctx)


def _start_recovery_span(context: dict[str, Any], error_type: str, strategy_count: int):
    tm = context.get("_trace_manager")
    tid = context.get("_current_trace_id")
    if tm is None or tid is None:
        return None
    trace_obj = tm.get_trace(tid)
    if trace_obj is None:
        return None
    span = trace_obj.create_span("recovery", kind=SpanKind.RECOVERY)
    span.set_attribute("error_type", error_type)
    span.set_attribute("strategy_count", strategy_count)
    return span


def _finish_recovery_span(span, final_status: str):
    if span is not None:
        span.set_attribute("final_status", final_status)
        span.finish()
