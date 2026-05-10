"""Dynamic SkillRegistry — runtime register/unregister/list/match."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from open_agent.skills.parser import Skill, SkillMeta, parse_skill_file

logger = logging.getLogger("open_agent")

# Built-in skills directory (relative to this package)
_BUILTIN_SKILLS_DIR = Path(__file__).parent / "builtin"


class SkillRegistry:
    """Dynamic skill registry with lazy loading and domain-based matching."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, name: str, meta: SkillMeta, file_path: str | None = None) -> Skill:
        """Register a skill. Only stores metadata; content loaded lazily."""
        if name in self._skills:
            raise ValueError(f"Skill already registered: {name}")
        skill = Skill(meta=meta, file_path=file_path)
        self._skills[name] = skill
        return skill

    def unregister(self, name: str) -> None:
        """Remove a skill from the registry."""
        if name not in self._skills:
            raise KeyError(f"Skill not found: {name}")
        del self._skills[name]

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"Skill not found: {name}")
        return self._skills[name]

    def list_skills(self) -> list[SkillMeta]:
        """List all registered skill metadata."""
        return [s.meta for s in self._skills.values()]

    def list_by_domain(self, domain: str) -> list[SkillMeta]:
        """List skills matching a domain."""
        return [s.meta for s in self._skills.values() if s.meta.domain == domain]

    def match_skills(self, domain: str, user_input: str) -> list[Skill]:
        """Match skills by domain + trigger keywords. Loads content on match."""
        input_lower = user_input.lower()
        matched = []

        for skill in self._skills.values():
            # Domain match
            if skill.meta.domain != domain and skill.meta.domain != "general":
                continue

            # Trigger keyword match
            triggered = any(
                kw.lower() in input_lower
                for kw in skill.meta.trigger
            )

            if triggered:
                skill.load_content()
                matched.append(skill)

        return matched

    def load_content(self, name: str) -> str:
        """Lazy-load a skill's content."""
        skill = self.get(name)
        return skill.load_content()

    def cleanup_content(self, name: str) -> None:
        """Clear a skill's loaded content."""
        skill = self.get(name)
        skill.clear_content()

    def has(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)


def scan_builtin_skills(registry: SkillRegistry) -> int:
    """Scan built-in skills directory and register them. Returns count registered."""
    if not _BUILTIN_SKILLS_DIR.exists():
        return 0

    count = 0
    for skill_file in _BUILTIN_SKILLS_DIR.glob("*.md"):
        meta, error = parse_skill_file(skill_file)
        if error:
            logger.warning(f"Skipping built-in skill {skill_file}: {error}")
            continue
        try:
            registry.register(meta.name, meta, str(skill_file))
            count += 1
        except ValueError:
            logger.debug(f"Built-in skill already registered: {meta.name}")
    return count


def scan_workspace_skills(registry: SkillRegistry, workspace: str | Path) -> int:
    """Scan .skills/ directory in workspace for custom skills."""
    skills_dir = Path(workspace) / ".skills"
    if not skills_dir.exists():
        return 0

    count = 0
    for skill_file in skills_dir.glob("*.md"):
        meta, error = parse_skill_file(skill_file)
        if error:
            logger.warning(f"Skipping workspace skill {skill_file}: {error}")
            continue
        try:
            registry.register(meta.name, meta, str(skill_file))
            count += 1
        except ValueError:
            logger.debug(f"Workspace skill already registered: {meta.name}")
    return count
