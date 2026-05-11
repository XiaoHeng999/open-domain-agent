"""Session Todo Tool — LLM-driven task plan management.

Implements the `todo` tool that lets the LLM manage multi-step task plans
via standard tool calls. Uses whole-list replacement (no incremental ops).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from open_agent.decorators import tool_schema


@dataclass
class TodoItem:
    """A single task item in the plan."""

    content: str
    status: str = "pending"  # pending | in_progress | completed
    activeForm: str = ""

    STATUS_MARKERS = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}

    def marker(self) -> str:
        return self.STATUS_MARKERS.get(self.status, "[ ]")


class TodoManager:
    """Manages a session-level task plan with whole-list replacement.

    Invariants:
    - At most one item may have status="in_progress" at a time.
    - Empty plans produce no prompt injection.
    """

    def __init__(self) -> None:
        self.items: list[TodoItem] = []

    def update(self, items: list[dict[str, Any]]) -> str:
        """Replace the entire plan with a new items list.

        Args:
            items: List of dicts with keys content, status, activeForm.

        Returns:
            Rendered plan text.

        Raises:
            ValueError: If more than one item has status in_progress.
        """
        parsed: list[TodoItem] = []
        in_progress_count = 0

        for raw in items:
            item = TodoItem(
                content=raw.get("content", ""),
                status=raw.get("status", "pending"),
                activeForm=raw.get("activeForm", ""),
            )
            if item.status not in ("pending", "in_progress", "completed"):
                item.status = "pending"
            if item.status == "in_progress":
                in_progress_count += 1
            parsed.append(item)

        if in_progress_count > 1:
            raise ValueError("Only one item can be in_progress")

        self.items = parsed
        return self.render()

    def render(self) -> str:
        """Render the plan as formatted text, or empty string if no items."""
        if not self.items:
            return ""

        lines: list[str] = []
        for item in self.items:
            display = item.activeForm if (item.status == "in_progress" and item.activeForm) else item.content
            lines.append(f"{item.marker()} {display}")
        return "\n".join(lines)

    def has_unfinished(self) -> bool:
        return any(i.status != "completed" for i in self.items)


@tool_schema(
    name="todo",
    description="Manage the current session's task plan. Call with the complete items list to create or update the plan. Each call replaces the entire plan.",
)
def todo_handler(items: list[dict[str, Any]], _todo_manager: TodoManager | None = None) -> str:
    """Update the session task plan.

    Args:
        items: Complete list of plan items. Each item has content (str), status (pending|in_progress|completed), and optional activeForm (str).
    """
    if _todo_manager is None:
        raise RuntimeError("TodoManager not injected")
    return _todo_manager.update(items)


TODO_TOOL_SCHEMA = {
    "name": "todo",
    "description": "Manage the current session's task plan. Call with the complete items list to create or update the plan. Each call replaces the entire plan.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "Complete list of plan items",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Task description",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "Item status",
                        },
                        "activeForm": {
                            "type": "string",
                            "description": "Short spinner text shown when item is in_progress",
                        },
                    },
                    "required": ["content", "status"],
                },
            },
        },
        "required": ["items"],
    },
}
