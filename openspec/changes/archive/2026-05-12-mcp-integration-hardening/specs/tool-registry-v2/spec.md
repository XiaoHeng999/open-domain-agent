## MODIFIED Requirements

### Requirement: 工具执行参数校验管道
系统 SHALL 在 `ToolRegistry.execute()` 中实现四阶段管道：cast → validate → safety checks → permission guard → execute。新增 `permission_guard` 参数在构造函数中注入。MCP 远程工具通过工具发现自动注册后，走相同管道执行。

#### Scenario: 校验失败返回错误
- **WHEN** `validate_params()` 返回非空错误列表
- **THEN** 执行中止，返回格式化的校验错误字符串，LLM 可据此修正参数

#### Scenario: 安全检查失败返回错误
- **WHEN** `_run_safety_checks()` 返回非空错误字符串
- **THEN** 执行中止，返回安全检查错误字符串，不进入权限检查

#### Scenario: 权限检查拒绝返回错误
- **WHEN** `PermissionGuard.check()` 返回 DENY 决策
- **THEN** 执行中止，返回格式化的权限拒绝错误字符串，格式为 `"Error: Permission denied: {reason}"`

#### Scenario: 权限检查通过继续执行
- **WHEN** `PermissionGuard.check()` 返回 ALLOW 决策
- **THEN** 执行 `await tool.execute(**params)` 并返回结果

#### Scenario: 无 PermissionGuard 时跳过权限检查
- **WHEN** `ToolRegistry.__init__` 的 `permission_guard` 参数为 None
- **THEN** 执行管道跳过权限检查阶段，直接从安全检查进入执行（向后兼容）

## ADDED Requirements

### Requirement: MCP 工具统一注册与输出
系统 SHALL 确保 MCP 远程工具与内置工具在 `ToolRegistry` 中统一管理，`get_definitions()` 输出统一的 Anthropic `tool_use` 格式，ReAct 循环通过 `execute()` 无差别调用。

#### Scenario: MCP 工具出现在 get_definitions 中
- **WHEN** MCP server 的工具通过发现注册到 `ToolRegistry`
- **THEN** `get_definitions()` 的返回列表包含 MCP 工具的 schema，格式与内置工具一致（`{"name", "description", "input_schema"}`）

#### Scenario: ReAct 循环调用 MCP 工具
- **WHEN** LLM 在 ReAct 循环中选择调用一个 MCP 远程工具（如 `db_query`）
- **THEN** `ToolRegistry.execute("db_query", params)` 通过 `FunctionTool.handler` → `MCPServerManager.call_tool()` → `MCPTransport.call_tool()` 路由到正确的 MCP server

#### Scenario: MCP server 断连时工具调用失败
- **WHEN** MCP server 已断连，ReAct 循环调用其注册的工具
- **THEN** `ToolRegistry.execute()` 返回错误字符串 `"Error: Server not connected: {server_id}"`，ReAct 循环将错误信息返回给 LLM 进行自我修正
