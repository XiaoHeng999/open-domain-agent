"""Tests for web tools — web_search, web_fetch."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from open_agent.tools.web import WebSearchTool, WebFetchTool


class TestWebSearchTool:
    @pytest.mark.asyncio
    async def test_no_api_key(self):
        tool = WebSearchTool()
        result = await tool.execute(query="test")
        assert "not configured" in result

    @pytest.mark.asyncio
    async def test_successful_search(self):
        tool = WebSearchTool(api_key="test-key")

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
        tool = WebSearchTool(api_key="test-key")

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
        tool = WebSearchTool(api_key="test-key")

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
        tool = WebSearchTool(api_key="key")
        assert tool.name == "web_search"
        assert tool.read_only is True
        assert "url" in tool.safety_checks


class TestWebFetchTool:
    @pytest.mark.asyncio
    async def test_non_http_protocol(self):
        tool = WebFetchTool()
        result = await tool.execute(url="file:///etc/passwd")
        assert "HTTP/HTTPS" in result

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        tool = WebFetchTool()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Hello World</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = instance

            result = await tool.execute(url="https://example.com")
            assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_content_truncation(self):
        tool = WebFetchTool(max_chars=50)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "x" * 1000
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
