## MODIFIED Requirements

### Requirement: 确定性恢复策略
所有恢复策略（ParameterRecovery、ServiceRecovery、RetrievalRecovery、ParseRecovery）在重试工具执行时 SHALL 通过 ToolRegistry.execute() 或 middleware chain 执行，而非直接调用 `tool_handler(**args)`。这确保重试路径经过完整的安全和权限检查。

#### Scenario: ParameterRecovery 重试经过安全检查
- **WHEN** ParameterRecoveryStrategy 修正参数后重试执行 exec 工具，且修正后的 command 包含危险模式
- **THEN** SHALL 通过 ToolRegistry.execute() 执行，被安全 middleware 拦截，recovery 报告失败

#### Scenario: ServiceRecovery 重试经过权限检查
- **WHEN** ServiceRecoveryStrategy 指数退避后重试，且权限模式为 conservative
- **THEN** 重试 SHALL 经过 PermissionGuard 检查
