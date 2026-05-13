## MODIFIED Requirements

### Requirement: WebSearchTool 网络搜索工具
系统 SHALL 提供 `web_search` 工具，通过可配置的搜索后端执行网络搜索并返回结果列表。默认使用 DuckDuckGo（免费、无需 API Key），可选 Brave Search（需 API Key）。搜索工具的 `safety_checks` SHALL 为空列表 `[]`，因为搜索 URL 由后端库内部构建，不需要 SSRF 检查。

#### Scenario: 成功搜索
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "Python async patterns"}`
- **THEN** 工具通过当前配置的后端执行搜索并返回格式化的搜索结果列表（标题 + URL + 摘要），且 SafetyMiddleware 不对搜索工具进行 URL 安全检查

#### Scenario: 无结果
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "xyznonexistent12345"}`
- **THEN** 工具返回 `"No results found for query: xyznonexistent12345"`

#### Scenario: 搜索服务不可用
- **WHEN** 搜索后端返回错误
- **THEN** 工具返回包含错误信息的字符串，以 `"Error:"` 开头

#### Scenario: 结果数量限制
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "test", "count": 5}`
- **THEN** 工具最多返回 5 条结果

#### Scenario: 无可用后端
- **WHEN** 配置的搜索后端不可用（如强制 Brave 但无 Key）
- **THEN** `web_search` 工具不注册到 ToolRegistry，LLM 无法选择该工具

#### Scenario: 搜索工具跳过 URL 安全检查
- **WHEN** DuckDuckGoSearchTool 或 BraveSearchTool 声明 `safety_checks=[]`
- **THEN** SafetyMiddleware SHALL 跳过对搜索工具的所有安全检查，不出现 "No hostname in URL" 错误

## MODIFIED Requirements (security-hardening-and-critical-fixes)

### Requirement: WebSearchTool (Network Search)
Provides a `web_search` tool with configurable backends — DuckDuckGo (default, free, no API key) or Brave Search (requires API key). Supports a `count` parameter to limit results. Returns formatted results (title + URL + snippet). If the configured backend is unavailable, the tool is not registered. The DuckDuckGo backend's `ddgs.text()` synchronous call MUST be wrapped in `asyncio.to_thread()` to avoid blocking the event loop. The tool's `safety_checks` MUST be an empty list `[]` because search URLs are constructed internally.

#### Scenario: DuckDuckGo search does not block event loop
- **WHEN** web_search is called with DuckDuckGo backend
- **THEN** ddgs.text() runs in a separate thread via asyncio.to_thread(), other async tasks continue executing

#### Scenario: Search results returned correctly
- **WHEN** web_search is called with query "test" and count 5
- **THEN** up to 5 results are returned with title, URL, and snippet
