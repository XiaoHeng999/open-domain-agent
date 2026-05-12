"""Tests for web tools — web_search (DuckDuckGo / Brave), web_fetch."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from open_agent.tools.web import (
    BraveSearchTool, DuckDuckGoSearchTool, WebFetchTool, WebSearchTool,
)


class TestDuckDuckGoSearchTool:
    def test_properties(self):
        tool = DuckDuckGoSearchTool()
        assert tool.name == "web_search"
        assert tool.read_only is True
        assert "url" in tool.safety_checks
        assert "query" in tool.parameters["properties"]

    @pytest.mark.asyncio
    async def test_successful_search(self):
        tool = DuckDuckGoSearchTool()

        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": "Python Async", "href": "https://example.com/async", "body": "Async patterns"},
            {"title": "Python Guide", "href": "https://example.com/guide", "body": "Python guide"},
        ]

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
            result = await tool.execute(query="python async")
        assert "Python Async" in result
        assert "https://example.com/async" in result
        assert "Async patterns" in result

    @pytest.mark.asyncio
    async def test_no_results(self):
        tool = DuckDuckGoSearchTool()

        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = []

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
            result = await tool.execute(query="xyznonexistent12345")
        assert "No results" in result

    @pytest.mark.asyncio
    async def test_count_limit(self):
        tool = DuckDuckGoSearchTool()

        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": f"Result {i}", "href": f"https://example.com/{i}", "body": f"Body {i}"}
            for i in range(10)
        ]

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
            result = await tool.execute(query="test", count=3)
        # Should have exactly 3 numbered results
        assert result.count("URL:") == 3
        mock_ddgs.text.assert_called_once_with("test", max_results=3)

    @pytest.mark.asyncio
    async def test_network_error(self):
        tool = DuckDuckGoSearchTool()

        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.side_effect = ConnectionError("network down")

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
            result = await tool.execute(query="test")
        assert result.startswith("Error: Search failed:")

    @pytest.mark.asyncio
    async def test_empty_query(self):
        tool = DuckDuckGoSearchTool()
        result = await tool.execute(query="")
        assert "Error" in result


class TestBraveSearchTool:
    @pytest.mark.asyncio
    async def test_no_api_key(self):
        tool = BraveSearchTool()
        result = await tool.execute(query="test")
        assert "not configured" in result

    @pytest.mark.asyncio
    async def test_successful_search(self):
        tool = BraveSearchTool(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Python Async", "url": "https://example.com/async", "description": "Async patterns"},
                    {"title": "Python Guide", "url": "https://example.com/guide", "description": "Python guide"},
                ]
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = instance

            result = await tool.execute(query="python async")
            assert "Python Async" in result
            assert "https://example.com/async" in result

    @pytest.mark.asyncio
    async def test_no_results(self):
        tool = BraveSearchTool(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"web": {"results": []}}

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = instance

            result = await tool.execute(query="xyznonexistent12345")
            assert "No results" in result

    @pytest.mark.asyncio
    async def test_service_unavailable(self):
        tool = BraveSearchTool(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = instance

            result = await tool.execute(query="test")
            assert "503" in result

    def test_properties(self):
        tool = BraveSearchTool(api_key="key")
        assert tool.name == "web_search"
        assert tool.read_only is True
        assert "url" in tool.safety_checks

    def test_backward_compat_alias(self):
        assert WebSearchTool is BraveSearchTool


class TestWebFetchTool:
    @pytest.mark.asyncio
    async def test_non_http_protocol(self):
        tool = WebFetchTool()
        result = await tool.execute(url="file:///etc/passwd")
        assert "HTTP/HTTPS" in result

    @pytest.mark.asyncio
    async def test_html_to_markdown(self):
        tool = WebFetchTool()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><h1>Title</h1><p>Hello World</p></body></html>"
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = instance

            result = await tool.execute(url="https://example.com")
        assert "Title" in result
        assert "Hello World" in result
        # Should not contain raw HTML tags
        assert "<html>" not in result

    @pytest.mark.asyncio
    async def test_json_content_no_conversion(self):
        tool = WebFetchTool()

        json_body = '{"key": "value"}'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json_body
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = instance

            result = await tool.execute(url="https://api.example.com/data")
        assert result == json_body

    @pytest.mark.asyncio
    async def test_content_truncation_after_markdown(self):
        tool = WebFetchTool(max_chars=50)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>" + "x" * 1000 + "</body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = instance

            result = await tool.execute(url="https://example.com")
        assert "[truncated" in result

    @pytest.mark.asyncio
    async def test_connection_error(self):
        import httpx
        tool = WebFetchTool()

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = instance

            result = await tool.execute(url="https://nonexistent.invalid")
            assert "Error" in result

    def test_properties(self):
        tool = WebFetchTool()
        assert tool.name == "web_fetch"
        assert tool.read_only is True
        assert "url" in tool.safety_checks
