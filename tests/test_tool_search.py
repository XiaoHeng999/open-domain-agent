"""Tests for SearchTool — grep and glob code search."""
import pytest
import shutil

from open_agent.tools.search import SearchTool


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def hello():\n    pass\n# TODO: fix\n")
    (tmp_path / "src" / "utils.js").write_text("function hello() {}\n// TODO: implement\n")
    (tmp_path / "README.md").write_text("# Project\nHello world\n")
    return tmp_path


class TestSearchTool:
    def test_name_and_description(self):
        tool = SearchTool()
        assert tool.name == "search"
        assert tool.description

    def test_schema(self):
        tool = SearchTool()
        schema = tool.to_schema()
        assert schema["name"] == "search"
        assert "input_schema" in schema

    def test_safety_checks(self):
        tool = SearchTool()
        assert "path" in tool.safety_checks
        assert tool.read_only is True

    @pytest.mark.asyncio
    async def test_grep_basic(self, workspace):
        if not shutil.which("rg"):
            pytest.skip("ripgrep not installed")
        tool = SearchTool(workspace=str(workspace))
        result = await tool.execute(action="grep", pattern="TODO", path="src/")
        assert "TODO" in result
        assert "app.py" in result

    @pytest.mark.asyncio
    async def test_grep_file_type_filter(self, workspace):
        if not shutil.which("rg"):
            pytest.skip("ripgrep not installed")
        tool = SearchTool(workspace=str(workspace))
        result = await tool.execute(action="grep", pattern="TODO", path="src/", file_type="py")
        assert "app.py" in result
        assert "utils.js" not in result

    @pytest.mark.asyncio
    async def test_grep_no_matches(self, workspace):
        if not shutil.which("rg"):
            pytest.skip("ripgrep not installed")
        tool = SearchTool(workspace=str(workspace))
        result = await tool.execute(action="grep", pattern="NONEXISTENT_PATTERN_XYZ", path="src/")
        assert "No matches" in result

    @pytest.mark.asyncio
    async def test_grep_missing_pattern(self):
        tool = SearchTool()
        result = await tool.execute(action="grep", path=".")
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_glob_basic(self, workspace):
        tool = SearchTool(workspace=str(workspace))
        result = await tool.execute(action="glob", pattern="**/*.py", path="src")
        assert "app.py" in result
        assert "utils.js" not in result

    @pytest.mark.asyncio
    async def test_glob_all_files(self, workspace):
        tool = SearchTool(workspace=str(workspace))
        result = await tool.execute(action="glob", pattern="**/*", path=".")
        assert "app.py" in result

    @pytest.mark.asyncio
    async def test_glob_no_matches(self, workspace):
        tool = SearchTool(workspace=str(workspace))
        result = await tool.execute(action="glob", pattern="**/*.xyz", path=".")
        assert "No files" in result

    @pytest.mark.asyncio
    async def test_glob_nonexistent_path(self, workspace):
        tool = SearchTool(workspace=str(workspace))
        result = await tool.execute(action="glob", pattern="*", path="nonexistent")
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_glob_missing_pattern(self):
        tool = SearchTool()
        result = await tool.execute(action="glob", path=".")
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = SearchTool()
        result = await tool.execute(action="unknown", pattern="test")
        assert "Unknown action" in result

    @pytest.mark.asyncio
    async def test_grep_rg_not_available(self, monkeypatch):
        tool = SearchTool()
        monkeypatch.setattr(shutil, "which", lambda cmd: None if cmd == "rg" else shutil.which.__wrapped__(cmd) if hasattr(shutil.which, '__wrapped__') else None)
        result = await tool.execute(action="grep", pattern="test", path=".")
        assert "ripgrep" in result.lower() or "rg" in result.lower()
