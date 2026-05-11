## 1. Permission Config 模型

- [x] 1.1 在 `config.py` 中新增 `PermissionMode` 枚举（cautious/conservative/fluent/unrestricted）和 `PermissionRule` Pydantic 模型（tool, pattern?, path?, domain?）
- [x] 1.2 在 `config.py` 中新增 `PermissionConfig` 模型（mode, deny, allow），作为 `AgentConfig` 的子配置 `permissions` 字段
- [x] 1.3 在 `config.yaml` 中新增 `permissions` 配置段，含默认 fluent 模式和示例 deny/allow 规则
- [x] 1.4 在 `_apply_env_overrides()` 中新增 `OPEN_AGENT_PERMISSION_MODE` 环境变量映射

## 2. PermissionGuard 中间件

- [x] 2.1 新建 `src/open_agent/safety/permission.py`，实现 `PermissionGuard` 类，包含 `check(tool_name, params, tool_meta)` 方法
- [x] 2.2 实现 deny rules 匹配：遍历 deny 列表，用 `fnmatch` 匹配 tool + pattern/path/domain
- [x] 2.3 实现 mode check：根据 PermissionMode 决定 read-only 放行、write 拒绝或放行
- [x] 2.4 实现 allow rules 匹配：遍历 allow 列表，同 deny 的匹配逻辑
- [x] 2.5 实现 ask user 级别：调用 `HITLApprovalManager.approve()`，返回用户决策
- [x] 2.6 在 `safety/__init__.py` 中导出 `PermissionGuard`、`PermissionMode`、`PermissionDecision`

## 3. ToolRegistry 接入

- [x] 3.1 修改 `ToolRegistry.__init__()` 新增 `permission_guard` 可选参数
- [x] 3.2 在 `ToolRegistry.execute()` 的 `_run_safety_checks()` 之后、`tool.execute()` 之前插入权限检查阶段
- [x] 3.3 权限拒绝时返回 `"Error: Permission denied: {reason}"` 格式的错误字符串

## 4. ExecTool Sandbox 注入

- [x] 4.1 修改 `ExecTool.__init__()` 新增可选 `sandbox` 参数
- [x] 4.2 修改 `ExecTool.execute()` 判断 sandbox 是否存在，存在则走 `sandbox.exec()`，否则走 `asyncio.create_subprocess_shell`
- [x] 4.3 处理 sandbox 执行结果的格式转换（统一为字符串返回）

## 5. AgentRuntime 集成

- [x] 5.1 修改 `AgentRuntime.__init__()` 创建 `PermissionGuard` 实例（从 `config.permissions` 构建）
- [x] 5.2 修改 `AgentRuntime.on_start()` 中 `ToolRegistry` 创建时注入 `permission_guard`
- [x] 5.3 修改 `AgentRuntime.on_start()` 中 `scan_builtin_tools` 后，替换 `ExecTool` 为带 sandbox 注入的版本
- [x] 5.4 实现 sandbox 启动失败降级逻辑：Docker/Daytona 失败时退回 SubprocessSandbox，记录警告

## 6. 测试

- [x] 6.1 新增 `tests/test_permission.py`，测试 deny/allow 规则匹配、4 种模式决策、HITL ask user 级别
- [x] 6.2 新增 sandbox 注入测试：验证 ExecTool 在有/无 sandbox 时的执行路径
- [x] 6.3 新增集成测试：验证 ToolRegistry 完整管道 safety → permission → execute
- [x] 6.4 验证现有测试（`test_security.py`, `test_react_tool_use.py`）通过，无回归
