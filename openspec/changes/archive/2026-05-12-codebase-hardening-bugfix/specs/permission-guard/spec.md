## MODIFIED Requirements

### Requirement: PermissionGuard 权限决策中间件
PermissionGuard SHALL 作为 middleware chain 中的一个环节执行，而非嵌入在 ToolRegistry.execute() 的硬编码管道中。Recovery 重试 SHALL 经过 PermissionGuard 检查，确保恢复路径不会绕过权限控制。

#### Scenario: Recovery 重试被权限拒绝
- **WHEN** 工具执行失败触发 recovery，recovery 尝试重试，但当前权限模式为 conservative 且工具为写操作
- **THEN** PermissionGuard SHALL 拒绝重试，recovery 报告失败
