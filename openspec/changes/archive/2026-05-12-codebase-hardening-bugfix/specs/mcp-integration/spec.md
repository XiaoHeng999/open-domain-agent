## MODIFIED Requirements

### Requirement: MCP Server 生命周期管理
`MCPServerManager.call_tool()` SHALL 通过 `hasattr(entry, "_server_id")` 安全获取 server_id，而非直接访问 `entry.server_id`，因为 `Tool` ABC 基类不定义此属性。MCP Transport 的 stdio 命令解析 SHALL 使用 `shlex.split()` 替代 `str.split()` 以正确处理带引号的参数。HTTP Transport SHALL 复用 httpx.AsyncClient 实例而非每次请求创建新连接。

#### Scenario: 对内置工具调用 call_tool 不崩溃
- **WHEN** `call_tool()` 被调用时传入一个内置 Tool 实例（无 `_server_id` 属性）
- **THEN** SHALL 返回错误信息而非抛出 AttributeError

#### Scenario: stdio 命令包含带空格的路径参数
- **WHEN** MCP server 配置为 `command: 'python "my script.py" --opt "hello world"'`
- **THEN** SHALL 使用 shlex.split() 正确解析为 `["python", "my script.py", "--opt", "hello world"]`

#### Scenario: HTTP transport 复用连接
- **WHEN** 连续调用多次 tools/list 和 tools/call
- **THEN** SHALL 使用同一个 httpx.AsyncClient 实例

### Requirement: JSON-RPC 2.0 协议合规
`MCPTransport._request_counter` SHALL 使用原子递增或 `itertools.count()` 避免并发场景下的请求 ID 冲突。

#### Scenario: 多个 transport 实例并发调用
- **WHEN** 两个 MCPTransport 实例同时调用 `_next_id()`
- **THEN** SHALL 返回不同的请求 ID
