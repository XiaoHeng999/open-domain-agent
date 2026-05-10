"""Skill file parser — Markdown + YAML frontmatter parsing + directory skill support."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillMeta:
    """YAML frontmatter metadata for a skill."""

    name: str
    description: str = ""
    domain: str = "general"
    tools: list[str] = field(default_factory=list)
    trigger: list[str] = field(default_factory=list)  # trigger keywords

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "tools": self.tools,
            "trigger": self.trigger,
        }


@dataclass
class Skill:
    """A loaded skill with metadata and content."""

    meta: SkillMeta
    content: str = ""  # Markdown body, loaded lazily
    file_path: str | None = None
    _content_loaded: bool = False

    def load_content(self) -> str:
        """Lazy-load the Markdown body from file."""
        if not self._content_loaded and self.file_path:
            path = Path(self.file_path)
            if path.exists():
                self.content = path.read_text(encoding="utf-8")
                # Remove frontmatter from content
                self.content = _strip_frontmatter(self.content)
                self._content_loaded = True
        return self.content

    def clear_content(self) -> None:
        """Clear loaded content to free memory."""
        self.content = ""
        self._content_loaded = False


def parse_skill_file(file_path: str | Path) -> tuple[SkillMeta | None, str | None]:
    """Parse a skill file. Returns (meta, content) or (None, error_reason)."""
    path = Path(file_path)
    if not path.exists():
        return None, f"File not found: {file_path}"

    text = path.read_text(encoding="utf-8")
    meta, error = _parse_frontmatter(text, str(path))

    if error:
        return None, error

    if meta is None:
        return None, f"No frontmatter found in: {file_path}"

    return meta, None


def parse_skill_directory(dir_path: str | Path) -> tuple[SkillMeta | None, str | None, Path | None]:
    """Parse a skill directory. Returns (meta, error, skill_md_path).

    The directory must contain a ``SKILL.md`` file with YAML frontmatter.
    Only ``name`` and ``description`` are required in the frontmatter.
    """
    directory = Path(dir_path)
    if not directory.is_dir():
        return None, f"Not a directory: {dir_path}", None

    skill_md = directory / "SKILL.md"
    if not skill_md.exists():
        return None, f"No SKILL.md in directory: {dir_path}", None

    meta, error = parse_skill_file(skill_md)
    if error:
        return None, error, None

    return meta, None, skill_md


def _parse_frontmatter(text: str, source: str = "") -> tuple[SkillMeta | None, str | None]:
    """Parse YAML frontmatter from Markdown text."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return None, f"No YAML frontmatter in: {source}"

    yaml_text = match.group(1)
    try:
        import yaml
        data = yaml.safe_load(yaml_text)
    except Exception as e:
        return None, f"YAML parse error in {source}: {e}"

    if not isinstance(data, dict):
        return None, f"Invalid frontmatter format in: {source}"

    # Validate required fields — only 'name' is required
    if "name" not in data:
        return None, f"Missing required field 'name' in: {source}"

    # Handle trigger — can be string with | or list
    trigger = data.get("trigger", [])
    if isinstance(trigger, str):
        trigger = [t.strip() for t in trigger.split("|")]
    elif not isinstance(trigger, list):
        trigger = [str(trigger)]

    meta = SkillMeta(
        name=data["name"],
        description=data.get("description", ""),
        domain=data.get("domain", "general"),
        tools=data.get("tools", []),
        trigger=trigger,
    )
    return meta, None


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from text, return body."""
    match = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.DOTALL)
    if match:
        return text[match.end():]
    return text
