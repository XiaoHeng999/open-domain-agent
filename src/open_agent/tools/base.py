"""Tool ABC base class — abstract interface for all built-in tools.

Provides:
- Tool ABC: name/description/parameters abstract properties, async execute()
- cast_params(): type coercion for common LLM output quirks
- validate_params(): JSON Schema recursive validation
- to_schema(): Anthropic tool_use format output
- FunctionTool: adapter for wrapping function handlers as Tool instances
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

_BOOL_TRUE = {"true", "1", "yes", "on"}
_BOOL_FALSE = {"false", "0", "no", "off"}


class Tool(ABC):
    """Abstract base class for all built-in tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool identifier used in tool_use calls."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema describing the tool's input parameters."""

    @property
    def read_only(self) -> bool:
        """Whether this tool has no side effects (default False)."""
        return False

    @property
    def safety_checks(self) -> list[str]:
        """Safety check types this tool requires (e.g. ["command"], ["url"], ["path"])."""
        return []

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool with the given parameters. Returns result string."""

    def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Coerce parameter types based on the JSON Schema.

        Handles common LLM output quirks: str->int, str->bool, null->"".
        """
        schema = self.parameters
        properties = schema.get("properties", {})
        return _cast_object(params, properties)

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters against the JSON Schema. Returns error list."""
        schema = self.parameters
        return _validate_object(params, schema, "")

    def to_schema(self) -> dict[str, Any]:
        """Output Anthropic tool_use format definition."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


class FunctionTool(Tool):
    """Adapter wrapping a function handler as a Tool ABC instance.

    Used for MCP remote tools and backward compatibility with @tool_schema.
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any],
        *,
        read_only: bool = False,
        safety_checks: list[str] | None = None,
    ) -> None:
        self._name = name
        self._description = description
        self._parameters = parameters
        self._handler = handler
        self._read_only = read_only
        self._safety_checks = safety_checks or []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    @property
    def read_only(self) -> bool:
        return self._read_only

    @property
    def safety_checks(self) -> list[str]:
        return self._safety_checks

    async def execute(self, **kwargs: Any) -> str:
        result = self._handler(**kwargs)
        if hasattr(result, "__await__"):
            result = await result
        return str(result)


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------

def _cast_value(value: Any, prop_schema: dict[str, Any]) -> Any:
    """Coerce a single value to match the schema type."""
    target_type = prop_schema.get("type")
    if target_type is None:
        return value

    if value is None:
        if target_type == "string":
            return ""
        return value

    if target_type == "integer" and isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            return value

    if target_type == "number" and isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return value

    if target_type == "boolean" and isinstance(value, str):
        if value.lower() in _BOOL_TRUE:
            return True
        if value.lower() in _BOOL_FALSE:
            return False
        return value

    if target_type == "array" and isinstance(value, list):
        items_schema = prop_schema.get("items", {})
        if items_schema:
            return [_cast_value(item, items_schema) for item in value]
        return value

    if target_type == "object" and isinstance(value, dict):
        return _cast_object(value, prop_schema.get("properties", {}))

    return value


def _cast_object(
    params: dict[str, Any], properties: dict[str, Any],
) -> dict[str, Any]:
    """Recursively coerce all parameter values based on property schemas."""
    result = dict(params)
    for key, prop_schema in properties.items():
        if key in result:
            result[key] = _cast_value(result[key], prop_schema)
    return result


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_object(
    obj: dict[str, Any], schema: dict[str, Any], path: str,
) -> list[str]:
    """Recursively validate an object against a JSON Schema."""
    errors: list[str] = []
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Required fields
    for field_name in required:
        if field_name not in obj or obj[field_name] is None:
            errors.append(f"Missing required field: {path}{field_name}")

    for key, value in obj.items():
        prop_path = f"{path}{key}"
        prop_schema = properties.get(key)
        if prop_schema is None:
            continue
        errors.extend(_validate_value(value, prop_schema, prop_path))

    return errors


def _validate_value(
    value: Any, schema: dict[str, Any], path: str,
) -> list[str]:
    """Validate a single value against its schema."""
    errors: list[str] = []
    expected_type = schema.get("type")

    # Type check
    if expected_type and value is not None:
        type_ok = _check_type(value, expected_type)
        if not type_ok:
            errors.append(
                f"Type mismatch at {path}: expected {expected_type}, got {type(value).__name__}"
            )
            return errors

    # Enum
    if "enum" in schema and value not in schema["enum"]:
        errors.append(
            f"Value at {path} must be one of {schema['enum']}, got {value!r}"
        )

    # Number constraints
    if isinstance(value, (int, float)):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"Value at {path} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"Value at {path} must be <= {schema['maximum']}")

    # String constraints
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(
                f"String at {path} must be >= {schema['minLength']} chars"
            )
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(
                f"String at {path} must be <= {schema['maxLength']} chars"
            )

    # Array constraints
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(
                f"Array at {path} must have >= {schema['minItems']} items"
            )
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(
                f"Array at {path} must have <= {schema['maxItems']} items"
            )
        items_schema = schema.get("items")
        if items_schema and isinstance(items_schema, dict):
            for i, item in enumerate(value):
                errors.extend(_validate_value(item, items_schema, f"{path}[{i}]."))

    # Nested object
    if isinstance(value, dict) and expected_type == "object":
        errors.extend(_validate_object(value, schema, f"{path}."))

    return errors


def _check_type(value: Any, expected: str) -> bool:
    """Check if value matches the expected JSON Schema type."""
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    expected_type = type_map.get(expected)
    if expected_type is None:
        return True
    # bool is subclass of int in Python, exclude explicitly
    if expected == "integer" and isinstance(value, bool):
        return False
    return isinstance(value, expected_type)
