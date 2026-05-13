## Context

代码审查发现 5 个 P0 安全漏洞和 13 个 P1 问题。当前代码存在以下系统性缺陷：

- SSRF 防护的 DNS 解析检查被跳过（`check_resolved_ip` 未被调用）
- Docker 沙箱使用 f-string 拼接 shell 命令，存在命令注入
- MCP STDIO 传输无请求-响应关联，并发调用会响应错位
- 全局错误处理使用 `f"Error: {exc}"` 字符串模式，自定义异常层次形同虚设
- 多处资源泄漏（无界字典、未关闭客户端、未等待子进程）

涉及 ~15 个核心文件的修改，需要分阶段推进。

## Goals / Non-Goals

**Goals:**

- 修复全部 P0 安全漏洞（SSRF 绕过、命令注入、MCP 竞态）
- 修复 P1 正确性问题（hash 不稳定、路径遍历、事件循环阻塞）
- 建立统一错误处理策略（结构化 ToolResult）
- 修复关键资源泄漏
- 保证现有测试通过

**Non-Goals:**

- P2/P3 问题（封装改进、死代码清理、CLI 统一）留待后续变更
- 不重构 ReActLoop 核心循环逻辑（退化检测、重复动作检测）
- 不改变 Memory 系统架构（WorkingMemory / RuntimeMemory 并存）
- 不引入新外部依赖

## Decisions

### Decision 1: SSRF 防护 — 使用 socket.getaddrinfo + ipaddress 双层检查

**选择**：在 `check_url` 中同步执行 `socket.getaddrinfo` 解析 DNS，然后调用 `check_resolved_ip` 验证所有返回地址。同时在 URL 解析阶段使用 `ipaddress.ip_address` + 正则表达式处理非标准 IP 表示。

**替代方案**：
- 使用 `aiodns` 异步解析 — 增加外部依赖，且 `check_url` 当前是同步方法
- 仅依赖 URL 字符串检查 — 无法防御 DNS rebinding

**理由**：`socket.getaddrinfo` 是标准库，无需新依赖。对于 async 调用路径，调用方在 `await` 前调用同步 `check_url`，性能影响可接受。

### Decision 2: 沙箱命令注入 — 使用 shlex.quote 转义

**选择**：Docker 沙箱的 `exec` 和 `write_file` 使用 `shlex.quote()` 转义命令参数，而非 f-string 拼接。`write_file` 改用 Python 脚本通过 stdin pipe 传入文件内容。

**替代方案**：
- 使用 Docker SDK 的 `exec_run` 的 `stdin=True` + pipe — API 更复杂但更安全
- Base64 编码传输 — 增加编解码复杂度

**理由**：`shlex.quote` 是标准库提供的 shell 转义方案，简单可靠。对于 `write_file`，使用 Python one-liner 从 stdin 读取内容避免 heredoc 终止符问题。

### Decision 3: MCP STDIO 竞态 — asyncio.Lock + 请求 ID 映射

**选择**：添加 `asyncio.Lock` 序列化 STDIO 读写操作，使用 `_pending_requests: dict[str, asyncio.Future]` 映射请求 ID 到 Future 对象。读取循环在独立 task 中运行，根据响应 ID 将结果设置到对应 Future。

**替代方案**：
- 每个请求创建独立子进程 — 资源开销大，不符合 MCP 协议设计
- 使用消息队列 + 单消费者 — 等效于 Lock 方案但更复杂

**理由**：Lock + Future 映射是标准的 asyncio 请求-响应关联模式，实现简单，性能足够。

### Decision 4: 统一错误处理 — ToolResult dataclass + 异常传播

**选择**：定义 `ToolResult` dataclass（`success: bool`, `content: str`, `error: Exception | None`），工具执行返回 `ToolResult`。Registry 的 `execute` 方法捕获异常并包装为 `ToolResult(success=False, ...)`。ReActLoop 基于 `result.success` 判断成败。

**替代方案**：
- 直接使用异常传播（raise 而非 return）— 需要大规模重构调用链
- 使用 Result monad — 过度工程化

**理由**：`ToolResult` dataclass 兼容现有 `str(result)` 使用模式（通过 `__str__` 方法），迁移成本低。同时保留异常信息用于监控和日志。

### Decision 5: 资源管理 — TTL 缓存 + async context manager

**选择**：
- `TraceManager._traces`、`SubagentManager._results`、`CheckpointManager._seen_keys` 添加 TTL 清理（默认保留最近 1000 条或 1 小时）
- `AgentRuntime` 实现 `__aenter__`/`__aexit__`，`__aexit__` 调用 `on_stop`
- 临时 `httpx.AsyncClient` 改为长连接，随 MCPServerManager 生命周期关闭

**替代方案**：
- 使用 `weakref.WeakValueDictionary` — 不适合这类 key-value 缓存场景
- 完全重构为依赖注入 — 超出本次范围

### Decision 6: MemoryError 重命名

**选择**：将 `errors.MemoryError` 重命名为 `errors.AgentMemoryError`，添加 `MemoryError = AgentMemoryError` 兼容别名（标记 deprecated）。

**理由**：直接改名最小化破坏性，兼容别名给下游用户迁移时间。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| SSRF 中 DNS 解析增加延迟（~50ms/请求） | 仅在 URL 含域名时执行，IP 直连无开销 |
| 统一错误处理涉及全局改动，可能引入回归 | 分阶段迁移：先定义 ToolResult → 更新 Registry → 更新 ReActLoop |
| MCP STDIO Lock 降低并发吞吐 | STDIO 传输本身是单进程单连接，Lock 不改变实际并发度 |
| Docker shlex.quote 对复杂命令可能过度转义 | 保留原始 command 语义，仅转义 shell 层面的特殊字符 |
| TTL 清理可能丢失有用数据 | 可配置 TTL 和最大条目数，默认值保守（1000 条 / 1 小时） |
