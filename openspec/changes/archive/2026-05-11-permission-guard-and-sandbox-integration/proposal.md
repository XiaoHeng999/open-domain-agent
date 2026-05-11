## Why

当前框架的安全系统存在三个核心缺口：

1. **权限决策层缺失**：`SafetyManager` 只做了"安全检查"（这个命令危不危险），但没有"权限决策"（这个操作允不允许执行）。现有 3 级 `safety_level`（strict/permissive/off）粒度过粗，`permissive` 下所有 WRITE 都自动放行，无法区分"安全的写"和"危险的写"。
2. **HITL 从未接入**：`HITLApprovalManager` 已实现 Read/Write/Dangerous 三层审批，但 `approve_operation()` 在整个执行链路中从未被调用，人机确认形同虚设。
3. **Sandbox 断连**：`SandboxFactory` 支持三种后端（subprocess/docker/daytona），但 `ExecTool` 直接用宿主机 `asyncio.create_subprocess_shell`，sandbox 实例从未参与工具执行。

这三个问题导致 agent 在 ReAct 循环中执行工具时，缺乏逐操作的权限控制和隔离执行能力。

## What Changes

- 新增 `PermissionGuard` 中间件，实现 `deny rules → permission mode → allow rules → ask user` 四级决策管线
- 新增 4 种权限模式：`cautious`（全部问用户）、`conservative`（只允许读）、`fluent`（安全操作自动放行）、`unrestricted`（全部放行）
- 新增 YAML 结构化的 `PermissionConfig`，支持 `deny`/`allow` 规则列表，每条规则包含 `tool` + `pattern`/`path`/`domain` 匹配字段
- 将 `PermissionGuard` 插入 `ToolRegistry.execute()` 的安全检查之后、工具执行之前
- 将 `HITLApprovalManager.approve()` 作为 PermissionGuard 第 4 级（ask user）的执行者，完成接入
- 修改 `ExecTool` 支持依赖注入可选的 sandbox 实例，优先走 sandbox 执行
- 在 `AgentRuntime.on_start()` 中创建 sandbox 并注入到 ExecTool，完成 sandbox 与执行路径的连接
- 更新 `SafetyConfig` 和 `config.yaml`，新增 `permissions` 配置段

## Capabilities

### New Capabilities
- `permission-guard`: 权限决策中间件 — deny/mode/allow/ask 四级管线，4 种权限模式，YAML 规则配置，HITL 用户确认接入
- `sandbox-execution-path`: Sandbox 执行路径接入 — ExecTool 接受可选 sandbox 实例，AgentRuntime 注入，docker/subprocess/daytona 三后端可选

### Modified Capabilities
- `security-sandbox`: 新增 `PermissionGuard` 调用点，HITL `approve_operation()` 从未调用改为在决策管线第 4 级实际调用
- `tool-registry-v2`: `execute()` 方法新增 Stage 3.5 权限检查，`__init__` 新增 `permission_guard` 参数
- `tool-shell`: `ExecTool.__init__` 新增可选 `sandbox` 参数，`execute()` 优先走 sandbox 执行路径

## Impact

- **配置变更**：`config.yaml` 新增 `permissions` 配置段（mode + deny/allow 规则列表）；`SafetyConfig` 扩展或新增 `PermissionConfig` Pydantic 模型
- **执行路径**：`ToolRegistry.execute()` 在 safety checks 和 tool.execute() 之间新增权限检查步骤，所有工具调用额外经过一次 PermissionGuard
- **ReAct 循环**：`react.py` 无需修改 — 所有改动收敛在 ToolRegistry 和 Tool 实例层
- **依赖**：`fnmatch`（标准库）用于规则 glob 匹配，无新增外部依赖
