"""Tests for directory skill package support — SKILL.md discovery and parsing."""

from __future__ import annotations

import pytest

from open_agent.skills.parser import parse_skill_directory, parse_skill_file
from open_agent.skills.registry import SkillRegistry, scan_builtin_skills


class TestParseSkillDirectory:
    def test_valid_directory_skill(self, tmp_path):
        skill_dir = tmp_path / "weather"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: weather
description: Weather queries
---

## Instructions
Check the weather.
""")

        meta, error, md_path = parse_skill_directory(skill_dir)
        assert error is None
        assert meta is not None
        assert meta.name == "weather"
        assert md_path is not None
        assert md_path.name == "SKILL.md"

    def test_directory_with_scripts(self, tmp_path):
        skill_dir = tmp_path / "my-tool"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: my-tool
description: A tool
---

Content here.
""")
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "helper.py").write_text("print('hello')")

        meta, error, md_path = parse_skill_directory(skill_dir)
        assert error is None
        assert meta is not None
        assert meta.name == "my-tool"

    def test_directory_without_skill_md_fails(self, tmp_path):
        skill_dir = tmp_path / "broken"
        skill_dir.mkdir()
        (skill_dir / "README.md").write_text("not a skill")

        meta, error, md_path = parse_skill_directory(skill_dir)
        assert error is not None
        assert "SKILL.md" in error

    def test_not_a_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        meta, error, md_path = parse_skill_directory(f)
        assert error is not None

    def test_skill_md_only_requires_name(self, tmp_path):
        """SKILL.md only requires 'name' — domain is optional."""
        skill_dir = tmp_path / "minimal"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: minimal
description: A minimal skill
---

Content.
""")
        meta, error, md_path = parse_skill_directory(skill_dir)
        assert error is None
        assert meta is not None
        assert meta.domain == "general"  # default


class TestScanBuiltinDirectorySkills:
    def test_builtin_skills_include_directory_skills(self):
        registry = SkillRegistry()
        count = scan_builtin_skills(registry)
        # Should find at least the 3 existing single-file skills + 4 directory skills
        assert count >= 3

    def test_builtin_skill_creator_found(self):
        registry = SkillRegistry()
        scan_builtin_skills(registry)
        assert registry.has("skill-creator")

    def test_builtin_summarize_found(self):
        registry = SkillRegistry()
        scan_builtin_skills(registry)
        assert registry.has("summarize")

    def test_builtin_weather_found(self):
        registry = SkillRegistry()
        scan_builtin_skills(registry)
        assert registry.has("weather")

    def test_builtin_github_found(self):
        registry = SkillRegistry()
        scan_builtin_skills(registry)
        assert registry.has("github")


class TestSkillContentLoading:
    def test_skill_md_content_loads(self, tmp_path):
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---

# Test Skill

Detailed instructions here.
""")
        meta, error, md_path = parse_skill_directory(skill_dir)
        assert meta is not None

        registry = SkillRegistry()
        registry.register("test-skill", meta, str(md_path))
        skill = registry.get("test-skill")
        content = skill.load_content()
        assert "Detailed instructions here." in content
        assert "---" not in content  # frontmatter stripped
