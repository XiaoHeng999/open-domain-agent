## MODIFIED Requirements

### Requirement: MCP 工具统一注册与输出
MCP 远程工具注册到 ToolRegistry 后，在执行时 SHALL 经过与内置工具相同的 middleware chain，不因 FunctionTool 适配器而绕过安全管道。SubagentTool 注册到 ToolRegistry 后 SHALL 同样经过 middleware chain，但 SafetyMiddleware 和 PermissionMiddleware SHALL 对 `task` 工具放行（子代理内部已有独立的中间件链）。

#### Scenario: MCP 工具执行经过安全检查
- **WHEN** MCP 注册的远程工具通过 registry.execute() 被调用
- **THEN** SHALL 经过 safety 和 permission middleware 检查

#### Scenario: SubagentTool 执行通过中间件链
- **WHEN** `task` 工具通过 registry.execute() 被调用
- **THEN** SHALL 经过 safety 和 permission middleware
- **THEN** safety middleware SHALL 对 `task` 工具直接放行（不检查参数内容）
- **THEN** permission middleware SHALL 对 `task` 工具直接放行（子代理内部有独立权限控制）
