## MODIFIED Requirements

### Requirement: AgentRuntime Sandbox 注入
Sandbox 的 `on_start()` SHALL 在 `AgentRuntime.on_start()` 中以 `await` 方式同步完成，而非 fire-and-forget 的 `create_task`。Sandbox 未完成初始化时 ExecTool SHALL NOT 被注册使用。

#### Scenario: Sandbox 初始化完成后再注册 ExecTool
- **WHEN** AgentRuntime.on_start() 执行 sandbox 初始化
- **THEN** SHALL await sandbox.on_start() 完成后再创建和注册 ExecTool

#### Scenario: Sandbox 初始化失败时降级
- **WHEN** sandbox.on_start() 抛出异常
- **THEN** SHALL 降级到 SubprocessSandbox 并记录警告日志
