## Context

当前 MCP 集成模块（`src/open_agent/mcp_integration.py`）存在以下问题：

1. **JSON-RPC 2.0 不完整**：STDIO transport 的请求 `id` 硬编码为 `1`，无法匹配并发响应；HTTP transport 完全不使用 JSON-RPC 2.0 格式
2. **Transport 实现薄弱**：SSE transport 只有 `pass` 空实现；HTTP transport 发送裸 JSON 而非 JSON-RPC
3. **工具发现缺失**：`MCPServerManager.start_server()` 启动服务器后不调用 `tools/list`，远程工具永远不会注册到 `ToolRegistry`
4. **Runtime 未接入**：`AgentRuntime` 不创建 `MCPServerManager`，不加载 MCP 配置，MCP 代码是孤立模块
5. **配置缺失**：`config.yaml` 和 `AgentConfig` 无 MCP 配置段
6. **Schema 转换简陋**：`inputSchema` → `input_schema` 只做 key 名兼容，不处理嵌套差异

现有正确的部分：`ToolRegistry` 统一管理接口、`FunctionTool` 适配器、`AnthropicProvider.complete_with_tools()`、`_anthropic_to_openai_tools()` 转换、`to_schema()` 输出格式。

## Goals / Non-Goals

**Goals:**
- 实现 MCP 协议 JSON-RPC 2.0 的完整合规：唯一请求 id、标准错误响应解析、所有 transport 统一使用 JSON-RPC
- 实现 MCP 工具发现：`start_server()` 后自动 `tools/list`，结果注册到 `ToolRegistry`
- 实现 SSE transport 连接
- 将 `MCPServerManager` 接入 `AgentRuntime` 生命周期（`on_start`/`on_stop`）
- 在 `config.yaml` 和 `AgentConfig` 中增加 MCP 配置段
- 确保 MCP 远程工具与内置工具在 ReAct 循环中统一调用

**Non-Goals:**
- 不实现 MCP Server 端（仅客户端）
- 不实现 MCP resources/prompts 协议（仅 tools）
- 不实现 MCP sampling 协议
- 不修改现有内置工具的执行逻辑
- 不修改 `AnthropicProvider` 或 `OpenAIProvider` 的 tool_use 处理

## Decisions

### Decision 1: JSON-RPC 2.0 请求 ID 管理

**选择**：在 `MCPTransport` 中使用原子递增计数器生成唯一 `id`（字符串类型），每次 `call_tool` 递增。

**备选**：使用 UUID。但 MCP 规范允许整数或字符串 id，递增计数器更简洁、可读，且单进程场景下无需 UUID 的全局唯一性。

**理由**：MCP 规范要求每个 JSON-RPC 请求有唯一 id 以匹配响应。原子计数器在单连接场景下足够，且不引入额外依赖。

### Decision 2: 工具发现时机与策略

**选择**：在 `MCPServerManager.start_server()` 中，连接建立后立即调用 `tools/list`，将发现的工具逐个通过 `register_tool_with_schema()` 注册到 `ToolRegistry`。健康检查恢复后也重新发现工具。

**备选**：延迟发现（首次调用时）。缺点是首次调用延迟高，且 LLM 无法在 `get_definitions()` 中看到这些工具。

**理由**：提前发现让 LLM 在 `get_definitions()` 中看到所有可用工具，确保 ReAct 循环第一次 LLM 调用就有完整工具列表。

### Decision 3: MCP 配置结构

**选择**：在 `config.yaml` 中新增 `mcp` 段，使用 `ServerConfig` 列表：

```yaml
mcp:
  servers:
    - server_id: "db-tools"
      transport: stdio
      command: "python db_mcp_server.py"
    - server_id: "web-tools"
      transport: http
      url: "http://localhost:8080/mcp"
      headers:
        Authorization: "Bearer xxx"
  connect_timeout: 10
  tool_discovery_timeout: 30
```

**理由**：与现有 `config.yaml` 风格一致，直接映射到已有的 `ServerConfig` dataclass。

### Decision 4: SSE Transport 实现

**选择**：使用 `httpx` + 手动 SSE 解析（而非引入 `httpx-sse` 依赖）。SSE 连接用于接收 server-push 通知，工具调用仍通过 HTTP POST + JSON-RPC 2.0。

**理由**：MCP SSE transport 本质是 HTTP POST 发请求 + SSE stream 收响应。用 `httpx` 即可实现，无需额外依赖。

### Decision 5: Schema 深度转换

**选择**：在 `register_tool_with_schema()` 中实现递归 `inputSchema` → `input_schema` 转换，处理 `$defs`/`definitions`、`anyOf`/`oneOf`、嵌套 `properties` 等差异。

**理由**：MCP 规范使用 JSON Schema `inputSchema`，Anthropic 使用 `input_schema`，虽然名称相同但嵌套结构可能有差异（如 `$ref` 解析），需要递归处理。

## Risks / Trade-offs

- **[MCP Server 兼容性]** → 不同 MCP server 实现可能有细微差异（如 `tools/list` 响应格式）。缓解：严格按 MCP 规范解析，对未知字段容忍忽略。
- **[连接稳定性]** → 远程 MCP server 可能断连。缓解：健康检查机制已有，需在 `call_tool` 中增加重连逻辑。
- **[工具名冲突]** → 不同 MCP server 可能提供同名工具。缓解：注册时检测冲突，用 `server_id:tool_name` 格式作为唯一标识，但 `name` 属性保持原始值供 LLM 调用。
- **[启动延迟]** → 启动多个 MCP server 并发现工具可能增加 `on_start` 时间。缓解：并行启动 + 超时控制。
