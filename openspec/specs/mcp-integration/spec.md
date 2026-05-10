## ADDED Requirements

### Requirement: Python MCP SDK 集成
系统 SHALL 使用 Python 版 MCP 包（`mcp`）实现工具协议，支持 SSE、HTTP、stdio 三种 transport。

#### Scenario: 多 transport 注册
- **WHEN** 通过 SSE transport 注册远程工具服务，同时通过 stdio transport 注册本地工具进程
- **THEN** 框架统一管理两种 Server，Agent 调用工具时无需关心 transport 差异

#### Scenario: Transport 自动选择
- **WHEN** 工具配置中指定 transport 类型为 "sse" 并提供 URL
- **THEN** 框架使用 SSE transport 连接，自动处理连接、心跳、重连

### Requirement: 工具 Schema 强制定义
系统 SHALL 要求每个工具在注册时提供完整的 JSON Schema（参数名、类型、描述、默认值），Schema 与工具实现分离。

#### Scenario: Schema 校验
- **WHEN** 注册一个工具但未提供参数 Schema
- **THEN** 框架拒绝注册并报错，提示缺少 schema 定义

#### Scenario: Schema 自动推导
- **WHEN** 开发者注册一个带有类型注解和 docstring 的 Python 函数
- **THEN** 框架自动生成符合 MCP 规范的 JSON Schema，参数名和类型与函数签名一致

### Requirement: MCP Server 生命周期管理
系统 SHALL 支持 MCP Server 的注册、启动、停止、健康检查。

#### Scenario: Server 健康检查
- **WHEN** MCP Server 连续 3 次健康检查失败
- **THEN** 框架将其标记为 unhealthy，停止向其路由工具调用，触发告警

### Requirement: Sandbox 执行环境
系统 SHALL 支持在 sandbox 中执行工具调用，限制文件系统访问、网络访问和资源消耗。

#### Sandbox 严格模式执行
- **WHEN** 工具在 strict sandbox 模式下执行
- **THEN** 工具只能访问指定的工作目录，网络访问受白名单限制，执行超时自动终止

#### Scenario: Sandbox 模式配置
- **WHEN** 配置中设置 sandbox_mode="permissive"
- **THEN** 工具执行放宽限制，允许更广泛的资源访问

### Requirement: 工具调用标准化
系统 SHALL 通过 MCP 协议统一所有工具调用，调用方无需关心具体实现或 transport。

#### Scenario: 跨 transport 调用
- **WHEN** Agent 需要调用分布在不同 MCP Server 上的两个工具（一个 stdio、一个 SSE）
- **THEN** Agent 使用统一调用接口，框架自动处理 transport 差异

### Requirement: 工具调用 Trace
系统 SHALL 为每次工具调用生成 trace，包含调用参数、返回结果、耗时、错误信息。

#### Scenario: 成功调用 trace
- **WHEN** 一次工具调用成功返回
- **THEN** trace 包含 tool_name、input_args、output_result、latency_ms、status="success"

#### Scenario: 失败调用 trace
- **WHEN** 一次工具调用抛出异常
- **THEN** trace 包含 tool_name、input_args、error_type、error_message、latency_ms、status="error"
