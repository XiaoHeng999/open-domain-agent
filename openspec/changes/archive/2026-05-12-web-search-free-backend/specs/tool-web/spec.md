## MODIFIED Requirements

### Requirement: WebSearchTool 网络搜索工具
系统 SHALL 提供 `web_search` 工具，通过可配置的搜索后端执行网络搜索并返回结果列表。默认使用 DuckDuckGo（免费、无需 API Key），可选 Brave Search（需 API Key）。

#### Scenario: 成功搜索
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "Python async patterns"}`
- **THEN** 工具通过当前配置的后端执行搜索并返回格式化的搜索结果列表（标题 + URL + 摘要）

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

### Requirement: WebFetchTool 网页抓取工具
系统 SHALL 提供 `web_fetch` 工具，抓取指定 URL 的内容并将 HTML 转换为 Markdown 格式返回，提升 LLM 可读性。

#### Scenario: 成功抓取 HTML 页面
- **WHEN** LLM 调用 `web_fetch` 参数 `{"url": "https://example.com/docs"}`
- **THEN** 工具抓取页面，将 HTML 转换为 Markdown 格式并返回

#### Scenario: 内容截断
- **WHEN** 转换后的 Markdown 内容超过 `max_chars`（默认 50000）
- **THEN** 工具截断内容并追加 `"\n...[truncated, {total} chars total]"`

#### Scenario: URL 不可达
- **WHEN** LLM 调用 `web_fetch` 参数 `{"url": "https://nonexistent.invalid/page"}`
- **THEN** 工具返回 `"Error: Failed to fetch URL: ..."`

#### Scenario: 非 HTTP/HTTPS 协议
- **WHEN** LLM 调用 `web_fetch` 参数 `{"url": "file:///etc/passwd"}`
- **THEN** 工具拒绝请求，返回 `"Error: Only HTTP/HTTPS URLs are supported"`

#### Scenario: 非 HTML 内容直接返回
- **WHEN** 响应 Content-Type 不是 HTML（如 JSON、纯文本）
- **THEN** 工具直接返回原始文本内容，不做 Markdown 转换
