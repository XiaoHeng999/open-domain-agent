"""Tests for Tool ABC, cast_params, validate_params, to_schema, FunctionTool."""
import pytest

from open_agent.tools.base import FunctionTool, Tool, _cast_value, _validate_value


# -- Minimal concrete Tool for testing --

class _DummyTool(Tool):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy tool for testing"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "limit": {"type": "integer", "description": "Max items"},
                "force": {"type": "boolean"},
                "config": {
                    "type": "object",
                    "properties": {
                        "retries": {"type": "integer"},
                    },
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs):
        return "ok"


# -- cast_params tests --

class TestCastParams:
    def test_str_to_int(self):
        tool = _DummyTool()
        result = tool.cast_params({"limit": "10"})
        assert result["limit"] == 10
        assert isinstance(result["limit"], int)

    def test_str_to_bool_true(self):
        tool = _DummyTool()
        for val in ("true", "True", "TRUE", "1", "yes", "on"):
            result = tool.cast_params({"force": val})
            assert result["force"] is True

    def test_str_to_bool_false(self):
        tool = _DummyTool()
        for val in ("false", "False", "0", "no", "off"):
            result = tool.cast_params({"force": val})
            assert result["force"] is False

    def test_null_to_empty_string(self):
        tool = _DummyTool()
        result = tool.cast_params({"path": None})
        assert result["path"] == ""

    def test_nested_object_cast(self):
        tool = _DummyTool()
        result = tool.cast_params({"config": {"retries": "3"}})
        assert result["config"]["retries"] == 3

    def test_no_coercion_needed(self):
        tool = _DummyTool()
        result = tool.cast_params({"path": "file.txt", "limit": 5})
        assert result["path"] == "file.txt"
        assert result["limit"] == 5

    def test_invalid_int_stays_str(self):
        result = _cast_value("abc", {"type": "integer"})
        assert result == "abc"


# -- validate_params tests --

class TestValidateParams:
    def test_missing_required(self):
        tool = _DummyTool()
        errors = tool.validate_params({})
        assert any("path" in e for e in errors)

    def test_type_mismatch(self):
        tool = _DummyTool()
        errors = tool.validate_params({"path": 123})
        assert any("string" in e for e in errors)

    def test_valid_params(self):
        tool = _DummyTool()
        errors = tool.validate_params({"path": "file.txt"})
        assert errors == []

    def test_enum_validation(self):
        schema = {"type": "string", "enum": ["a", "b", "c"]}
        errors = _validate_value("d", schema, "field")
        assert any("enum" in e.lower() or "must be one of" in e for e in errors)

    def test_minimum(self):
        schema = {"type": "integer", "minimum": 0}
        errors = _validate_value(-1, schema, "num")
        assert any("minimum" in e or ">=" in e for e in errors)

    def test_maximum(self):
        schema = {"type": "integer", "maximum": 100}
        errors = _validate_value(200, schema, "num")
        assert any("maximum" in e or "<=" in e for e in errors)

    def test_min_length(self):
        schema = {"type": "string", "minLength": 3}
        errors = _validate_value("ab", schema, "s")
        assert len(errors) > 0

    def test_max_length(self):
        schema = {"type": "string", "maxLength": 5}
        errors = _validate_value("abcdef", schema, "s")
        assert len(errors) > 0

    def test_min_items(self):
        schema = {"type": "array", "minItems": 1, "items": {"type": "string"}}
        errors = _validate_value([], schema, "arr")
        assert len(errors) > 0

    def test_max_items(self):
        schema = {"type": "array", "maxItems": 2, "items": {"type": "string"}}
        errors = _validate_value(["a", "b", "c"], schema, "arr")
        assert len(errors) > 0

    def test_bool_not_integer(self):
        errors = _validate_value(True, {"type": "integer"}, "n")
        assert len(errors) > 0


# -- to_schema tests --

class TestToSchema:
    def test_output_format(self):
        tool = _DummyTool()
        schema = tool.to_schema()
        assert schema["name"] == "dummy"
        assert schema["description"] == "A dummy tool for testing"
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"
        assert "properties" in schema["input_schema"]

    def test_read_only_default_false(self):
        tool = _DummyTool()
        assert tool.read_only is False


# -- FunctionTool tests --

class TestFunctionTool:
    @pytest.mark.asyncio
    async def test_sync_handler(self):
        tool = FunctionTool(
            name="test",
            description="test tool",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "hello",
        )
        result = await tool.execute()
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_async_handler(self):
        async def async_fn():
            return "async hello"

        tool = FunctionTool(
            name="test",
            description="test tool",
            parameters={"type": "object", "properties": {}},
            handler=async_fn,
        )
        result = await tool.execute()
        assert result == "async hello"

    def test_properties(self):
        tool = FunctionTool(
            name="my_tool",
            description="desc",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "",
            read_only=True,
            safety_checks=["url"],
        )
        assert tool.name == "my_tool"
        assert tool.description == "desc"
        assert tool.read_only is True
        assert tool.safety_checks == ["url"]

    def test_to_schema(self):
        tool = FunctionTool(
            name="ft",
            description="ft desc",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=lambda x: x,
        )
        schema = tool.to_schema()
        assert schema["name"] == "ft"
        assert "input_schema" in schema
