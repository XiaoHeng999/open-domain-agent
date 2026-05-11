## MODIFIED Requirements

### Requirement: 工具执行参数校验管道
系统 SHALL 在 `ToolRegistry.execute()` 中实现四阶段管道：cast → validate → safety checks → permission guard → execute。新增 `permission_guard` 参数在构造函数中注入。

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
