## ADDED Requirements

### Requirement: SafetyCheckResult SHALL include risk_level field
`SafetyCheckResult` dataclass SHALL 新增 `risk_level` 字段，取值为 `"safe"` / `"risky"` / `"blocked"` 三级之一。当 `safe=True` 时 `risk_level` SHALL 为 `"safe"`。当 `safe=False` 时，`risk_level` 由检查器根据威胁等级设定。

#### Scenario: Safe command produces safe risk level
- **WHEN** CommandSafetyChecker 检查 `"git status"`
- **THEN** SafetyCheckResult SHALL 返回 `safe=True, risk_level="safe"`

#### Scenario: Dangerous command produces blocked risk level
- **WHEN** CommandSafetyChecker 检查 `"rm -rf /"`
- **THEN** SafetyCheckResult SHALL 返回 `safe=False, risk_level="blocked"`

#### Scenario: Low-risk metacharacter produces risky risk level
- **WHEN** CommandSafetyChecker 检查 `"curl -s https://example.com | head -20"`，管道符 `|` 为低风险元字符
- **THEN** SafetyCheckResult SHALL 返回 `safe=False, risk_level="risky"`

### Requirement: CommandSafetyChecker SHALL classify metacharacters into risk tiers
CommandSafetyChecker SHALL 将 shell 元字符分为两个级别：低风险元字符（`|`、`&&`、`||`）和高风险元字符（`;`、`$(`、反引号、`>`、`<`）。低风险元字符触发 `risky` 级别，高风险元字符触发 `blocked` 级别。

#### Scenario: Pipe metacharacter classified as risky
- **WHEN** CommandSafetyChecker 检查命令 `"cat file.txt | grep error"`
- **THEN** 匹配管道符 `|` 后 SHALL 返回 `risk_level="risky"`，reason 包含 "low-risk shell metacharacter"

#### Scenario: Command substitution classified as blocked
- **WHEN** CommandSafetyChecker 检查命令 `"echo $(cat /etc/passwd)"`
- **THEN** 匹配 `$(` 后 SHALL 返回 `risk_level="blocked"`，reason 包含 "Dangerous shell metacharacter"

#### Scenario: Redirect output classified as blocked
- **WHEN** CommandSafetyChecker 检查命令 `"echo data > /tmp/file"`
- **THEN** 匹配 `>` 后 SHALL 返回 `risk_level="blocked"`

#### Scenario: No metacharacters passes through to blacklist check
- **WHEN** CommandSafetyChecker 检查命令 `"ls -la"`（无元字符）
- **THEN** SHALL 跳过元字符检查，继续黑名单模式检查，返回 `safe=True, risk_level="safe"`

### Requirement: SafetyMiddleware SHALL pass risk info instead of hard-blocking on risky
SafetyMiddleware SHALL 仅对 `blocked` 级别的安全检查结果直接短路返回错误。对 `risky` 级别的结果，SafetyMiddleware SHALL 将风险信息附加到 `MiddlewareContext` 上（`context.safety_risks`），然后继续执行 `next()`，由下游 PermissionMiddleware 决定是否需要用户确认。

#### Scenario: Blocked risk short-circuits the chain
- **WHEN** SafetyMiddleware 检测到 `risk_level="blocked"`（如 `rm -rf /`）
- **THEN** SHALL 直接返回 `"Error: Command blocked by safety policy: ..."` 并短路链路

#### Scenario: Risky risk continues chain with context
- **WHEN** SafetyMiddleware 检测到 `risk_level="risky"`（如 `curl | head`）
- **THEN** SHALL 将 `SafetyRisk(tool_name=..., check_type=..., reason=..., risk_level="risky")` 附加到 `context.safety_risks`，并调用 `await next()` 继续链路

#### Scenario: Safe result passes through
- **WHEN** SafetyMiddleware 检测到 `risk_level="safe"`
- **THEN** SHALL 直接调用 `await next()` 继续链路，不附加任何风险信息

### Requirement: SafetyMiddleware SHALL resolve check parameter bindings
SafetyMiddleware SHALL 支持两种 `safety_checks` 声明格式：纯字符串 `"url"` 等价于 `{"type": "url", "param": "url"}`，以及显式映射 `{"type": "url", "param": "target_url"}`。检查时从 `params[param_name]` 提取值，而非硬编码 `params["url"]`。

#### Scenario: String safety check uses default param name
- **WHEN** 工具声明 `safety_checks=["command"]` 且 params 包含 `{"command": "ls"}`
- **THEN** SafetyMiddleware SHALL 从 `params["command"]` 提取命令并执行检查

#### Scenario: Mapped safety check uses explicit param name
- **WHEN** 工具声明 `safety_checks=[{"type": "url", "param": "target_url"}]` 且 params 包含 `{"target_url": "https://example.com"}`
- **THEN** SafetyMiddleware SHALL 从 `params["target_url"]` 提取 URL 并执行检查

#### Scenario: Check param not found in params
- **WHEN** 工具声明 `safety_checks=["url"]` 但 params 中不包含 `"url"` 键
- **THEN** SafetyMiddleware SHALL 跳过该检查（视为安全），不报错

### Requirement: MiddlewareContext SHALL support safety_risks field
`MiddlewareContext` dataclass SHALL 新增 `safety_risks: list[SafetyRisk]` 字段，默认为空列表。用于在 SafetyMiddleware 和 PermissionMiddleware 之间传递安全风险信息。

#### Scenario: SafetyMiddleware appends risk to context
- **WHEN** SafetyMiddleware 检测到 `risky` 级别的安全风险
- **THEN** SHALL 创建 `SafetyRisk` 对象并追加到 `context.safety_risks` 列表

#### Scenario: PermissionMiddleware reads risks from context
- **WHEN** PermissionMiddleware 执行权限检查
- **THEN** SHALL 检查 `context.safety_risks` 是否非空，并据此调整权限决策
