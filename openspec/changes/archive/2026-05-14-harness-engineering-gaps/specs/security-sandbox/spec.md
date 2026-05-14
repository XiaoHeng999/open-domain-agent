## ADDED Requirements

### Requirement: 沙箱执行 SHALL 强制 auto_timeout
所有沙箱后端（SubprocessSandbox、DockerSandbox、DaytonaSandbox）的 `exec()` 方法 SHALL 使用 `asyncio.wait_for()` 包装执行过程，超时值为 `SandboxConfig.auto_timeout`（默认 300 秒）。超时后 SHALL 抛出 `asyncio.TimeoutError`，由上层 recovery 机制处理。

#### Scenario: 执行超时被强制终止
- **WHEN** 沙箱命令执行时间超过 auto_timeout（300 秒）
- **THEN** 执行 SHALL 被取消，抛出 asyncio.TimeoutError
- **THEN** 错误消息包含 "Sandbox execution timed out after {auto_timeout}s"

#### Scenario: 正常执行不受超时影响
- **WHEN** 沙箱命令在 10 秒内完成，auto_timeout 为 300 秒
- **THEN** 正常返回执行结果，无超时错误

#### Scenario: 自定义 auto_timeout 生效
- **WHEN** 配置设置 auto_timeout=60，沙箱命令执行 61 秒
- **THEN** 执行 SHALL 被超时终止

### Requirement: Docker 沙箱 SHALL 实现 restore
`DockerSandbox.restore(snapshot_id)` SHALL 从之前 commit 的镜像重新创建容器。restore 后 SHALL 验证新容器可正常执行命令。

#### Scenario: 从 snapshot 成功恢复
- **WHEN** 调用 DockerSandbox.restore("snap-001")，且 snap-001 是之前通过 snapshot() commit 的镜像
- **THEN** SHALL 停止并移除当前容器
- **THEN** SHALL 从 snap-001 镜像创建新容器
- **THEN** SHALL 在新容器中执行 `echo ok` 验证可用性
- **THEN** 返回 True 表示恢复成功

#### Scenario: snapshot 不存在时 restore 失败
- **WHEN** 调用 DockerSandbox.restore("nonexistent-snap")
- **THEN** SHALL 返回 False，并记录错误 "Snapshot nonexistent-snap not found"

#### Scenario: restore 后新容器工作目录正确
- **WHEN** 从 snapshot 恢复容器
- **THEN** 新容器的工作目录 SHALL 与 snapshot 时一致
