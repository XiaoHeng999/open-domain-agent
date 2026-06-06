"""Tests for CLI `agent skill list` command."""

from __future__ import annotations

from typer.testing import CliRunner

from open_agent.cli import app

runner = CliRunner()


class TestSkillListCommand:
    def test_skill_list_shows_available_skills(self):
        """`agent skill list` should display built-in skills in a table."""
        result = runner.invoke(app, ["skill", "list"])
        assert result.exit_code == 0
        # Should have a table header
        assert "Available Skills" in result.output
        # Should show at least one known built-in skill name
        assert "summarize" in result.output or "skill-creator" in result.output or "github" in result.output or "weather" in result.output

    def test_skill_list_includes_source_column(self):
        """The skill table should include a Source column."""
        result = runner.invoke(app, ["skill", "list"])
        assert result.exit_code == 0
        assert "Source" in result.output

    def test_skill_list_shows_skill_details(self):
        """Each skill row should show name, domain, description."""
        result = runner.invoke(app, ["skill", "list"])
        assert result.exit_code == 0
        # The table should contain known domain values
        assert "general" in result.output or "coding" in result.output

    def test_skill_list_unknown_action(self):
        """Unknown action should show error message."""
        result = runner.invoke(app, ["skill", "unknown"])
        assert result.exit_code == 0
        assert "Unknown action" in result.output
