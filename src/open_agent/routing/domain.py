"""Domain Router — routes requests to domain-specific agents."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from open_agent.base import BaseComponent
from open_agent.errors import RoutingError
from open_agent.model import parse_json_response

logger = logging.getLogger("open_agent")

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

_DOMAIN_SYSTEM_PROMPT_TEMPLATE = (
    "You are a domain classifier for a multi-domain AI agent. "
    "Given a user message, classify it into one of the following domains:\n\n"
    "{domains_description}\n\n"
    "Rules:\n"
    "- Choose the single best-fitting domain\n"
    "- If no domain is a clear match, choose 'general'\n"
    "- Support both Chinese and English input\n"
    'Respond with JSON: {{"domain": "<domain_name>", "candidates": ["<best>", "<second>", ...]}}'
)


@dataclass
class DomainRouteResult:
    """Result of domain routing."""

    domain: str
    candidates: list[str]
    routed_as_fallback: bool
    system_prompt: str = ""


class DomainRouter(BaseComponent):
    """Route requests to domain agents.

    For built-in domains (those present at construction time): uses LLM when a
    provider is supplied, otherwise falls back to keyword matching.
    For dynamically registered domains (added via ``register_domain``): always
    uses keyword matching, regardless of whether a provider is available.
    """

    def __init__(
        self,
        domains: dict[str, dict[str, Any]] | None = None,
        provider: Any = None,
    ) -> None:
        super().__init__()
        self._domains = domains or _DOMAINS.copy()
        self._provider = provider
        self._builtin_domain_names: set[str] = set(self._domains.keys())

    # -- public API ----------------------------------------------------------

    async def route(self, user_input: str) -> DomainRouteResult:
        """Route user input to the best-matching domain.

        Strategy:
        1. Dynamic domains → keyword matching (authoritative).
        2. Built-in domains → LLM if provider available, else keywords.
        Raises ``RoutingError`` when the LLM call fails.
        """
        # 1. Check dynamic domains via keywords first
        dynamic_domains = {
            k: v for k, v in self._domains.items()
            if k not in self._builtin_domain_names
        }
        if dynamic_domains:
            kw_result = self._route_keywords_subset(user_input, dynamic_domains)
            if not kw_result.routed_as_fallback:
                return kw_result

        # 2. Built-in domains
        if self._provider is not None:
            return await self._route_llm(user_input)
        return self._route_keywords_subset(user_input, self._domains)

    def register_domain(
        self,
        name: str,
        system_prompt: str,
        keywords: list[str] | None = None,
    ) -> None:
        """Register a new domain."""
        self._domains[name] = {
            "keywords": keywords or [],
            "system_prompt": system_prompt,
        }

    def list_domains(self) -> list[str]:
        return list(self._domains.keys())

    # -- LLM-based routing ---------------------------------------------------

    def _build_domain_system_prompt(self) -> str:
        """Build system prompt with built-in domain descriptions."""
        lines: list[str] = []
        for name in sorted(self._builtin_domain_names):
            cfg = self._domains.get(name, {})
            lines.append(f"- **{name}**: {cfg.get('system_prompt', '')}")
        description = "\n".join(lines)
        return _DOMAIN_SYSTEM_PROMPT_TEMPLATE.format(domains_description=description)

    async def _route_llm(self, user_input: str) -> DomainRouteResult:
        """Route via LLM for built-in domains. Raises RoutingError on failure."""
        system_prompt = self._build_domain_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        try:
            response = await self._provider.complete_with_tools(messages, [])
            result = parse_json_response(response.text)
        except Exception as exc:
            raise RoutingError(f"LLM domain routing failed: {exc}") from exc

        domain = result.get("domain", "general")
        if domain not in self._domains:
            domain = "general"

        candidates = result.get("candidates", [domain])
        candidates = [c for c in candidates if c in self._domains]
        if not candidates:
            candidates = [domain]

        return DomainRouteResult(
            domain=domain,
            candidates=candidates,
            routed_as_fallback=(domain == "general"),
            system_prompt=self._domains[domain].get("system_prompt", ""),
        )

    # -- keyword-based routing -----------------------------------------------

    def _route_keywords_subset(
        self,
        user_input: str,
        domains: dict[str, dict[str, Any]],
    ) -> DomainRouteResult:
        """Pure keyword matching on a subset of domains."""
        input_lower = user_input.lower()
        scores: dict[str, int] = {}

        for domain_name, domain_config in domains.items():
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
            system_prompt=self._domains.get("general", {}).get("system_prompt", ""),
        )
