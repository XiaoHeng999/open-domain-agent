## ADDED Requirements

### Requirement: WebSearchTool 网络搜索工具
系统 SHALL 提供 `web_search` 工具，通过 Brave Search API 执行网络搜索并返回结果列表。

#### Scenario: 成功搜索
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "Python async patterns"}`
- **THEN** 工具调用 Brave Search API 并返回格式化的搜索结果列表（标题 + URL + 摘要）

#### Scenario: 无结果
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "xyznonexistent12345"}`
- **THEN** 工具返回 `"No results found for query: xyznonexistent12345"`

#### Scenario: API 不可用
- **WHEN** Brave Search API 返回 HTTP 503
- **THEN** 工具返回 `"Error: Search service unavailable (HTTP 503). Please try again later."`

#### Scenario: 结果数量限制
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "test", "count": 5}`
- **THEN** 工具最多返回 5 条结果

#### Scenario: 无 API Key
- **WHEN** 工具初始化时未提供 Brave Search API key
- **THEN** 工具返回 `"Error: Web search not configured. Set BRAVE_SEARCH_API_KEY."`

### Requirement: WebFetchTool 网页抓取工具
系统 SHALL 提供 `web_fetch` 工具，抓取指定 URL 的内容并提取可读文本。

#### Scenario: 成功抓取
- **WHEN** LLM 调用 `web_fetch` 参数 `{"url": "https://example.com/docs"}`
- **THEN** 工具抓取页面并返回提取的文本内容

#### Scenario: 内容截断
- **WHEN** 抓取的内容超过 `max_chars`（默认 50000）
- **THEN** 工具截断内容并追加 `"\n...[truncated, {total} chars total]"`

#### Scenario: URL 不可达
- **WHEN** LLM 调用 `web_fetch` 参数 `{"url": "https://nonexistent.invalid/page"}`
- **THEN** 工具返回 `"Error: Failed to fetch URL: ..."`

#### Scenario: 非 HTTP/HTTPS 协议
- **WHEN** LLM 调用 `web_fetch` 参数 `{"url": "file:///etc/passwd"}`
- **THEN** 工具拒绝请求，返回 `"Error: Only HTTP/HTTPS URLs are supported"`

### Requirement: Web 工具 SSRF 防护集成
系统 SHALL 在所有 Web 工具发起网络请求前通过 SafetyManager 进行 URL 安全检查。

#### Scenario: 内网地址被阻止
- **WHEN** LLM 调用 `web_fetch` 参数 `{"url": "http://127.0.0.1/admin"}`
- **THEN** SafetyManager 检测到私有 IP，工具返回 SSRF 错误

#### Scenario: 云元数据端点被阻止
- **WHEN** LLM 调用 `web_fetch` 参数 `{"url": "http://169.254.169.254/latest/meta-data/"}`
- **THEN** SafetyManager 阻止请求，防止云凭证泄露

#### Scenario: 公网 URL 放行
- **WHEN** LLM 调用 `web_fetch` 参数 `{"url": "https://api.github.com/repos"}`
- **THEN** URL 通过 SSRF 检查，请求正常执行

### Requirement: Web 工具使用 httpx 异步客户端
系统 SHALL 使用 `httpx.AsyncClient` 作为 HTTP 客户端，支持异步非阻塞请求。

#### Scenario: 异步请求
- **WHEN** `web_fetch` 发起 HTTP 请求
- **THEN** 使用 `httpx.AsyncClient.get()` 异步执行，不阻塞事件循环

#### Scenario: 代理配置
- **WHEN** 工具构造时传入 `proxy="http://proxy:8080"`
- **THEN** `httpx.AsyncClient` 使用指定代理发起请求
