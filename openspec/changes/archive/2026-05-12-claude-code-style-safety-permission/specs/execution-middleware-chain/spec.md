## MODIFIED Requirements

### Requirement: Tool execution SHALL use a composable middleware chain
The `ToolRegistry.execute()` method SHALL delegate to a middleware chain where each middleware can inspect, modify, or short-circuit the execution. The built-in chain order SHALL be: SafetyMiddleware → PermissionMiddleware → ExecuteMiddleware → TruncateMiddleware. SafetyMiddleware SHALL 仅对 `blocked` 级别的安全风险短路返回错误；对 `risky` 级别 SHALL 将风险信息附加到 `MiddlewareContext.safety_risks` 后继续链路。

#### Scenario: All middlewares pass
- **WHEN** a tool is executed with valid parameters, no safety violations, and no permission blocks
- **THEN** the tool SHALL be executed and the result truncated as configured

#### Scenario: Safety middleware blocks execution (blocked level)
- **WHEN** a tool requires a "command" safety check and the command matches a dangerous pattern with `risk_level="blocked"`
- **THEN** the chain SHALL short-circuit and return an error string without executing the tool or checking permissions

#### Scenario: Safety middleware escalates risk (risky level)
- **WHEN** a tool requires a "command" safety check and the command contains low-risk metacharacters with `risk_level="risky"`
- **THEN** the chain SHALL NOT short-circuit at SafetyMiddleware. SafetyMiddleware SHALL append risk info to `context.safety_risks` and continue to PermissionMiddleware

#### Scenario: Permission middleware blocks execution
- **WHEN** the permission guard returns DENY
- **THEN** the chain SHALL short-circuit and return an error string without executing the tool

### Requirement: Recovery retries SHALL pass through the middleware chain
When a recovery strategy retries a tool execution, it SHALL use the same middleware chain as normal execution, ensuring safety and permission checks are not bypassed.

#### Scenario: Recovery retry is blocked by safety policy
- **WHEN** a tool execution fails and the recovery strategy retries with modified parameters, but the modified parameters violate a safety rule
- **THEN** the retry SHALL be blocked and the recovery SHALL report failure

### Requirement: Middleware SHALL be independently testable
Each middleware SHALL be a standalone class with a `async def process(name, params, context, next)` signature, allowing unit testing without the full chain.

#### Scenario: Testing safety middleware in isolation
- **WHEN** a test creates a SafetyMiddleware with a mock `next` callable and passes a dangerous command
- **THEN** the middleware SHALL return a safety error without calling `next`
