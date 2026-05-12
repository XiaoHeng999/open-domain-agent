## ADDED Requirements

### Requirement: MCP 配置段定义
系统 SHALL 在 `config.yaml` 中支持 `mcp` 配置段，包含 servers 列表和全局超时设置，并映射到 `AgentConfig.mcp` 字段。

#### Scenario: 配置加载与解析
- **WHEN** 系统加载 `config.yaml`，其中包含 `mcp` 段
- **THEN** `AgentConfig` 正确解析 `mcp.servers` 列表（每个包含 `server_id`、`transport`、`command`/`url`、`headers`）和 `mcp.connect_timeout`、`mcp.tool_discovery_timeout` 全局设置

#### Scenario: 无 MCP 配置时优雅降级
- **WHEN** `config.yaml` 中不包含 `mcp` 段
- **THEN** `AgentConfig.mcp` 使用默认值（空 servers 列表），`AgentRuntime` 正常启动，不创建 `MCPServerManager`

#### Scenario: 环境变量覆盖
- **WHEN** 设置环境变量 `OPEN_AGENT_MCP_SERVERS` 为 JSON 格式的 server 配置
- **THEN** 环境变量值覆盖 `config.yaml` 中的 `mcp.servers`（遵循现有配置优先级规则）

#### Scenario: Server 配置校验
- **WHEN** 一个 server 配置中 `transport` 为 `stdio` 但缺少 `command` 字段
- **THEN** 系统在启动时抛出 `ValueError`，提示 "stdio transport requires 'command'"

#### Scenario: HTTP transport 配置校验
- **WHEN** 一个 server 配置中 `transport` 为 `http` 或 `sse` 但缺少 `url` 字段
- **THEN** 系统在启动时抛出 `ValueError`，提示 "{transport} transport requires 'url'"
