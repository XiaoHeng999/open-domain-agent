"""Domain Router — routes requests to domain-specific agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent

# Domain definitions with keywords and system prompts
_DOMAINS: dict[str, dict[str, Any]] = {
    "coding": {
        "keywords": ["代码", "编程", "函数", "bug", "debug", "code", "program", "function",
                     "refactor", "review", "implement", "python", "javascript", "typescript",
                     "git", "compile", "error", "test"],
        "system_prompt": "You are an expert coding assistant. Focus on writing clean, efficient code.",
    },
    "search": {
        "keywords": ["搜索", "查找", "查询", "search", "find", "look up", "查询", "信息"],
        "system_prompt": "You are a search and information retrieval specialist. Find accurate, relevant information.",
    },
    "web": {
        "keywords": ["网页", "网站", "浏览器", "web", "browser", "website", "html", "css",
                     "scrape", "crawl", "http"],
        "system_prompt": "You are a web interaction specialist. Help with web-related tasks.",
    },
    "general": {
        "keywords": [],
        "system_prompt": "You are a helpful general-purpose assistant.",
    },
}


@dataclass
class DomainRouteResult:
    """Result of domain routing."""

    domain: str
    candidates: list[str]
    routed_as_fallback: bool
    system_prompt: str = ""


class DomainRouter(BaseComponent):
    """Route requests to domain agents based on keyword matching."""

    def __init__(self, domains: dict[str, dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._domains = domains or _DOMAINS

    def route(self, user_input: str) -> DomainRouteResult:
        """Route user input to the best-matching domain."""
        input_lower = user_input.lower()
        scores: dict[str, int] = {}

        for domain_name, domain_config in self._domains.items():
            keywords = domain_config.get("keywords", [])
            score = sum(1 for kw in keywords if kw in input_lower)
            if score > 0:
                scores[domain_name] = score

        if scores:
            best_domain = max(scores, key=scores.get)  # type: ignore
            candidates = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
            return DomainRouteResult(
                domain=best_domain,
                candidates=candidates,
                routed_as_fallback=False,
                system_prompt=self._domains[best_domain].get("system_prompt", ""),
            )

        return DomainRouteResult(
            domain="general",
            candidates=["general"],
            routed_as_fallback=True,
            system_prompt=self._domains["general"].get("system_prompt", ""),
        )

    def register_domain(self, name: str, system_prompt: str, keywords: list[str] | None = None) -> None:
        """Register a new domain."""
        self._domains[name] = {
            "keywords": keywords or [],
            "system_prompt": system_prompt,
        }

    def list_domains(self) -> list[str]:
        return list(self._domains.keys())
