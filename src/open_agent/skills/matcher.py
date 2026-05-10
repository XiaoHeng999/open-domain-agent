"""Skill matcher — Domain + Trigger dual matching for skill selection."""

from __future__ import annotations

from typing import Any

from open_agent.skills.parser import Skill, SkillMeta
from open_agent.skills.registry import SkillRegistry


class SkillMatcher:
    """Match skills based on domain and trigger keywords."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def match(self, domain: str, user_input: str) -> list[Skill]:
        """Find matching skills for given domain and user input."""
        return self._registry.match_skills(domain, user_input)

    def get_skills_for_prompt(self, domain: str, user_input: str) -> list[dict[str, Any]]:
        """Get matched skills formatted for injection into Agent system prompt."""
        matched = self.match(domain, user_input)
        result = []
        for skill in matched:
            content = skill.load_content()
            result.append({
                "name": skill.meta.name,
                "domain": skill.meta.domain,
                "content": content,
                "tools": skill.meta.tools,
            })
        return result

    def cleanup(self, domain: str, user_input: str) -> None:
        """Clean up loaded skill content after task completion."""
        matched = self._registry.match_skills(domain, user_input)
        for skill in matched:
            skill.clear_content()
