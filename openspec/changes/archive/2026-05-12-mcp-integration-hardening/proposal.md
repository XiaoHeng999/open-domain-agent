## Why

MCP 集成模块（`mcp_integration.py`）存在框架骨架但实际集成链路断裂：Runtime 未初始化 `MCPServerManager`、工具发现未实现、JSON-RPC 2.0 不完整、HTTP transport 不合规、SSE transport 空实现、配置文件无 MCP 段。当前 MCP 代码无法在运行时被实际使用，需要补全从配置加载 → 服务器启动 → 工具发现 → ReAct 调用的完整链路，并修复 JSON-RPC 2.0 协议合规性。

## What Changes

- **修复 JSON-RPC 2.0 协议实现**：为每次请求生成唯一 `id`（递增计数器），处理标准错误响应格式（`{"error": {"code", "message"}}`），HTTP transport 同样使用 JSON-RPC 2.0 封装
- **实现 MCP 工具发现**：`start_server()` 后自动调用 `tools/list` 发现远程工具，通过 `FunctionTool` 适配器注册到 `ToolRegistry`
- **补全 Transport 实现**：实现 SSE transport（EventSource 连接 + JSON-RPC 2.0 消息），修复 HTTP transport 使其符合 MCP 规范
- **接入 Runtime 生命周期**：在 `AgentRuntime` 中初始化 `MCPServerManager`，从配置加载 MCP servers，`on_start` 时启动所有服务器并发现工具，`on_stop` 时优雅关闭
- **添加 MCP 配置段**：在 `config.yaml` 和 `AgentConfig` 中增加 `mcp` 配置段（servers 列表、transport 参数、超时策略）
- **统一工具调用链路**：确保 MCP 远程工具与内置工具在 `ToolRegistry` 中统一管理，ReAct 循环通过 `registry.execute()` 无差别调用
- **完善 Schema 转换**：增强 MCP `inputSchema` → Anthropic `input_schema` 的嵌套 schema 深度转换

## Capabilities

### New Capabilities
- `mcp-tool-discovery`: MCP 服务器工具发现与自动注册 — 启动 MCP server 后自动调用 `tools/list`，将远程工具通过 `FunctionTool` 适配器注册到 `ToolRegistry`
- `mcp-config`: MCP 配置加载 — 在 `AgentConfig` 和 `config.yaml` 中定义 MCP servers 配置段，支持多 server、多种 transport

### Modified Capabilities
- `mcp-integration`: 补全 JSON-RPC 2.0 协议合规（唯一请求 id、错误响应解析），修复 HTTP transport 规范，实现 SSE transport，接入 Runtime 生命周期
- `tool-registry-v2`: MCP 工具发现后自动注册的集成点，确保远程工具与内置工具在 `get_definitions()` 中统一输出

## Impact

- **核心代码**：`mcp_integration.py`（JSON-RPC 修复、transport 补全、工具发现）、`runtime.py`（MCP 初始化与生命周期）、`config.py` + `config.yaml`（配置段）
- **模型层**：`model.py` 中 `_anthropic_to_openai_tools()` 无需修改（已有正确转换），但 `mcp_integration.py` 中需增强 `inputSchema` → `input_schema` 深度转换
- **测试**：需更新 `tests/test_mcp.py`（工具发现、JSON-RPC 格式、配置加载），新增 SSE transport 测试
- **依赖**：SSE 实现可能需要新增 `httpx-sse` 或类似依赖
- **无 Breaking Change**：所有改动为增量修复和补全，现有内置工具调用链路不受影响
