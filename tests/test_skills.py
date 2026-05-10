"""Tests for skills system."""

from __future__ import annotations

import pytest
from pathlib import Path

from open_agent.skills.parser import SkillMeta, Skill, parse_skill_file
from open_agent.skills.registry import SkillRegistry, scan_builtin_skills, scan_workspace_skills
from open_agent.skills.matcher import SkillMatcher


class TestSkillParser:
    def test_parse_valid_skill(self, tmp_path):
        skill_file = tmp_path / "test-skill.md"
        skill_file.write_text("""---
name: test-skill
description: A test skill
domain: coding
tools: [read, write]
trigger:
  - test
  - 测试
---

## Instructions
Do something useful.
""")
        meta, error = parse_skill_file(skill_file)
        assert error is None
        assert meta is not None
        assert meta.name == "test-skill"
        assert meta.domain == "coding"
        assert len(meta.tools) == 2
        assert len(meta.trigger) == 2

    def test_parse_trigger_pipe_syntax(self, tmp_path):
        skill_file = tmp_path / "pipe-skill.md"
        skill_file.write_text("""---
name: pipe-skill
domain: general
trigger: "hello | world"
---

Body text.
""")
        meta, error = parse_skill_file(skill_file)
        assert error is None
        assert len(meta.trigger) == 2

    def test_missing_name(self, tmp_path):
        skill_file = tmp_path / "bad.md"
        skill_file.write_text("""---
domain: general
---

Body.
""")
        meta, error = parse_skill_file(skill_file)
        assert meta is None
        assert "name" in error

    def test_missing_domain_defaults_to_general(self, tmp_path):
        """domain is optional — defaults to 'general'."""
        skill_file = tmp_path / "no-domain.md"
        skill_file.write_text("""---
name: test
---

Body.
""")
        meta, error = parse_skill_file(skill_file)
        assert meta is not None
        assert meta.domain == "general"

    def test_missing_file(self):
        meta, error = parse_skill_file("/nonexistent/file.md")
        assert meta is None
        assert "not found" in error

    def test_no_frontmatter(self, tmp_path):
        skill_file = tmp_path / "plain.md"
        skill_file.write_text("Just plain text.")
        meta, error = parse_skill_file(skill_file)
        assert meta is None


class TestSkillLazyLoading:
    def test_lazy_content_loading(self, tmp_path):
        skill_file = tmp_path / "lazy.md"
        skill_file.write_text("""---
name: lazy-skill
domain: general
trigger: [lazy]
---

## Lazy Content
This is lazy loaded content.
""")
        meta, _ = parse_skill_file(skill_file)
        skill = Skill(meta=meta, file_path=str(skill_file))
        assert not skill._content_loaded
        content = skill.load_content()
        assert "Lazy Content" in content
        assert skill._content_loaded

    def test_clear_content(self, tmp_path):
        skill_file = tmp_path / "clear.md"
        skill_file.write_text("""---
name: clear-skill
domain: general
trigger: [clear]
---

Content to clear.
""")
        meta, _ = parse_skill_file(skill_file)
        skill = Skill(meta=meta, file_path=str(skill_file))
        skill.load_content()
        assert skill._content_loaded
        skill.clear_content()
        assert not skill._content_loaded
        assert skill.content == ""


class TestSkillRegistry:
    def test_register_and_get(self):
        reg = SkillRegistry()
        meta = SkillMeta(name="test", domain="coding")
        reg.register("test", meta)
        assert reg.has("test")
        skill = reg.get("test")
        assert skill.meta.name == "test"

    def test_duplicate_register(self):
        reg = SkillRegistry()
        meta = SkillMeta(name="dup", domain="general")
        reg.register("dup", meta)
        with pytest.raises(ValueError):
            reg.register("dup", meta)

    def test_unregister(self):
        reg = SkillRegistry()
        meta = SkillMeta(name="rem", domain="general")
        reg.register("rem", meta)
        reg.unregister("rem")
        assert not reg.has("rem")

    def test_list_by_domain(self):
        reg = SkillRegistry()
        reg.register("s1", SkillMeta(name="s1", domain="coding"))
        reg.register("s2", SkillMeta(name="s2", domain="search"))
        reg.register("s3", SkillMeta(name="s3", domain="coding"))
        coding = reg.list_by_domain("coding")
        assert len(coding) == 2

    def test_match_skills(self, tmp_path):
        reg = SkillRegistry()
        skill_file = tmp_path / "match.md"
        skill_file.write_text("""---
name: match-skill
domain: coding
trigger: [review, 审查]
---

Review content.
""")
        meta, _ = parse_skill_file(skill_file)
        reg.register("match-skill", meta, str(skill_file))

        matched = reg.match_skills("coding", "please review my code")
        assert len(matched) == 1
        assert matched[0].meta.name == "match-skill"
        assert matched[0]._content_loaded  # content loaded on match

    def test_match_no_trigger(self):
        reg = SkillRegistry()
        reg.register("s1", SkillMeta(name="s1", domain="coding", trigger=["debug"]))
        matched = reg.match_skills("coding", "write a function")
        assert len(matched) == 0


class TestBuiltinSkills:
    def test_scan_builtin(self):
        reg = SkillRegistry()
        count = scan_builtin_skills(reg)
        assert count >= 4  # skill-creator, summarize, weather, github
        assert reg.has("skill-creator")
        assert reg.has("summarize")
        assert reg.has("weather")
        assert reg.has("github")

    def test_scan_workspace(self, tmp_path):
        skills_dir = tmp_path / ".skills"
        skills_dir.mkdir()
        (skills_dir / "custom.md").write_text("""---
name: custom-skill
domain: coding
trigger: [custom]
---

Custom skill content.
""")
        reg = SkillRegistry()
        count = scan_workspace_skills(reg, tmp_path)
        assert count == 1
        assert reg.has("custom-skill")

    def test_scan_empty_workspace(self, tmp_path):
        reg = SkillRegistry()
        count = scan_workspace_skills(reg, tmp_path)
        assert count == 0


class TestSkillMatcher:
    def test_match_and_inject(self, tmp_path):
        reg = SkillRegistry()
        skill_file = tmp_path / "inject.md"
        skill_file.write_text("""---
name: inject-skill
domain: coding
trigger: [debug]
---

Debug instructions here.
""")
        meta, _ = parse_skill_file(skill_file)
        reg.register("inject-skill", meta, str(skill_file))

        matcher = SkillMatcher(reg)
        results = matcher.get_skills_for_prompt("coding", "debug this error")
        assert len(results) == 1
        assert results[0]["name"] == "inject-skill"
        assert "Debug instructions" in results[0]["content"]

    def test_cleanup(self, tmp_path):
        reg = SkillRegistry()
        skill_file = tmp_path / "cleanup.md"
        skill_file.write_text("""---
name: cleanup-skill
domain: general
trigger: [test]
---

Content.
""")
        meta, _ = parse_skill_file(skill_file)
        reg.register("cleanup-skill", meta, str(skill_file))

        matcher = SkillMatcher(reg)
        matched = matcher.match("general", "test something")
        assert len(matched) == 1
        assert matched[0]._content_loaded

        matcher.cleanup("general", "test something")
        # Content cleared
        assert not matched[0]._content_loaded
