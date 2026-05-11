"""Decorators — @tool_schema auto-generates MCP-compatible JSON Schema.

Deprecated: Use Tool ABC subclass instead of @tool_schema for new tools.
"""
from __future__ import annotations

import inspect
import re
import warnings
from typing import Any, Callable, get_type_hints

# Map Python types to JSON Schema types
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def tool_schema(func: Callable | None = None, *, name: str | None = None, description: str | None = None):
    """Decorator that generates MCP-compatible JSON Schema from function signature + docstring.

    Usage:
        @tool_schema
        def search(query: str, limit: int = 10) -> str:
            '''Search the web.
            Args:
                query: Search query string
                limit: Max results to return
            '''
            ...

    Or with overrides:
        @tool_schema(name="web_search", description="Search the web")
        def search(query: str) -> str: ...
    """

    def decorator(fn: Callable) -> Callable:
        warnings.warn(
            "@tool_schema is deprecated — use Tool ABC subclass instead",
            DeprecationWarning,
            stacklevel=2,
        )
        schema = _build_schema(fn, tool_name=name, tool_desc=description)
        fn._tool_schema = schema
        fn._is_tool = True
        return fn

    if func is not None:
        return decorator(func)
    return decorator


def _build_schema(func: Callable, tool_name: str | None = None, tool_desc: str | None = None) -> dict[str, Any]:
    """Build JSON Schema from function signature and docstring."""
    sig = inspect.signature(func)
    hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}
    doc_params = _parse_docstring_params(func.__doc__)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        prop: dict[str, Any] = {}
        json_type = _TYPE_MAP.get(hints.get(param_name, str), "string")
        prop["type"] = json_type

        if param_name in doc_params:
            prop["description"] = doc_params[param_name]

        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop["default"] = param.default

        properties[param_name] = prop

    schema: dict[str, Any] = {
        "name": tool_name or func.__name__,
        "description": tool_desc or _parse_docstring_summary(func.__doc__),
        "inputSchema": {
            "type": "object",
            "properties": properties,
        },
    }
    if required:
        schema["inputSchema"]["required"] = required

    return schema


def _parse_docstring_summary(doc: str | None) -> str:
    """Extract first line of docstring as summary."""
    if not doc:
        return ""
    lines = doc.strip().splitlines()
    return lines[0].strip()


def _parse_docstring_params(doc: str | None) -> dict[str, str]:
    """Parse Args: section from docstring into {param: description}."""
    if not doc:
        return {}
    params: dict[str, str] = {}
    in_args = False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("Args:"):
            in_args = True
            continue
        if in_args:
            if not stripped or (not stripped.startswith(" ") and ":" not in stripped):
                break
            match = re.match(r"\s*(\w+):\s*(.*)", stripped)
            if match:
                params[match.group(1)] = match.group(2)
    return params
