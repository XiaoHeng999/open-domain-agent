"""Cost tracking — accumulates per-model token usage with configurable pricing."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


# Default pricing per 1M tokens (USD)
DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "deepseek-chat": {"input": 0.27, "output": 1.10},
}


class CostTracker:
    """Accumulates per-model, per-day token usage with budget alerts."""

    def __init__(self, pricing: dict[str, dict[str, float]] | None = None) -> None:
        self._pricing = pricing or DEFAULT_PRICING
        self._records: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for a model."""
        self._records[model].append({
            "timestamp": datetime.now(timezone.utc),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })

    def get_daily_summary(self) -> dict[str, dict[str, int]]:
        """Return today's token usage aggregated by model."""
        return self._aggregate(days=1)

    def get_weekly_summary(self) -> dict[str, dict[str, int]]:
        """Return last 7 days' token usage aggregated by model."""
        return self._aggregate(days=7)

    def check_budget(self, limit: float) -> dict[str, Any]:
        """Check whether total cost exceeds the budget limit (USD)."""
        total_cost = self._compute_cost()
        return {
            "total_cost": total_cost,
            "over_budget": total_cost > limit,
            "limit": limit,
        }

    def _aggregate(self, days: int) -> dict[str, dict[str, int]]:
        """Aggregate token usage for the last N days."""
        now = datetime.now(timezone.utc)
        summary: dict[str, dict[str, int]] = {}
        for model, records in self._records.items():
            total_input = 0
            total_output = 0
            for rec in records:
                if (now - rec["timestamp"]).days < days:
                    total_input += rec["input_tokens"]
                    total_output += rec["output_tokens"]
            if total_input or total_output:
                summary[model] = {
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                }
        return summary

    def _compute_cost(self) -> float:
        """Compute total cost across all records using pricing table."""
        total = 0.0
        summary = self._aggregate(days=1)
        for model, tokens in summary.items():
            rates = self._pricing.get(model, {"input": 0.0, "output": 0.0})
            total += tokens["input_tokens"] * rates["input"] / 1_000_000
            total += tokens["output_tokens"] * rates["output"] / 1_000_000
        return total
