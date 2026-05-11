## MODIFIED Requirements

### Requirement: 命令安全防护
系统 SHALL 在执行任何 shell 命令前进行安全检查，阻止破坏性命令，支持黑名单和白名单模式。安全检查 MUST 在 `ToolRegistry.execute()` 执行管道中实际调用，而非仅作为声明式 API 存在。

#### Scenario: 阻止 rm -rf
- **WHEN** Agent 尝试通过 `exec` 工具执行 `rm -rf /` 或 `rm -rf ~`
- **THEN** `SafetyManager.check_command()` 在 `ToolRegistry.execute()` 中被调用，阻止该命令，返回错误字符串，记录到 trace

#### Scenario: 阻止 fork bomb
- **WHEN** Agent 尝试通过 `exec` 工具执行 `:(){ :|:& };:` 或其变体
- **THEN** SafetyManager 检测到 fork bomb 模式并阻止

#### Scenario: 阻止磁盘破坏命令
- **WHEN** Agent 尝试通过 `exec` 工具执行 `mkfs`、`dd if=/dev/zero of=/dev/sda` 等命令
- **THEN** SafetyManager 直接阻止

#### Scenario: 安全校验 trace
- **WHEN** 一次命令被安全检查阻止
- **THEN** trace 包含 blocked_command、block_reason、safety_level="dangerous"

### Requirement: SSRF 保护
系统 SHALL 在执行任何网络请求前检查目标 URL，阻止内网地址和私有域名。检查 MUST 在 `ToolRegistry.execute()` 中通过 `SafetyManager.check_url()` 实际执行。

#### Scenario: 阻止内网 IP
- **WHEN** Agent 通过 `web_fetch` 工具尝试访问 `http://127.0.0.1/admin`
- **THEN** `SafetyManager.check_url()` 在 execute 管道中阻止请求

#### Scenario: 阻止云元数据端点
- **WHEN** Agent 通过 `web_fetch` 工具尝试访问 `http://169.254.169.254/latest/meta-data/`
- **THEN** SafetyManager 阻止请求

#### Scenario: DNS 重绑定防护
- **WHEN** URL 域名解析后的 IP 为内网地址
- **THEN** SafetyManager 在 DNS 解析后二次检查 IP，阻止重绑定攻击

#### Scenario: 安全 URL 放行
- **WHEN** Agent 通过 `web_fetch` 工具尝试访问 `https://api.github.com/repos`
- **THEN** URL 通过 SSRF 检查，请求正常执行

### Requirement: 工作区路径限制
系统 SHALL 将文件操作限制在配置的工作区目录内，阻止路径遍历和敏感文件访问。检查 MUST 在 `ToolRegistry.execute()` 中通过 `SafetyManager.check_path()` 实际执行。

#### Scenario: 阻止路径遍历
- **WHEN** Agent 通过 `read_file` 工具尝试读取 `../../../etc/passwd`
- **THEN** `SafetyManager.check_path()` 在 execute 管道中阻止操作

#### Scenario: 阻止敏感文件访问
- **WHEN** Agent 通过 `read_file` 工具尝试读取 `.env`
- **THEN** SafetyManager 根据配置的敏感文件列表阻止访问或降级为 HITL 审批

#### Scenario: 工作区内操作放行
- **WHEN** Agent 通过 `read_file` 工具尝试读取工作区内的 `src/main.py`
- **THEN** 路径检查通过，操作正常执行

### Requirement: Human-in-the-Loop 分层审批
系统 SHALL 基于操作类型实施三层审批：Read 自动通过 → Write 需人类确认 → Dangerous 直接阻止。审批 MUST 在 `ToolRegistry.execute()` 中通过 `SafetyManager.approve_operation()` 实际执行。

#### Scenario: Read 自动通过
- **WHEN** Agent 执行文件读取操作（`read_file`、`list_dir`）
- **THEN** `approve_operation(level="read")` 自动通过

#### Scenario: Write 需人类确认
- **WHEN** Agent 执行文件写入操作（`write_file`、`edit_file`）
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
