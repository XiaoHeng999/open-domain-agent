## ADDED Requirements

### Requirement: 命令安全防护
系统 SHALL 在执行任何 shell 命令前进行安全检查，阻止破坏性命令，支持黑名单和白名单模式。

#### Scenario: 阻止 rm -rf
- **WHEN** Agent 尝试执行 `rm -rf /` 或 `rm -rf ~`
- **THEN** 系统直接阻止该命令，返回 DangerousOperationError，记录到 trace

#### Scenario: 阻止 fork bomb
- **WHEN** Agent 尝试执行 `:(){ :|:& };:` 或其变体
- **THEN** 系统检测到 fork bomb 模式并阻止

#### Scenario: 阻止磁盘破坏命令
- **WHEN** Agent 尝试执行 `mkfs`、`dd if=/dev/zero of=/dev/sda` 等命令
- **THEN** 系统直接阻止并返回 DangerousOperationError

#### Scenario: 安全校验 trace
- **WHEN** 一次命令被安全检查阻止
- **THEN** trace 包含 blocked_command、block_reason、safety_level="dangerous"

### Requirement: SSRF 保护
系统 SHALL 在执行任何网络请求前检查目标 URL，阻止内网地址和私有域名。

#### Scenario: 阻止内网 IP
- **WHEN** Agent 尝试访问 `http://127.0.0.1/admin` 或 `http://10.0.0.1/internal`
- **THEN** 系统阻止请求，返回 SSRFError，记录到 trace

#### Scenario: 阻止云元数据端点
- **WHEN** Agent 尝试访问 `http://169.254.169.254/latest/meta-data/`
- **THEN** 系统阻止请求，防止云凭证泄露

#### Scenario: DNS 重绑定防护
- **WHEN** URL 域名解析后的 IP 为内网地址
- **THEN** 系统在 DNS 解析后二次检查 IP，阻止重绑定攻击

#### Scenario: 安全 URL 放行
- **WHEN** Agent 尝试访问 `https://api.github.com/repos`
- **THEN** URL 通过 SSRF 检查，请求正常执行

### Requirement: 工作区路径限制
系统 SHALL 将文件操作限制在配置的工作区目录内，阻止路径遍历和敏感文件访问。

#### Scenario: 阻止路径遍历
- **WHEN** Agent 尝试读取 `../../../etc/passwd`
- **THEN** 系统检测到路径遍历，阻止操作

#### Scenario: 阻止敏感文件访问
- **WHEN** Agent 尝试读取 `.env` 或 `credentials.json`
- **THEN** 系统根据配置的敏感文件列表阻止访问或降级为 HITL 审批

#### Scenario: 工作区内操作放行
- **WHEN** Agent 尝试读取工作区内的 `src/main.py`
- **THEN** 路径检查通过，操作正常执行

### Requirement: Human-in-the-Loop 分层审批
系统 SHALL 基于操作类型实施三层审批：Read 自动通过 → Write 需人类确认 → Dangerous 直接阻止。

#### Scenario: Read 自动通过
- **WHEN** Agent 执行文件读取操作
- **THEN** 操作自动通过，不等待人类确认

#### Scenario: Write 需人类确认
- **WHEN** Agent 执行文件写入操作
- **THEN** 系统暂停执行，通过 CLI（Rich 交互式确认）向人类展示操作摘要，等待 `[y/N]` 确认

#### Scenario: Dangerous 直接阻止
- **WHEN** Agent 执行删除文件或系统命令
- **THEN** 操作直接被阻止，不经过 HITL 确认

#### Scenario: Session-level 信任提升
- **WHEN** 同一 session 内连续 5 次确认同一类型的写操作
- **THEN** 系统自动将该类型操作提升为自动通过，减少确认频率

#### Scenario: 白名单路径
- **WHEN** 配置了 `trusted_paths: ["/tmp/agent_workspace"]`
- **THEN** 在白名单路径下的写操作自动通过

#### Scenario: HITL Trace
- **WHEN** 一次操作经过 HITL 审批
- **THEN** trace 包含 hitl_level（read/write/dangerous）、approved_by（"auto"/"human"/"blocked"）、operation_summary

### Requirement: Sandbox-as-Tools（Daytona）
系统 SHALL 以 "sandbox as tools" 方式集成 Daytona sandbox，文件操作和命令执行通过 sandbox 工具完成。

#### Scenario: Sandbox 命令执行
- **WHEN** Agent 调用 `sandbox_exec` 工具执行 `python script.py`
- **THEN** 命令在 Daytona sandbox 中执行，结果返回给 Agent，宿主机不受影响

#### Scenario: Sandbox 文件操作
- **WHEN** Agent 调用 `sandbox_write_file` 写入代码文件
- **THEN** 文件写入 sandbox 的文件系统，宿主机不受影响

#### Scenario: Sandbox 快照与恢复
- **WHEN** Agent 调用 `sandbox_snapshot` 创建快照
- **THEN** sandbox 状态被保存，后续可通过 `sandbox_restore` 恢复

#### Scenario: Docker fallback
- **WHEN** Daytona 服务不可用
- **THEN** 框架降级到 Docker-based sandbox 实现，通过 Factory 模式切换

### Requirement: 安全防护可配置性
系统 SHALL 支持安全级别的配置：strict（所有安全检查启用）→ permissive（仅阻止 dangerous）→ off（无安全检查）。

#### Scenario: Strict 模式
- **WHEN** 配置 safety_level="strict"
- **THEN** 命令黑名单、SSRF 保护、路径限制、HITL 全部启用

#### Scenario: Permissive 模式
- **WHEN** 配置 safety_level="permissive"
- **THEN** 仅阻止 dangerous 操作，SSRF 保护启用，HITL 关闭
