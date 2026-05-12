## ADDED Requirements

### Requirement: MCP 工具发现与自动注册
系统 SHALL 在 MCP server 连接建立后自动调用 `tools/list` 发现远程工具，将每个工具通过 `FunctionTool` 适配器包装并注册到 `ToolRegistry`。

#### Scenario: 启动 server 后自动发现工具
- **WHEN** 调用 `MCPServerManager.start_server(server_id)` 并成功建立 transport 连接
- **THEN** 系统自动向 MCP server 发送 `tools/list` JSON-RPC 2.0 请求，解析响应中的工具列表，逐个调用 `register_tool_with_schema()` 注册到 `ToolRegistry`

#### Scenario: 工具发现返回空列表
- **WHEN** MCP server 的 `tools/list` 响应返回空工具列表
- **THEN** 系统记录 info 级别日志 "No tools discovered from server {server_id}"，不抛出异常，server 状态保持 healthy

#### Scenario: 工具发现超时
- **WHEN** `tools/list` 请求超过 `tool_discovery_timeout`（默认 30 秒）未响应
- **THEN** 系统记录 warning 级别日志，server 状态保持 registered 但标记为 discovery_failed，不影响其他 server

#### Scenario: 工具名冲突检测
- **WHEN** 发现的工具名与 `ToolRegistry` 中已注册的工具同名
- **THEN** 系统记录 warning 级别日志 "Tool name conflict: {name} from server {server_id}，skipping"，跳过该工具注册，不抛出异常

#### Scenario: 工具 schema 深度转换
- **WHEN** MCP server 返回的工具 schema 包含嵌套结构（`$defs`、`anyOf`、`oneOf`、嵌套 `properties`）
- **THEN** 系统递归转换 schema，确保输出与 Anthropic `input_schema` 格式兼容，`FunctionTool.parameters` 持有转换后的 schema

#### Scenario: 健康恢复后重新发现工具
- **WHEN** 之前 discovery_failed 的 server 通过健康检查恢复
- **THEN** 系统重新执行工具发现流程，注册新发现的工具
