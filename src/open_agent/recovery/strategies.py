"""Recovery Strategies — pluggable strategy implementations per error type.

Each concrete strategy implements RecoveryStrategy.execute which returns a
RecoveryResult indicating success or failure.  Strategies are intentionally
deterministic: no LLM is consulted to choose what to do.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from open_agent.errors import ToolError


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class RecoveryStatus(str, Enum):
    """Outcome of a single recovery attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    ESCALATE = "escalate"


@dataclass
class RecoveryResult:
    """Result returned by every recovery strategy."""

    status: RecoveryStatus
    error_type: str
    strategy_name: str
    attempt: int = 1
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class RecoveryTrace:
    """Audit trail capturing all attempts for a single recovery flow."""

    error: ToolError
    error_type: str
    attempts: list[RecoveryResult] = field(default_factory=list)
    final_status: RecoveryStatus = RecoveryStatus.FAILED
    total_duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class RecoveryStrategy(ABC):
    """Base class for all recovery strategies.

    Subclasses must implement ``execute``.  The *context* dict is the
    primary mechanism for strategies to receive tool metadata, original
    arguments, the tool registry, etc.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def execute(
        self,
        error: ToolError,
        context: dict[str, Any],
    ) -> RecoveryResult:
        """Attempt recovery and return a ``RecoveryResult``."""
        ...


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------


class ParameterRecoveryStrategy(RecoveryStrategy):
    """Fix parameters and retry.

    Steps:
    1. If ``context["fixed_args"]`` is provided, merge them with the
       original ``context["args"]`` to produce corrected arguments.
    2. If a ``context["tool_registry"]`` is available and the tool's
       schema declares default values, fill missing parameters.
    3. Retry execution via ``context["tool_handler"]`` if available.
    """

    async def execute(
        self,
        error: ToolError,
        context: dict[str, Any],
    ) -> RecoveryResult:
        start = time.monotonic()
        args: dict[str, Any] = dict(context.get("args", {}))

        # Merge fixed_args if caller supplied corrections ---------------
        fixed_args = context.get("fixed_args")
        if fixed_args and isinstance(fixed_args, dict):
            args.update(fixed_args)

        # Fill defaults from schema -------------------------------------
        schema = context.get("tool_schema", {})
        properties = schema.get("inputSchema", {}).get("properties", {})
        for prop_name, prop_def in properties.items():
            if prop_name not in args and "default" in prop_def:
                args[prop_name] = prop_def["default"]

        # Attempt retry -------------------------------------------------
        tool_handler: Callable[..., Any] | None = context.get("tool_handler")
        if tool_handler is not None:
            try:
                result = tool_handler(**args)
                if asyncio.iscoroutine(result):
                    result = await result
                return RecoveryResult(
                    status=RecoveryStatus.SUCCESS,
                    error_type="parameter_error",
                    strategy_name=self.name,
                    message="Parameters corrected; retry succeeded.",
                    data={"corrected_args": args, "result": result},
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            except Exception as retry_err:
                return RecoveryResult(
                    status=RecoveryStatus.FAILED,
                    error_type="parameter_error",
                    strategy_name=self.name,
                    message=f"Retry with corrected params failed: {retry_err}",
                    data={"corrected_args": args},
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        return RecoveryResult(
            status=RecoveryStatus.FAILED,
            error_type="parameter_error",
            strategy_name=self.name,
            message="No tool_handler in context; cannot retry.",
            data={"corrected_args": args},
            duration_ms=(time.monotonic() - start) * 1000,
        )


class RetrievalRecoveryStrategy(RecoveryStrategy):
    """Expand query / relax filters / use cache.

    Runs through up to three sub-steps in order, stopping at first success:
    1. ``expand_query`` — broaden the search query string.
    2. ``relax_filters`` — remove the most restrictive filter keys.
    3. ``use_cache`` — return a stale-but-acceptable cached result.
    """

    async def execute(
        self,
        error: ToolError,
        context: dict[str, Any],
    ) -> RecoveryResult:
        start = time.monotonic()
        args: dict[str, Any] = dict(context.get("args", {}))

        # Step 1 — expand query -----------------------------------------
        query = args.get("query", args.get("q", ""))
        if query:
            expanded = self._expand_query(str(query))
            args["query"] = expanded
            tool_handler = context.get("tool_handler")
            if tool_handler is not None:
                try:
                    result = tool_handler(**args)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return RecoveryResult(
                        status=RecoveryStatus.SUCCESS,
                        error_type="retrieval_error",
                        strategy_name=self.name,
                        message="Query expanded; retry succeeded.",
                        data={"expanded_query": expanded, "result": result},
                        duration_ms=(time.monotonic() - start) * 1000,
                    )
                except Exception:
                    pass  # fall through to next step

        # Step 2 — relax filters ----------------------------------------
        filters = args.get("filters", args.get("filter"))
        if isinstance(filters, dict) and filters:
            relaxed = self._relax_filters(filters)
            args["filters"] = relaxed
            tool_handler = context.get("tool_handler")
            if tool_handler is not None:
                try:
                    result = tool_handler(**args)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return RecoveryResult(
                        status=RecoveryStatus.SUCCESS,
                        error_type="retrieval_error",
                        strategy_name=self.name,
                        message="Filters relaxed; retry succeeded.",
                        data={"relaxed_filters": relaxed, "result": result},
                        duration_ms=(time.monotonic() - start) * 1000,
                    )
                except Exception:
                    pass  # fall through

        # Step 3 — use cache --------------------------------------------
        cache = context.get("cache")
        cache_key = context.get("cache_key", query)
        if cache is not None and cache_key:
            cached = cache.get(str(cache_key))
            if cached is not None:
                return RecoveryResult(
                    status=RecoveryStatus.SUCCESS,
                    error_type="retrieval_error",
                    strategy_name=self.name,
                    message="Served from cache.",
                    data={"cache_key": str(cache_key), "result": cached},
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        return RecoveryResult(
            status=RecoveryStatus.FAILED,
            error_type="retrieval_error",
            strategy_name=self.name,
            message="expand_query, relax_filters, and use_cache all failed.",
            duration_ms=(time.monotonic() - start) * 1000,
        )

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _expand_query(query: str) -> str:
        """Simple query expansion: append a broader synonym hint."""
        return f"{query} OR *"

    @staticmethod
    def _relax_filters(filters: dict[str, Any]) -> dict[str, Any]:
        """Drop the most specific (longest value) filter entry."""
        if not filters:
            return filters
        longest_key = max(filters, key=lambda k: len(str(filters[k])))
        return {k: v for k, v in filters.items() if k != longest_key}


class ServiceRecoveryStrategy(RecoveryStrategy):
    """Exponential backoff retry (max 3 attempts), then fallback tool lookup.

    The backoff sequence is: 0.1s, 0.2s, 0.4s.  If all retries fail, look
    for a fallback tool tagged ``fallback`` in the tool registry.
    """

    MAX_RETRIES: int = 3
    BASE_DELAY: float = 0.1  # seconds

    async def execute(
        self,
        error: ToolError,
        context: dict[str, Any],
    ) -> RecoveryResult:
        start = time.monotonic()
        tool_handler = context.get("tool_handler")
        args: dict[str, Any] = dict(context.get("args", {}))

        # Phase 1 — exponential backoff retries -------------------------
        last_exc: Exception | None = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            delay = self.BASE_DELAY * (2 ** (attempt - 1))
            await asyncio.sleep(delay)
            if tool_handler is not None:
                try:
                    result = tool_handler(**args)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return RecoveryResult(
                        status=RecoveryStatus.SUCCESS,
                        error_type="service_error",
                        strategy_name=self.name,
                        attempt=attempt,
                        message=f"Retry attempt {attempt} succeeded.",
                        data={"result": result, "attempts": attempt},
                        duration_ms=(time.monotonic() - start) * 1000,
                    )
                except Exception as exc:
                    last_exc = exc

        # Phase 2 — fallback tool lookup --------------------------------
        registry = context.get("tool_registry")
        if registry is not None:
            fallback_tools = registry.list_by_tag("fallback")
            for entry in fallback_tools:
                try:
                    result = await entry.execute(**args)
                    return RecoveryResult(
                        status=RecoveryStatus.SUCCESS,
                        error_type="service_error",
                        strategy_name=self.name,
                        attempt=self.MAX_RETRIES + 1,
                        message=f"Fallback tool '{entry.name}' succeeded.",
                        data={"fallback_tool": entry.name, "result": result},
                        duration_ms=(time.monotonic() - start) * 1000,
                    )
                except Exception:
                    continue

        msg = f"All {self.MAX_RETRIES} retries failed"
        if last_exc:
            msg += f" (last: {last_exc})"
        return RecoveryResult(
            status=RecoveryStatus.FAILED,
            error_type="service_error",
            strategy_name=self.name,
            attempt=self.MAX_RETRIES,
            message=msg,
            duration_ms=(time.monotonic() - start) * 1000,
        )


class ParseRecoveryStrategy(RecoveryStrategy):
    """Switch output format, then attempt LLM-assisted repair.

    Steps:
    1. Try parsing with an alternate format (e.g. switch json → text).
    2. If ``context["llm_assist"]`` is a callable, invoke it to repair
       the raw output and re-parse.
    """

    FORMAT_PRIORITY: list[str] = ["json", "text", "csv"]

    async def execute(
        self,
        error: ToolError,
        context: dict[str, Any],
    ) -> RecoveryResult:
        start = time.monotonic()
        raw_output = context.get("raw_output", "")
        requested_format = context.get("format", "json")

        # Step 1 — try alternate formats --------------------------------
        for fmt in self.FORMAT_PRIORITY:
            if fmt == requested_format:
                continue
            parsed = self._try_parse(raw_output, fmt)
            if parsed is not None:
                return RecoveryResult(
                    status=RecoveryStatus.SUCCESS,
                    error_type="parse_error",
                    strategy_name=self.name,
                    message=f"Parsed using alternate format '{fmt}'.",
                    data={"format": fmt, "result": parsed},
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        # Step 2 — LLM assist ------------------------------------------
        llm_assist: Callable[..., Any] | None = context.get("llm_assist")
        if llm_assist is not None:
            try:
                repaired = llm_assist(raw_output)
                if asyncio.iscoroutine(repaired):
                    repaired = await repaired
                return RecoveryResult(
                    status=RecoveryStatus.SUCCESS,
                    error_type="parse_error",
                    strategy_name=self.name,
                    message="LLM-assisted parse repair succeeded.",
                    data={"result": repaired, "method": "llm_assist"},
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            except Exception:
                pass

        return RecoveryResult(
            status=RecoveryStatus.FAILED,
            error_type="parse_error",
            strategy_name=self.name,
            message="All format switches and LLM assist failed.",
            duration_ms=(time.monotonic() - start) * 1000,
        )

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _try_parse(raw: str, fmt: str) -> Any:
        """Best-effort parse of *raw* into a Python object."""
        import csv
        import io
        import json

        if fmt == "json":
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return None
        if fmt == "text":
            if raw.strip():
                return {"text": raw.strip()}
            return None
        if fmt == "csv":
            try:
                reader = csv.DictReader(io.StringIO(raw))
                rows = list(reader)
                return rows if rows else None
            except Exception:
                return None
        return None
