## ADDED Requirements

### Requirement: ToolRegistry 重构
系统 SHALL 重构 `ToolRegistry`，内部存储从 `dict[str, ToolEntry]` 改为 `dict[str, Tool]`（Tool ABC 实例）。保留 `register(tool: Tool)`、`unregister(name)`、`get(name)`、`has(name)` 接口，新增 `execute(name, params)` 异步执行方法和 `get_definitions()` 批量 schema 导出。

#### Scenario: 注册 Tool 实例
- **WHEN** 调用 `registry.register(ReadFileTool(workspace="/project"))`
- **THEN** 工具以 `tool.name`（`"read_file"`）为 key 存入 registry

#### Scenario: 重复注册拒绝
- **WHEN** 调用 `registry.register(tool)` 但 `tool.name` 已存在
- **THEN** 抛出 `ValueError("Tool already registered: {name}")`

#### Scenario: 异步执行含校验管道
- **WHEN** 调用 `registry.execute("read_file", {"path": "main.py"})`
- **THEN** 执行顺序为：`tool.cast_params(params)` → `tool.validate_params(params)` → `tool.execute(**params)` → 截断结果

#### Scenario: 批量 schema 导出
- **WHEN** 调用 `registry.get_definitions()`
- **THEN** 返回 `[tool.to_schema() for tool in self._tools.values()]`，格式为 Anthropic tool definition 列表

### Requirement: 工具自动发现 scan_builtin_tools
系统 SHALL 提供 `scan_builtin_tools(registry, config)` 函数，自动扫描 `src/open_agent/tools/` 目录下的所有 Tool 子类并注册到 registry。

#### Scenario: 启动时自动注册
- **WHEN** `AgentRuntime.on_start()` 调用 `scan_builtin_tools(registry, config)`
- **THEN** 所有内置工具（read_file、write_file、edit_file、list_dir、exec、web_search、web_fetch、todo）注册到 registry

#### Scenario: 条件注册
- **WHEN** 配置中 `exec_config.enable=False`
- **THEN** `exec` 工具不被注册，LLM 看不到该工具

#### Scenario: 缺少 API Key 的工具降级
- **WHEN** `web_search` 工具需要 Brave Search API key 但未配置
- **THEN** 工具仍被注册，但在 execute 时返回配置错误提示

### Requirement: 工具执行参数校验管道
系统 SHALL 在 `ToolRegistry.execute()` 中实现三阶段管道：cast → validate → execute。

#### Scenario: 校验失败返回错误
- **WHEN** `validate_params()` 返回非空错误列表
- **THEN** 执行中止，返回格式化的校验错误字符串，LLM 可据此修正参数

#### Scenario: 校验通过正常执行
- **WHEN** `validate_params()` 返回空列表
- **THEN** 执行 `await tool.execute(**params)` 并返回结果

### Requirement: 工具结果 Token 截断
系统 SHALL 在 `ToolRegistry.execute()` 返回前根据 `max_tool_result_tokens` 配置截断过长的工具输出。

#### Scenario: 结果超长截断
- **WHEN** 工具返回 50000 字符的文本且 `max_tool_result_tokens=2000`
- **THEN** 结果被截断为约 8000 字符（2000 × 4），追加截断提示

#### Scenario: 结果未超长
- **WHEN** 工具返回 500 字符且 `max_tool_result_tokens=2000`
- **THEN** 结果原样返回，不截断

### Requirement: 工具执行安全检查
系统 SHALL 在 `ToolRegistry.execute()` 中调用 SafetyManager，根据工具声明的安全检查类型执行对应检查。

#### Scenario: ExecTool 命令检查
- **WHEN** 执行 `exec` 工具
- **THEN** `SafetyManager.check_command(command)` 在 cast_params 后、execute 前被调用

#### Scenario: WebTool URL 检查
- **WHEN** 执行 `web_fetch` 工具
- **THEN** `SafetyManager.check_url(url)` 在 execute 前被调用

#### Scenario: FileTool 路径检查
- **WHEN** 执行 `write_file` 工具
- **THEN** `SafetyManager.check_path(path, allow_write=True)` 在 execute 前被调用

### Requirement: MCP 工具兼容适配
系统 SHALL 提供 `FunctionTool` 适配器，将 MCP 注册的函数式工具包装为 Tool ABC 实例，保持 MCP 集成兼容。

#### Scenario: 包装 MCP 远程工具
- **WHEN** MCP server 发现一个远程工具 `{"name": "db_query", "description": "...", "parameters": {...}}`
- **THEN** 通过 `FunctionTool(name, description, parameters, handler)` 包装为 Tool 实例并注册

### Requirement: 保留 snapshot/restore 能力
系统 SHALL 保留 `ToolRegistry.snapshot()` 和 `restore()` 方法，支持工具集的检查点和回滚。

#### Scenario: 快照与回滚
- **WHEN** 调用 `snapshot = registry.snapshot()` 后注册了新工具，再调用 `registry.restore(snapshot)`
- **THEN** 新注册的工具被移除，registry 恢复到快照时状态
