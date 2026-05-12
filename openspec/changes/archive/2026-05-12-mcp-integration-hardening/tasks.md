## 1. JSON-RPC 2.0 协议修复

- [x] 1.1 在 `MCPTransport` 中添加原子递增计数器 `_request_id`，每次 `call_tool` 生成唯一 id（字符串类型）
- [x] 1.2 修复 STDIO transport：使用唯一 id 替换硬编码的 `"id": 1`，解析响应时验证 `id` 匹配
- [x] 1.3 修复 HTTP transport：将裸 JSON 请求改为标准 JSON-RPC 2.0 格式（`jsonrpc`/`method`/`params`/`id`）
- [x] 1.4 添加 `MCPError` 异常类（携带 `code` + `message`），在所有 transport 中解析 JSON-RPC 错误响应并抛出 `MCPError`
- [x] 1.5 编写 JSON-RPC 2.0 相关测试：唯一 id 生成、错误响应解析、id 不匹配处理

## 2. Transport 补全

- [x] 2.1 实现 SSE transport：`connect()` 建立 SSE 长连接到 `{url}/sse`，`call_tool()` 通过 HTTP POST 发送 JSON-RPC 请求到 `{url}/messages`，通过 SSE stream 接收响应
- [x] 2.2 实现 SSE 断连重连：指数退避（1s → 2s → 4s，最大 30s），最多 5 次重试
- [x] 2.3 添加 `tools/list` 方法到 `MCPTransport`：发送 JSON-RPC 2.0 请求 `{"method": "tools/list"}`，返回工具列表
- [x] 2.4 编写 SSE transport 测试（使用 mock httpx）

## 3. MCP 配置加载

- [x] 3.1 在 `config.py` 中添加 `MCPConfig` 和 `MCPServerConfig` Pydantic 模型（`servers` 列表、`connect_timeout`、`tool_discovery_timeout`）
- [x] 3.2 在 `AgentConfig` 中添加 `mcp: MCPConfig` 字段（默认空 servers）
- [x] 3.3 在 `config.yaml` 中添加 `mcp` 配置段示例（含 stdio/http/sse 三种 transport 示例）
- [x] 3.4 实现配置校验：stdio transport 必须有 `command`，http/sse transport 必须有 `url`
- [x] 3.5 编写 MCP 配置加载测试：完整配置解析、空配置降级、配置校验错误

## 4. 工具发现与注册

- [x] 4.1 在 `MCPServerManager` 中实现 `_discover_tools(server_id)` 方法：调用 `transport.tools_list()` 获取远程工具列表
- [x] 4.2 实现 Schema 深度转换函数 `_convert_mcp_schema(input_schema)`：递归处理 `$defs`/`definitions`、`anyOf`/`oneOf`、嵌套 `properties`
- [x] 4.3 在 `start_server()` 中调用 `_discover_tools()`，将发现的工具通过 `register_tool_with_schema()` 注册到 `ToolRegistry`
- [x] 4.4 实现工具名冲突检测：注册前检查 `registry.has(name)`，冲突时记录 warning 并跳过
- [x] 4.5 实现健康恢复后重新发现：`health_check()` 恢复 healthy 时触发 `_discover_tools()`
- [x] 4.6 编写工具发现测试：正常发现、空列表、超时、名称冲突、schema 深度转换

## 5. Runtime 生命周期集成

- [x] 5.1 在 `AgentRuntime.__init__()` 中创建 `MCPServerManager` 实例（传入 `tool_registry`）
- [x] 5.2 在 `AgentRuntime.on_start()` 中从配置加载 MCP servers，逐个注册并启动
- [x] 5.3 在 `AgentRuntime.on_stop()` 中调用 `MCPServerManager.stop_server()` 关闭所有 servers
- [x] 5.4 实现并行启动：使用 `asyncio.gather` 并行启动多个 MCP servers，受 `connect_timeout` 控制
- [x] 5.5 确保 `FunctionTool.handler` 正确路由到 `MCPServerManager.call_tool()`，使 ReAct 循环通过 `ToolRegistry.execute()` 无差别调用 MCP 工具
- [x] 5.6 编写 Runtime MCP 集成测试：初始化、启动、工具注册、调用链路、停止清理

## 6. 测试与验收

- [x] 6.1 更新 `tests/test_mcp.py`：覆盖所有新增场景（JSON-RPC 格式、工具发现、配置加载、SSE transport）
- [x] 6.2 运行全量测试确保无回归：`pytest tests/ -v`
- [x] 6.3 验证 MCP 工具与内置工具在 `get_definitions()` 中统一输出 Anthropic `tool_use` 格式
