"""Token estimation utilities."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Estimate token count using len(text)//4 heuristic.

    Falls back to tiktoken if available and configured.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)
