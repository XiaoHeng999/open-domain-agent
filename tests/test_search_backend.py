"""Tests for multi-backend search tool registration."""
import pytest
from unittest.mock import MagicMock

from open_agent.config import ToolsConfig
from open_agent.registry import ToolRegistry, scan_builtin_tools
from open_agent.tools.web import BraveSearchTool, DuckDuckGoSearchTool


def _make_config(**tools_overrides):
    tools = ToolsConfig(**tools_overrides)
    config = MagicMock()
    config.tools = tools
    config.workspace = "."
    return config


class TestSearchBackendRegistration:
    def test_auto_mode_with_brave_key(self):
        config = _make_config(search_backend="auto", brave_search_api_key="test-key")
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)

        assert registry.has("web_search")
        tool = registry.get("web_search")
        assert isinstance(tool, BraveSearchTool)

    def test_auto_mode_without_brave_key(self):
        config = _make_config(search_backend="auto", brave_search_api_key=None)
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)

        assert registry.has("web_search")
        tool = registry.get("web_search")
        assert isinstance(tool, DuckDuckGoSearchTool)

    def test_forced_duckduckgo(self):
        config = _make_config(search_backend="duckduckgo", brave_search_api_key="test-key")
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)

        assert registry.has("web_search")
        tool = registry.get("web_search")
        assert isinstance(tool, DuckDuckGoSearchTool)

    def test_forced_duckduckgo_no_key(self):
        config = _make_config(search_backend="duckduckgo", brave_search_api_key=None)
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)

        assert registry.has("web_search")
        tool = registry.get("web_search")
        assert isinstance(tool, DuckDuckGoSearchTool)

    def test_forced_brave_with_key(self):
        config = _make_config(search_backend="brave", brave_search_api_key="test-key")
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)

        assert registry.has("web_search")
        tool = registry.get("web_search")
        assert isinstance(tool, BraveSearchTool)

    def test_forced_brave_without_key(self):
        config = _make_config(search_backend="brave", brave_search_api_key=None)
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)

        assert not registry.has("web_search")

    def test_web_fetch_always_registered(self):
        config = _make_config(search_backend="brave", brave_search_api_key=None)
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)

        assert registry.has("web_fetch")

    def test_default_config_uses_duckduckgo(self):
        config = _make_config()
        registry = ToolRegistry()
        scan_builtin_tools(registry, config)

        assert registry.has("web_search")
        assert isinstance(registry.get("web_search"), DuckDuckGoSearchTool)
