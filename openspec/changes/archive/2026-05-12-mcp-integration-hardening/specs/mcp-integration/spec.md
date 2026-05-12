## MODIFIED Requirements

### Requirement: MCP Server 生命周期管理
系统 SHALL 支持 MCP Server 的注册、启动、停止、健康检查。Server 启动时自动发现工具并注册到 `ToolRegistry`。`MCPServerManager` 由 `AgentRuntime` 在 `on_start` 时初始化，从配置加载 servers 并启动。停止时通过 `AgentRuntime.on_stop` 优雅关闭所有 server。

#### Scenario: Server 健康检查
- **WHEN** MCP Server 连续 3 次健康检查失败
- **THEN** 框架将其标记为 unhealthy，停止向其路由工具调用，触发告警

#### Scenario: Server 停止时工具清理
- **WHEN** 调用 `MCPServerManager.stop_server(id)`
- **THEN** 通过 `registry.unregister_by_server(id)` 移除所有该 server 的工具

#### Scenario: Runtime 启动时初始化 MCP
- **WHEN** `AgentRuntime.on_start()` 执行且配置中包含 MCP servers
- **THEN** 创建 `MCPServerManager` 实例，逐个注册并启动配置中的 servers，每个 server 启动后自动发现工具

#### Scenario: Runtime 停止时关闭 MCP
- **WHEN** `AgentRuntime.on_stop()` 执行
- **THEN** 遍历所有已启动的 MCP servers，调用 `stop_server()` 优雅关闭

#### Scenario: 并行启动多个 server
- **WHEN** 配置中包含多个 MCP servers
- **THEN** 使用 `asyncio.gather` 并行启动所有 servers，总超时受 `connect_timeout` 控制

## ADDED Requirements

### Requirement: JSON-RPC 2.0 协议合规
系统 SHALL 在所有 MCP transport（STDIO、SSE、HTTP）中严格遵循 JSON-RPC 2.0 协议格式，包括唯一请求 id、标准错误响应解析。

#### Scenario: 唯一请求 id
- **WHEN** 通过任何 transport 发送 JSON-RPC 请求
- **THEN** 每个请求携带唯一递增的 `id`（字符串类型），`MCPTransport` 内部维护原子计数器

#### Scenario: 标准错误响应解析
- **WHEN** MCP server 返回 JSON-RPC 错误响应 `{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": "3"}`
- **THEN** 系统解析 `error.code` 和 `error.message`，抛出 `MCPError` 异常携带错误码和消息

#### Scenario: 响应 id 匹配
- **WHEN** 收到 JSON-RPC 响应
- **THEN** 系统验证响应 `id` 与请求 `id` 匹配，不匹配时记录 warning 并忽略该响应

### Requirement: HTTP Transport JSON-RPC 2.0 合规
系统 SHALL 在 HTTP transport 中使用 JSON-RPC 2.0 格式发送请求（而非裸 JSON），请求体包含 `jsonrpc`、`method`、`params`、`id` 字段。

#### Scenario: HTTP 调用工具
- **WHEN** 通过 HTTP transport 调用 `call_tool(tool_name, arguments)`
- **THEN** 发送 POST 请求到 `{url}` ，请求体为 `{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}, "id": "<unique_id>"}`

#### Scenario: HTTP 工具发现
- **WHEN** 通过 HTTP transport 发送 `tools/list` 请求
- **THEN** 发送 POST 请求体为 `{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": "<unique_id>"}`

### Requirement: SSE Transport 实现
系统 SHALL 实现 SSE transport，通过 HTTP POST 发送请求，通过 SSE EventSource 接收响应。

#### Scenario: SSE 连接建立
- **WHEN** SSE transport 的 `connect()` 被调用
- **THEN** 系统通过 `httpx` 建立 SSE 连接到 `{url}/sse`，保持长连接用于接收 server-push 消息

#### Scenario: SSE 工具调用
- **WHEN** 通过 SSE transport 调用 `call_tool(tool_name, arguments)`
- **THEN** 系统通过 HTTP POST 发送 JSON-RPC 2.0 请求到 `{url}/messages`，通过 SSE stream 接收响应

#### Scenario: SSE 连接断开重连
- **WHEN** SSE 连接意外断开
- **THEN** 系统自动重连，重连间隔指数退避（1s → 2s → 4s，最大 30s），最多重试 5 次
