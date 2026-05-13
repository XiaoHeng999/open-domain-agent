## ADDED Requirements

### Requirement: AgentRuntime async context manager
`AgentRuntime` SHALL 实现 `__aenter__` 和 `__aexit__` 方法。`__aenter__` SHALL 调用 `on_start()`，`__aexit__` SHALL 调用 `on_stop()` 并保证即使 `on_start()` 中途失败也清理已创建的资源。

#### Scenario: Normal lifecycle via context manager
- **WHEN** 使用 `async with AgentRuntime(config) as rt:` 创建运行时
- **THEN** 进入时自动调用 on_start()，退出时自动调用 on_stop()

#### Scenario: on_start failure cleans up partial resources
- **WHEN** on_start() 在创建 MCP 连接后失败
- **THEN** __aexit__ 仍被调用，已创建的 provider、内存层、已连接的 MCP 服务器被正确关闭

### Requirement: Bounded trace storage
`TraceManager._traces` SHALL 限制最大存储条目数。当条目数超过阈值（默认 1000）时，SHALL 按 LRU 策略淘汰最旧条目。SHALL 支持配置最大条目数和 TTL。

#### Scenario: Trace storage reaches limit
- **WHEN** _traces 中存储了 1000 条 trace 并新增第 1001 条
- **THEN** 最旧的 trace 被移除，总数保持 1000

#### Scenario: Trace expires by TTL
- **WHEN** 某条 trace 的创建时间超过配置的 TTL（默认 1 小时）
- **THEN** 该 trace 在下次访问检查时被清理

### Requirement: Bounded subagent results storage
`SubagentManager._results` SHALL 限制最大存储条目数（默认 500）。超过阈值时 SHALL 淘汰最早完成的结果。

#### Scenario: Results storage reaches limit
- **WHEN** _results 中存储了 500 条结果并新增第 501 条
- **THEN** 最早完成的结果被移除

### Requirement: MCP httpx client lifecycle
`MCPServerManager` SHALL 在初始化时创建单个 `httpx.AsyncClient` 实例并在所有 SSE 传输间共享。SHALL 在 `stop()` 方法中关闭该 client。

#### Scenario: Shared client across SSE connections
- **WHEN** 多个 MCP 服务器使用 SSE 传输
- **THEN** 所有连接共享同一个 httpx.AsyncClient 实例

#### Scenario: Client closed on shutdown
- **WHEN** MCPServerManager.stop() 被调用
- **THEN** 共享的 httpx.AsyncClient 被 aclose() 关闭

### Requirement: Shell process cleanup
`tools/shell.py` 在调用 `proc.kill()` 后 SHALL 调用 `await proc.wait()` 防止僵尸进程。

#### Scenario: Process killed and reaped
- **WHEN** shell 工具因超时调用 proc.kill()
- **THEN** 随后 await proc.wait() 被调用，进程资源被释放
