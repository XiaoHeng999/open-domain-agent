## MODIFIED Requirements

### Requirement: PermissionGuard 权限决策中间件
PermissionGuard SHALL 作为 middleware chain 中的一个环节执行，而非嵌入在 ToolRegistry.execute() 的硬编码管道中。Recovery 重试 SHALL 经过 PermissionGuard 检查，确保恢复路径不会绕过权限控制。`_match_rules` 方法 SHALL 对所有从 `params` 中提取的参数值进行类型保护，确保字符串 `in` 操作的操作数类型正确。

#### Scenario: Recovery 重试被权限拒绝
- **WHEN** 工具执行失败触发 recovery，recovery 尝试重试，但当前权限模式为 conservative 且工具为写操作
- **THEN** PermissionGuard SHALL 拒绝重试，recovery 报告失败

#### Scenario: URL 参数为非字符串类型
- **WHEN** `_match_rules` 检查 `rule.domain not in url`，且 `params.get("url")` 返回 dict 或其他非字符串类型
- **THEN** 系统 SHALL 将该值转换为字符串后再执行 `in` 检查，不 SHALL 抛出 TypeError

#### Scenario: command 参数为非字符串类型
- **WHEN** `_match_rules` 检查 `fnmatch(command, rule.pattern)`，且 `params.get("command")` 返回非字符串类型
- **THEN** 系统 SHALL 将该值转换为字符串后再执行 fnmatch，不 SHALL 抛出 TypeError

#### Scenario: path 参数为非字符串类型
- **WHEN** `_match_rules` 检查 `fnmatch(path, rule.path)`，且 `params.get("path")` 返回非字符串类型
- **THEN** 系统 SHALL 将该值转换为字符串后再执行 fnmatch，不 SHALL 抛出 TypeError
