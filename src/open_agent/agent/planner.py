"""Optional Planning Step — generate a guidance plan for complex tasks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from open_agent.trace import Span, SpanKind, Trace
from open_agent.model import parse_json_response

logger = logging.getLogger("open_agent")


@dataclass
class Plan:
    """An ordered list of step descriptions guiding the ReAct loop.

    The plan is advisory: the ReAct loop may deviate from it when
    observations suggest a better path.
    """

    steps: list[str] = field(default_factory=list)
    goal: str = ""

    def current_step(self, index: int) -> str | None:
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    def is_complete(self, index: int) -> bool:
        return index >= len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {"goal": self.goal, "steps": self.steps}


class PlanGenerator:
    """Generate a plan for complex tasks using an LLM provider.

    Falls back to a simple rule-based plan when no provider is available.
    """

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider

    async def generate(
        self,
        user_input: str,
        trace: Trace | None = None,
    ) -> Plan:
        """Generate a plan for *user_input*.

        Returns a :class:`Plan` with an ordered list of step descriptions.
        """
        span: Span | None = None
        if trace:
            span = trace.create_span("plan_generation", kind=SpanKind.AGENT_LOOP)
            span.set_attribute("user_input", user_input)

        try:
            if self._provider:
                plan = await self._llm_generate(user_input)
            else:
                plan = self._rule_generate(user_input)
        except Exception as exc:
            logger.warning("Plan generation failed, using fallback: %s", exc)
            plan = self._rule_generate(user_input)

        if span:
            span.set_attribute("plan_steps", len(plan.steps))
            span.finish()

        return plan

    # -- private helpers -----------------------------------------------------

    async def _llm_generate(self, user_input: str) -> Plan:
        messages = [
            {
                "role": "system",
                "content": (
                    "Break down the following task into ordered steps. "
                    'Respond with JSON: {"goal": "...", "steps": ["step1", "step2", ...]}'
                ),
            },
            {"role": "user", "content": user_input},
        ]
        response = await self._provider.complete_with_tools(messages, [])
        result = parse_json_response(response.text)
        return Plan(
            goal=result.get("goal", user_input),
            steps=result.get("steps", []),
        )

    @staticmethod
    def _rule_generate(user_input: str) -> Plan:
        """Fallback: produce a minimal single-step plan."""
        return Plan(
            goal=user_input,
            steps=[f"Address the user's request: {user_input}"],
        )
