## ADDED Requirements

### Requirement: PermissionGuard 权限决策中间件
系统 SHALL 提供 `PermissionGuard` 类，实现 `deny rules → permission mode → allow rules → ask user` 四级权限决策管线。作为独立中间件插入 `ToolRegistry.execute()` 执行管道。

#### Scenario: Deny 规则命中直接拒绝
- **WHEN** 工具调用 `exec` 参数 `{"command": "rm -rf /"}` 且存在 deny 规则 `{tool: "exec", pattern: "rm -rf /"}`
- **THEN** PermissionGuard 返回 DENY 决策，附带拒绝原因，工具不执行

#### Scenario: Deny 规则优先级高于 Allow
- **WHEN** 同时存在 deny 规则 `{tool: "exec", pattern: "rm *"}` 和 allow 规则 `{tool: "exec", pattern: "rm *"}`
- **THEN** deny 规则先匹配，操作被拒绝，allow 规则不生效

#### Scenario: Cautious 模式下非 read-only 工具问用户
- **WHEN** 权限模式为 `cautious`，工具 `write_file` 的 `read_only=False`，且无 deny/allow 规则命中
- **THEN** PermissionGuard 调用 HITLApprovalManager.approve()，等待用户确认

#### Scenario: Cautious 模式下 read-only 工具自动放行
- **WHEN** 权限模式为 `cautious`，工具 `read_file` 的 `read_only=True`
- **THEN** PermissionGuard 返回 ALLOW 决策，不问用户

#### Scenario: Conservative 模式下写操作直接拒绝
- **WHEN** 权限模式为 `conservative`，工具 `write_file` 的 `read_only=False`
- **THEN** PermissionGuard 返回 DENY 决策，原因为 "Write blocked in conservative mode"

#### Scenario: Fluent 模式下 allow 规则命中自动放行
- **WHEN** 权限模式为 `fluent`，工具 `exec` 参数 `{"command": "pip install requests"}`，allow 规则 `{tool: "exec", pattern: "pip install *"}`
- **THEN** PermissionGuard 返回 ALLOW 决策，附带 "Allowed by rule" 原因

#### Scenario: Fluent 模式下无规则命中问用户
- **WHEN** 权限模式为 `fluent`，工具 `exec` 参数 `{"command": "curl http://example.com"}`，无 allow/deny 规则命中
- **THEN** PermissionGuard 调用 HITLApprovalManager.approve()，等待用户确认

#### Scenario: Unrestricted 模式下全部放行
- **WHEN** 权限模式为 `unrestricted`，工具 `write_file` 参数写入任意路径，且无 deny 规则命中
- **THEN** PermissionGuard 返回 ALLOW 决策

### Requirement: 4 种权限模式
系统 SHALL 支持 4 种权限模式，通过配置或环境变量选择：`cautious`、`conservative`、`fluent`、`unrestricted`。

#### Scenario: 默认模式为 fluent
- **WHEN** 配置中未指定 `permissions.mode`
- **THEN** PermissionGuard 使用 `fluent` 模式

#### Scenario: 环境变量覆盖模式
- **WHEN** 环境变量 `OPEN_AGENT_PERMISSION_MODE=conservative`
- **THEN** PermissionGuard 使用 `conservative` 模式，忽略配置文件中的 mode 设置

### Requirement: YAML 结构化权限规则
系统 SHALL 支持 YAML 配置中的结构化权限规则列表，每条规则包含 `tool`（工具名或 `*` 通配）和可选的 `pattern`（命令 glob）、`path`（路径 glob）、`domain`（域名匹配）字段。使用 `fnmatch` 进行匹配。

#### Scenario: 通配符匹配所有工具
- **WHEN** deny 规则为 `{tool: "*", pattern: "rm -rf *"}`
- **THEN** 任何工具调用中参数含 `rm -rf` 前缀的操作都被拒绝

#### Scenario: 路径 glob 匹配文件工具
- **WHEN** deny 规则为 `{tool: "read_file", path: "./secrets/**"}`
- **THEN** `read_file` 工具读取 `./secrets/credentials.json` 被拒绝

#### Scenario: 域名匹配 Web 工具
- **WHEN** deny 规则为 `{tool: "web_fetch", domain: "169.254.169.254"}`
- **THEN** `web_fetch` 工具访问 `http://169.254.169.254/latest/meta-data/` 被拒绝

#### Scenario: 精确工具名匹配
- **WHEN** allow 规则为 `{tool: "exec", pattern: "git status"}`
- **THEN** `exec` 工具执行 `git status` 被允许，但 `git push` 不匹配

### Requirement: HITL 用户确认接入
系统 SHALL 在权限管线第 4 级（ask user）调用现有 `HITLApprovalManager.approve()`，实现运行时用户确认。支持"总是允许"选项将动态规则添加到 allow 列表。

#### Scenario: 用户确认通过
- **WHEN** PermissionGuard 进入 ask user 级别，HITLApprovalManager 返回 `approved=True`
- **THEN** PermissionGuard 返回 ALLOW 决策

#### Scenario: 用户拒绝
- **WHEN** PermissionGuard 进入 ask user 级别，HITLApprovalManager 返回 `approved=False`
- **THEN** PermissionGuard 返回 DENY 决策

#### Scenario: 非交互模式默认拒绝
- **WHEN** `HITLApprovalManager` 配置为 `interactive=False` 且无 allow 规则命中
- **THEN** ask user 级别默认返回 DENY 决策

### Requirement: PermissionConfig Pydantic 模型
系统 SHALL 提供 `PermissionConfig` Pydantic 模型，包含 `mode`（PermissionMode 枚举）、`deny`（PermissionRule 列表）、`allow`（PermissionRule 列表）字段。作为 `AgentConfig` 的子配置。

#### Scenario: 缺失 permissions 配置段
- **WHEN** YAML 配置中无 `permissions` 键
- **THEN** `AgentConfig.permissions` 使用默认值：`mode=fluent, deny=[], allow=[]`

#### Scenario: 配置校验
- **WHEN** YAML 配置 `permissions.mode` 为非法值 `"unknown"`
- **THEN** Pydantic 校验失败，抛出 `ValidationError`
