## MODIFIED Requirements

### Requirement: Human-in-the-Loop 分层审批
系统 SHALL 基于操作类型实施三层审批：Read 自动通过 → Write 需人类确认 → Dangerous 直接阻止。审批 MUST 在 `ToolRegistry.execute()` 中通过 `PermissionGuard` 的 ask user 级别实际调用 `SafetyManager.approve_operation()`。

#### Scenario: Read 自动通过
- **WHEN** Agent 执行文件读取操作（`read_file`、`list_dir`）
- **THEN** `approve_operation(level="read")` 自动通过

#### Scenario: Write 需人类确认
- **WHEN** Agent 执行文件写入操作（`write_file`、`edit_file`），权限模式为 `cautious` 或 `fluent`，且无 allow 规则命中
- **THEN** `approve_operation(level="write")` 暂停执行，通过 CLI 向人类展示操作摘要

#### Scenario: Dangerous 直接阻止
- **WHEN** Agent 执行删除文件或破坏性系统命令
- **THEN** `approve_operation(level="dangerous")` 直接阻止

#### Scenario: Session-level 信任提升
- **WHEN** 同一 session 内连续 5 次确认同一类型的写操作
- **THEN** SafetyManager 自动将该类型操作提升为自动通过

#### Scenario: 白名单路径
- **WHEN** 配置了 `trusted_paths: ["/tmp/agent_workspace"]`
- **THEN** 在白名单路径下的写操作自动通过

#### Scenario: HITL Trace
- **WHEN** 一次操作经过 HITL 审批
- **THEN** trace 包含 hitl_level、approved_by、operation_summary
