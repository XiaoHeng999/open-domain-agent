## MODIFIED Requirements

### Requirement: WebSearchTool (Network Search)
Provides a `web_search` tool with configurable backends — DuckDuckGo (default, free, no API key) or Brave Search (requires API key). Supports a `count` parameter to limit results. Returns formatted results (title + URL + snippet). If the configured backend is unavailable, the tool is not registered. The DuckDuckGo backend's `ddgs.text()` synchronous call MUST be wrapped in `asyncio.to_thread()` to avoid blocking the event loop. The tool's `safety_checks` MUST be an empty list `[]` because search URLs are constructed internally.

#### Scenario: DuckDuckGo search does not block event loop
- **WHEN** web_search is called with DuckDuckGo backend
- **THEN** ddgs.text() runs in a separate thread via asyncio.to_thread(), other async tasks continue executing

#### Scenario: Search results returned correctly
- **WHEN** web_search is called with query "test" and count 5
- **THEN** up to 5 results are returned with title, URL, and snippet
