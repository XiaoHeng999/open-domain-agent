## MODIFIED Requirements

### Requirement: 工具执行参数校验管道
工具执行 SHALL 通过可组合的 middleware chain 执行，内置管道顺序为：SafetyMiddleware → PermissionMiddleware → ExecuteMiddleware → TruncateMiddleware。每个 middleware SHALL 支持 `async def process(name, params, context, next)` 签名，可独立测试。Recovery 重试 SHALL 使用同一管道，确保安全检查不被绕过。

#### Scenario: Recovery 重试经过安全检查
- **WHEN** 工具执行失败触发 recovery，recovery 策略尝试修正参数重试，但修正后的参数违反安全规则
- **THEN** 重试 SHALL 被安全 middleware 阻止，recovery SHALL 报告失败

#### Scenario: 正常执行经过完整管道
- **WHEN** 调用 `registry.execute("exec", {"command": "ls"})`
- **THEN** SHALL 依次经过 safety → permission → execute → truncate 四个阶段

### Requirement: MCP 工具统一注册与输出
MCP 远程工具注册到 ToolRegistry 后，在执行时 SHALL 经过与内置工具相同的 middleware chain，不因 FunctionTool 适配器而绕过安全管道。

#### Scenario: MCP 工具执行经过安全检查
- **WHEN** MCP 注册的远程工具通过 registry.execute() 被调用
- **THEN** SHALL 经过 safety 和 permission middleware 检查
