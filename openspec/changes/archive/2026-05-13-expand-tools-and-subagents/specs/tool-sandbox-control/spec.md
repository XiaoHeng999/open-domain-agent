## ADDED Requirements

### Requirement: Sandbox 控制工具生命周期管理
`sandbox_control` 工具 SHALL 提供 `action="start"` 操作，启动一个新的沙箱环境实例。

#### Scenario: 启动沙箱
- **WHEN** Agent 调用 `sandbox_control` 工具并传入 `action="start"`
- **THEN** SHALL 调用注入的 sandbox 实例的启动流程
- **THEN** SHALL 返回沙箱实例 ID 和状态

### Requirement: Sandbox 控制工具命令执行
`sandbox_control` 工具 SHALL 提供 `action="exec"` 操作，在沙箱环境中执行命令。

#### Scenario: 沙箱内执行命令
- **WHEN** Agent 调用 `sandbox_control` 工具并传入 `action="exec"`、`command="python test.py"`
- **THEN** SHALL 通过 sandbox 实例的 `exec()` 方法执行命令
- **THEN** SHALL 返回命令输出（stdout/stderr）和退出码

### Requirement: Sandbox 控制工具快照操作
`sandbox_control` 工具 SHALL 提供 `action="snapshot"` 操作，创建沙箱当前状态的快照。

#### Scenario: 创建快照
- **WHEN** Agent 调用 `sandbox_control` 工具并传入 `action="snapshot"`
- **THEN** SHALL 调用 sandbox 实例的 `snapshot()` 方法
- **THEN** SHALL 返回快照 ID

### Requirement: Sandbox 控制工具恢复操作
`sandbox_control` 工具 SHALL 提供 `action="restore"` 操作，将沙箱恢复到指定快照。

#### Scenario: 从快照恢复
- **WHEN** Agent 调用 `sandbox_control` 工具并传入 `action="restore"`、`snapshot_id="snap_001"`
- **THEN** SHALL 调用 sandbox 实例的 `restore()` 方法
- **THEN** SHALL 返回恢复结果

### Requirement: Sandbox 控制工具安全属性
`sandbox_control` 工具 SHALL 标记为 `read_only=False`，`safety_checks` SHALL 包含 `["command"]`。

#### Scenario: 安全检查标记
- **WHEN** `sandbox_control` 工具注册到 ToolRegistry
- **THEN** `read_only` SHALL 为 False
- **THEN** `safety_checks` SHALL 包含 `["command"]`

### Requirement: Sandbox 控制工具与沙箱模块解耦
`sandbox_control` 工具 SHALL 仅定义在 `tools/sandbox_control.py` 中，通过构造函数注入 sandbox 实例。沙箱后端实现（Docker、Daytona、Subprocess）保留在 `sandbox/` 目录中不变。

#### Scenario: 依赖注入方式
- **WHEN** runtime 创建 SandboxControlTool 实例
- **THEN** SHALL 通过构造函数传入 `SandboxFactory.create()` 创建的 sandbox 实例
- **THEN** SandboxControlTool SHALL 不直接 import sandbox 后端类
