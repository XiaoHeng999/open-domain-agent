"""Web tools — web_search (Brave Search API) and web_fetch (URL content)."""
from __future__ import annotations

from typing import Any

from open_agent.tools.base import Tool


class WebSearchTool(Tool):
    """Search the web using Brave Search API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web using Brave Search. Returns a list of results with title, URL, and snippet."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "count": {"type": "integer", "description": "Max results to return (default 5)"},
            },
            "required": ["query"],
        }

    @property
    def read_only(self) -> bool:
        return True

    @property
    def safety_checks(self) -> list[str]:
        return ["url"]

    async def execute(self, **kwargs: Any) -> str:
        if not self._api_key:
            return "Error: Web search not configured. Set BRAVE_SEARCH_API_KEY."

        query = kwargs.get("query", "")
        count = kwargs.get("count", 5)

        try:
            import httpx
        except ImportError:
            return "Error: httpx is required for web search. Install with: pip install httpx"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": count},
                    headers={"X-Subscription-Token": self._api_key},
                    timeout=10,
                )

                if response.status_code == 503:
                    return "Error: Search service unavailable (HTTP 503). Please try again later."
                if response.status_code != 200:
                    return f"Error: Search failed (HTTP {response.status_code})"

                data = response.json()
                results = data.get("web", {}).get("results", [])

                if not results:
                    return f"No results found for query: {query}"

                lines: list[str] = []
                for i, r in enumerate(results[:count], 1):
                    title = r.get("title", "")
                    url = r.get("url", "")
                    snippet = r.get("description", "")
                    lines.append(f"{i}. {title}\n   URL: {url}\n   {snippet}")
                return "\n\n".join(lines)

        except Exception as e:
            return f"Error: Search failed: {e}"


class WebFetchTool(Tool):
    """Fetch and extract text content from a URL."""

    def __init__(self, max_chars: int = 50000) -> None:
        self._max_chars = max_chars

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch the content of a URL and return the text."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch (HTTP/HTTPS only)"},
            },
            "required": ["url"],
        }

    @property
    def read_only(self) -> bool:
        return True

    @property
    def safety_checks(self) -> list[str]:
        return ["url"]

    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url", "")

        # Protocol check
        if not url.startswith(("http://", "https://")):
            return "Error: Only HTTP/HTTPS URLs are supported"

        try:
            import httpx
        except ImportError:
            return "Error: httpx is required for web fetch. Install with: pip install httpx"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15, follow_redirects=True)
                response.raise_for_status()
                content = response.text

                if len(content) > self._max_chars:
                    content = content[:self._max_chars] + f"\n...[truncated, {len(content)} chars total]"

                return content

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} for {url}"
        except httpx.ConnectError:
            return f"Error: Failed to connect to {url}"
        except Exception as e:
            return f"Error: Failed to fetch URL: {e}"
