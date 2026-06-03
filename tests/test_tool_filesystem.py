"""Tests for filesystem tools — read_file, write_file, edit_file, list_dir."""
import os
import tempfile

import pytest

from open_agent.tools.filesystem import (
    EditFileTool, ListDirTool, ReadFileTool, WriteFileTool, _resolve_path,
)


@pytest.fixture
def workspace(tmp_path):
    return str(tmp_path)


# -- ReadFileTool tests --

class TestReadFileTool:
    @pytest.mark.asyncio
    async def test_read_full_file(self, workspace):
        f = os.path.join(workspace, "test.txt")
        with open(f, "w") as fh:
            fh.write("line1\nline2\nline3\n")

        tool = ReadFileTool(workspace=workspace)
        result = await tool.execute(path="test.txt")
        assert "line1" in result
        assert "line3" in result

    @pytest.mark.asyncio
    async def test_read_with_offset_limit(self, workspace):
        f = os.path.join(workspace, "test.txt")
        with open(f, "w") as fh:
            for i in range(10):
                fh.write(f"line{i}\n")

        tool = ReadFileTool(workspace=workspace)
        result = await tool.execute(path="test.txt", offset=2, limit=3)
        assert "line2" in result
        assert "line4" in result
        assert "line5" not in result

    @pytest.mark.asyncio
    async def test_read_nonexistent(self, workspace):
        tool = ReadFileTool(workspace=workspace)
        result = await tool.execute(path="nope.txt")
        assert "not found" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_read_only_property(self, workspace):
        tool = ReadFileTool(workspace=workspace)
        assert tool.read_only is True

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, workspace):
        tool = ReadFileTool(workspace=workspace)
        result = await tool.execute(path="../../../etc/passwd")
        assert "workspace" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_safety_checks(self, workspace):
        tool = ReadFileTool(workspace=workspace)
        assert "path" in tool.safety_checks


# -- WriteFileTool tests --

class TestWriteFileTool:
    @pytest.mark.asyncio
    async def test_create_file(self, workspace):
        tool = WriteFileTool(workspace=workspace)
        result = await tool.execute(path="new_file.txt", content="hello world")
        assert "Successfully" in result

        with open(os.path.join(workspace, "new_file.txt")) as f:
            assert f.read() == "hello world"

    @pytest.mark.asyncio
    async def test_create_in_subdirectory(self, workspace):
        tool = WriteFileTool(workspace=workspace)
        result = await tool.execute(path="sub/dir/file.txt", content="nested")
        assert "Successfully" in result

        with open(os.path.join(workspace, "sub", "dir", "file.txt")) as f:
            assert f.read() == "nested"

    @pytest.mark.asyncio
    async def test_overwrite_file(self, workspace):
        f = os.path.join(workspace, "existing.txt")
        with open(f, "w") as fh:
            fh.write("old")

        tool = WriteFileTool(workspace=workspace)
        await tool.execute(path="existing.txt", content="new")
        with open(f) as fh:
            assert fh.read() == "new"

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, workspace):
        tool = WriteFileTool(workspace=workspace)
        result = await tool.execute(path="/tmp/evil.txt", content="hacked")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_read_only_false(self, workspace):
        tool = WriteFileTool(workspace=workspace)
        assert tool.read_only is False


# -- EditFileTool tests --

class TestEditFileTool:
    @pytest.mark.asyncio
    async def test_successful_edit(self, workspace):
        f = os.path.join(workspace, "edit.txt")
        with open(f, "w") as fh:
            fh.write("print('hello')\nprint('world')\n")

        tool = EditFileTool(workspace=workspace)
        result = await tool.execute(
            path="edit.txt",
            old_string="print('hello')",
            new_string="print('world')",
        )
        assert "Successfully" in result

        with open(f) as fh:
            content = fh.read()
        assert "print('world')\nprint('world')" in content

    @pytest.mark.asyncio
    async def test_not_unique(self, workspace):
        f = os.path.join(workspace, "dup.txt")
        with open(f, "w") as fh:
            fh.write("abc\nabc\nabc\n")

        tool = EditFileTool(workspace=workspace)
        result = await tool.execute(
            path="dup.txt",
            old_string="abc",
            new_string="xyz",
        )
        assert "3 times" in result

    @pytest.mark.asyncio
    async def test_not_found(self, workspace):
        f = os.path.join(workspace, "edit.txt")
        with open(f, "w") as fh:
            fh.write("hello\n")

        tool = EditFileTool(workspace=workspace)
        result = await tool.execute(
            path="edit.txt",
            old_string="nonexistent",
            new_string="replacement",
        )
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_file_not_found(self, workspace):
        tool = EditFileTool(workspace=workspace)
        result = await tool.execute(
            path="missing.txt",
            old_string="a",
            new_string="b",
        )
        assert "Error" in result


# -- ListDirTool tests --

class TestListDirTool:
    @pytest.mark.asyncio
    async def test_list_directory(self, workspace):
        os.makedirs(os.path.join(workspace, "subdir"))
        with open(os.path.join(workspace, "file1.txt"), "w") as f:
            f.write("x")

        tool = ListDirTool(workspace=workspace)
        result = await tool.execute(path=".")
        assert "[DIR]" in result
        assert "subdir" in result
        assert "[FILE]" in result
        assert "file1.txt" in result

    @pytest.mark.asyncio
    async def test_empty_directory(self, workspace):
        empty = os.path.join(workspace, "empty")
        os.makedirs(empty)

        tool = ListDirTool(workspace=workspace)
        result = await tool.execute(path="empty")
        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_nonexistent_directory(self, workspace):
        tool = ListDirTool(workspace=workspace)
        result = await tool.execute(path="nonexistent")
        assert "not found" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_read_only(self, workspace):
        tool = ListDirTool(workspace=workspace)
        assert tool.read_only is True


# -- Symlink traversal tests --

class TestSymlinkTraversal:
    """Ensure symlinks pointing outside the workspace are blocked."""

    def test_symlink_outside_workspace_rejected(self, workspace):
        outside = tempfile.mkdtemp()
        target = os.path.join(outside, "secret.txt")
        with open(target, "w") as f:
            f.write("secret data")

        link = os.path.join(workspace, "evil_link")
        os.symlink(target, link)

        with pytest.raises(ValueError, match="escapes workspace"):
            _resolve_path("evil_link", workspace)

        os.remove(link)
        os.remove(target)
        os.rmdir(outside)

    def test_symlink_inside_workspace_allowed(self, workspace):
        real = os.path.join(workspace, "real.txt")
        with open(real, "w") as f:
            f.write("ok")

        link = os.path.join(workspace, "link.txt")
        os.symlink("real.txt", link)

        resolved = _resolve_path("link.txt", workspace)
        assert str(resolved) == os.path.realpath(link)

    @pytest.mark.asyncio
    async def test_read_via_symlink_blocked(self, workspace):
        outside = tempfile.mkdtemp()
        target = os.path.join(outside, "secret.txt")
        with open(target, "w") as f:
            f.write("secret")

        link = os.path.join(workspace, "escape")
        os.symlink(target, link)

        tool = ReadFileTool(workspace=workspace)
        result = await tool.execute(path="escape")
        assert "Error" in result

        os.remove(link)
        os.remove(target)
        os.rmdir(outside)

    @pytest.mark.asyncio
    async def test_write_via_symlink_blocked(self, workspace):
        outside = tempfile.mkdtemp()
        target = os.path.join(outside, "secret.txt")

        link = os.path.join(workspace, "escape")
        os.symlink(target, link)

        tool = WriteFileTool(workspace=workspace)
        result = await tool.execute(path="escape", content="hacked")
        assert "Error" in result

        os.remove(link)
        os.rmdir(outside)
