## ADDED Requirements

### Requirement: ExecTool 可选 Sandbox 依赖注入
系统 SHALL 修改 `ExecTool` 支持通过构造函数注入可选的 sandbox 实例。当 sandbox 实例存在时，优先通过 sandbox 执行命令；当 sandbox 不存在时，退回宿主机 `asyncio.create_subprocess_shell` 执行。

#### Scenario: 注入 Docker Sandbox 执行命令
- **WHEN** ExecTool 初始化时注入 `DockerSandbox` 实例，LLM 调用 `exec` 参数 `{"command": "python -c 'print(2+2)'"}`
- **THEN** 命令通过 Docker 容器执行，返回结果，宿主机不受影响

#### Scenario: 注入 Daytona Sandbox 执行命令
- **WHEN** ExecTool 初始化时注入 `DaytonaSandbox` 实例
- **THEN** 命令通过 Daytona SDK 在独立 VM 中执行

#### Scenario: 无 Sandbox 退回宿主机执行
- **WHEN** ExecTool 初始化时未注入 sandbox（sandbox=None）
- **THEN** 命令通过 `asyncio.create_subprocess_shell` 在宿主机执行，行为与当前一致

#### Scenario: Sandbox 执行超时
- **WHEN** 通过 sandbox 执行命令，且命令运行时间超过 timeout 参数
- **THEN** sandbox 返回超时错误，ExecTool 将错误转为字符串返回给 LLM

### Requirement: AgentRuntime Sandbox 注入
系统 SHALL 在 `AgentRuntime.on_start()` 中创建 sandbox 实例，并在注册 `ExecTool` 时注入 sandbox，完成 sandbox 与执行路径的连接。

#### Scenario: 配置 Docker 后端
- **WHEN** 配置 `sandbox.backend: "docker"`
- **THEN** AgentRuntime 创建 DockerSandbox 实例，注入到 ExecTool，所有 shell 命令在容器中执行

#### Scenario: 配置 subprocess 后端（默认）
- **WHEN** 配置 `sandbox.backend: "subprocess"` 或未配置
- **THEN** AgentRuntime 创建 SubprocessSandbox 实例，注入到 ExecTool，命令仍在宿主机执行（向后兼容）

#### Scenario: Sandbox 启动失败降级
- **WHEN** 配置 `sandbox.backend: "docker"` 但 Docker 服务不可用
- **THEN** AgentRuntime 降级为 SubprocessSandbox，记录警告日志，ExecTool 继续工作

### Requirement: Sandbox 与权限系统协同
系统 SHALL 确保 sandbox 执行和权限检查独立工作：PermissionGuard 决定"能不能执行"，sandbox 决定"怎么执行"。两层互不依赖。

#### Scenario: 权限拒绝后不触发 sandbox
- **WHEN** PermissionGuard 返回 DENY 决策
- **THEN** `tool.execute()` 不被调用，sandbox 不执行任何操作

#### Scenario: 权限通过后走 sandbox 执行
- **WHEN** PermissionGuard 返回 ALLOW 决策，ExecTool 注入了 sandbox
- **THEN** 命令通过 sandbox 执行
