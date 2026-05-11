## MODIFIED Requirements

### Requirement: 工具 Schema 强制定义
系统 SHALL 要求每个工具在注册时提供完整的 JSON Schema（参数名、类型、描述、默认值），Schema 与工具实现分离。MCP 远程工具通过 `FunctionTool` 适配器包装为 Tool ABC 实例，适配器内部持有原始 schema。

#### Scenario: Schema 校验
- **WHEN** 注册一个 MCP 远程工具但未提供参数 Schema
- **THEN** 框架拒绝注册并报错

#### Scenario: FunctionTool 适配器包装
- **WHEN** MCP server 发现远程工具 `{"name": "db_query", "parameters": {...}}`
- **THEN** 通过 `FunctionTool` 包装为 Tool 实例，`to_schema()` 输出 Anthropic 格式

### Requirement: MCP Server 生命周期管理
系统 SHALL 支持 MCP Server 的注册、启动、停止、健康检查。Server 工具注册时使用 `FunctionTool` 适配器，schema 格式需与 Tool ABC 的 `to_schema()` 兼容。

#### Scenario: Server 健康检查
- **WHEN** MCP Server 连续 3 次健康检查失败
- **THEN** 框架将其标记为 unhealthy，停止向其路由工具调用，触发告警

#### Scenario: Server 停止时工具清理
- **WHEN** 调用 `MCPServerManager.stop_server(id)`
- **THEN** 通过 `registry.unregister_by_server(id)` 移除所有该 server 的工具

### Requirement: 工具调用标准化
系统 SHALL 通过 MCP 协议统一所有工具调用，调用方无需关心具体实现或 transport。MCP 工具的 schema 输出格式 MUST 与内置工具的 `to_schema()` 格式一致（Anthropic tool_use 格式）。

#### Scenario: 跨 transport 调用
- **WHEN** Agent 需要调用内置 `read_file` 和 MCP 远程 `db_query` 工具
- **THEN** 两者在 `registry.get_definitions()` 中输出相同格式，LLM 统一调用

### Requirement: 工具调用 Trace
系统 SHALL 为每次工具调用生成 trace，包含调用参数、返回结果、耗时、错误信息。Trace 覆盖 `ToolRegistry.execute()` 的完整管道（cast → validate → safety → execute → truncate）。

#### Scenario: 成功调用 trace
- **WHEN** 一次工具调用成功返回
- **THEN** trace 包含 tool_name、input_args、output_result、latency_ms、status="success"、pipeline_stages（含每阶段耗时）

#### Scenario: 校验失败 trace
- **WHEN** `validate_params()` 返回错误
- **THEN** trace 包含 tool_name、input_args、validation_errors、status="validation_failed"

#### Scenario: 安全拦截 trace
- **WHEN** SafetyManager 阻止操作
- **THEN** trace 包含 tool_name、safety_check_type、block_reason、status="safety_blocked"
