## ADDED Requirements

### Requirement: DuckDuckGo 搜索工具
系统 SHALL 提供 `DuckDuckGoSearchTool`，使用 `duckduckgo-search` 库执行免费网络搜索，无需 API Key。

#### Scenario: 成功搜索
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "Python async patterns"}`
- **THEN** 工具通过 DuckDuckGo 执行搜索并返回格式化的结果列表（序号 + 标题 + URL + 摘要）

#### Scenario: 无结果
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "xyznonexistent12345"}`
- **THEN** 工具返回 `"No results found for query: xyznonexistent12345"`

#### Scenario: 结果数量限制
- **WHEN** LLM 调用 `web_search` 参数 `{"query": "test", "count": 3}`
- **THEN** 工具最多返回 3 条结果

#### Scenario: 网络异常
- **WHEN** DuckDuckGo 搜索因网络错误失败
- **THEN** 工具返回 `"Error: Search failed: <异常信息>"`

### Requirement: 搜索后端自动选择
系统 SHALL 根据 `search_backend` 配置项自动选择搜索后端注册到 ToolRegistry，LLM 看到的工具名统一为 `web_search`。

#### Scenario: auto 模式有 Brave Key
- **WHEN** `search_backend = "auto"` 且 `brave_search_api_key` 已配置
- **THEN** 注册 `BraveSearchTool`（name="web_search"）

#### Scenario: auto 模式无 Brave Key
- **WHEN** `search_backend = "auto"` 且 `brave_search_api_key` 未配置
- **THEN** 注册 `DuckDuckGoSearchTool`（name="web_search"）

#### Scenario: 强制 DuckDuckGo
- **WHEN** `search_backend = "duckduckgo"`
- **THEN** 无论是否有 Brave Key，都注册 `DuckDuckGoSearchTool`

#### Scenario: 强制 Brave 但无 Key
- **WHEN** `search_backend = "brave"` 且 `brave_search_api_key` 未配置
- **THEN** 不注册任何搜索工具，LLM 看不到 `web_search`

### Requirement: 搜索工具统一接口
所有搜索后端 SHALL 实现相同的 Tool ABC 接口，对外的 `name`、`description`、`parameters` schema 完全一致。

#### Scenario: 工具 schema 一致性
- **WHEN** 注册了任意搜索后端
- **THEN** 工具的 `name` 为 `"web_search"`，`parameters` 包含 `query`（string, required）和 `count`（integer, optional）
