## MODIFIED Requirements

### Requirement: ExecTool Shell 执行工具
系统 SHALL 提供 `exec` 工具，通过异步子进程或 sandbox 执行 shell 命令。支持超时控制和输出截断。构造函数新增可选 `sandbox` 参数用于依赖注入。

#### Scenario: 成功执行（宿主机）
- **WHEN** LLM 调用 `exec` 参数 `{"command": "python -c 'print(2+2)'"}` 且无 sandbox 注入
- **THEN** 工具通过 `asyncio.create_subprocess_shell` 异步执行命令并返回 `"4\n"`

#### Scenario: 成功执行（sandbox）
- **WHEN** LLM 调用 `exec` 参数 `{"command": "python -c 'print(2+2)'"}` 且注入了 sandbox 实例
- **THEN** 工具通过 `sandbox.exec(command, timeout)` 执行并返回结果

#### Scenario: 命令超时
- **WHEN** LLM 调用 `exec` 参数 `{"command": "sleep 100"}` 且配置 timeout=30（秒）
- **THEN** 工具在 30 秒后终止进程并返回 `"Error: Command timed out after 30s"`

#### Scenario: 非零退出码
- **WHEN** LLM 调用 `exec` 参数 `{"command": "ls /nonexistent"}`
- **THEN** 工具返回包含 stderr 输出的错误信息，格式为 `"Error (exit code 2): ls: cannot access..."`

#### Scenario: 输出截断
- **WHEN** 命令输出超过 `max_output_chars`（默认 10000）
- **THEN** 工具截断输出并追加 `"\n...[truncated, {total} chars total]"`

#### Scenario: 工作目录限制
- **WHEN** 工具配置 `restrict_to_workspace=True` 且 `working_dir="/workspace"`
- **THEN** 命令在 `/workspace` 目录下执行，且不允许 `cd` 超出工作区

### Requirement: ExecTool 安全检查集成
系统 SHALL 在执行 shell 命令前通过 SafetyManager 进行命令安全检查，权限检查通过 SafetyManager → PermissionGuard 管线执行。安全检查 SHALL 区分三级风险：`safe`（直接放行）、`risky`（需用户确认）、`blocked`（硬拦截）。

#### Scenario: 破坏性命令被阻止
- **WHEN** LLM 调用 `exec` 参数 `{"command": "rm -rf /"}`
- **THEN** SafetyManager 检测到破坏性命令，返回 `risk_level="blocked"`，工具返回 `"Error: Command blocked by safety policy: dangerous pattern detected"`

#### Scenario: 安全命令放行
- **WHEN** LLM 调用 `exec` 参数 `{"command": "git status"}`
- **THEN** 命令通过安全检查（`risk_level="safe"`）和权限检查，正常执行

#### Scenario: 管道命令标记为 risky
- **WHEN** LLM 调用 `exec` 参数 `{"command": "curl -s https://example.com | head -20"}`
- **THEN** SafetyManager 检测到低风险元字符 `|`，返回 `risk_level="risky"`，操作 SHALL 转入 PermissionMiddleware 请求用户确认

#### Scenario: 命令替换被阻止
- **WHEN** LLM 调用 `exec` 参数 `{"command": "echo $(whoami)"}`
- **THEN** SafetyManager 检测到高风险元字符 `$(`，返回 `risk_level="blocked"`，工具返回 `"Error: Command blocked by safety policy: Dangerous shell metacharacter detected"`
