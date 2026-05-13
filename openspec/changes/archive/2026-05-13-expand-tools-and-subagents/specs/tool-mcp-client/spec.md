## ADDED Requirements

### Requirement: MCP 客户端工具连接服务器
`mcp_client` 工具 SHALL 提供 `action="connect"` 操作，运行时动态连接一个新的 MCP Server。支持 stdio 和 HTTP/SSE 两种传输方式。

#### Scenario: 通过 stdio 连接 MCP Server
- **WHEN** Agent 调用 `mcp_client` 工具并传入 `action="connect"`、`server_id="my-server"`、`transport="stdio"`、`command="npx my-mcp-server"`
- **THEN** SHALL 调用 MCPServerManager 创建并启动该服务器连接
- **THEN** SHALL 将该服务器暴露的工具自动注册到 ToolRegistry

#### Scenario: 通过 HTTP 连接 MCP Server
- **WHEN** Agent 调用 `mcp_client` 工具并传入 `action="connect"`、`server_id="remote-server"`、`transport="http"`、`url="http://localhost:3000/mcp"`
- **THEN** SHALL 连接到指定 URL 的 MCP Server
- **THEN** SHALL 自动发现并注册该服务器的工具

### Requirement: MCP 客户端工具断开服务器
`mcp_client` 工具 SHALL 提供 `action="disconnect"` 操作，断开并清理指定 MCP Server 的连接和已注册工具。

#### Scenario: 断开服务器连接
- **WHEN** Agent 调用 `mcp_client` 工具并传入 `action="disconnect"`、`server_id="my-server"`
- **THEN** SHALL 调用 MCPServerManager 停止该服务器
- **THEN** SHALL 从 ToolRegistry 中移除该服务器注册的所有工具

### Requirement: MCP 客户端工具列出服务器
`mcp_client` 工具 SHALL 提供 `action="list"` 操作，返回当前已连接的 MCP Server 列表及各服务器提供的工具数量。

#### Scenario: 列出已连接服务器
- **WHEN** Agent 调用 `mcp_client` 工具并传入 `action="list"`
- **THEN** SHALL 返回所有已连接 MCP Server 的 server_id、健康状态和工具数量

### Requirement: MCP 客户端工具安全属性
`mcp_client` 工具 SHALL 标记为 `read_only=False`，`safety_checks` SHALL 包含 `["command"]`。

#### Scenario: 安全检查标记
- **WHEN** `mcp_client` 工具注册到 ToolRegistry
- **THEN** `read_only` SHALL 为 False
- **THEN** `safety_checks` SHALL 包含 `["command"]`

### Requirement: MCP 客户端工具与 MCP 模块解耦
`mcp_client` 工具 SHALL 仅定义在 `tools/mcp_client.py` 中，通过构造函数注入 `MCPServerManager` 实例。MCP 传输协议和服务器管理逻辑保留在 `mcp_integration.py` 中不变。

#### Scenario: 依赖注入方式
- **WHEN** runtime 创建 MCPClientTool 实例
- **THEN** SHALL 通过构造函数传入 MCPServerManager 实例
- **THEN** MCPClientTool SHALL 不直接实现传输层协议
