## 1. SSRF 防护修复 (P0)

- [x] 1.1 在 `check_url` 中集成 DNS 解析：使用 `socket.getaddrinfo` 解析域名，调用 `check_resolved_ip` 验证所有返回 IP 地址
- [x] 1.2 添加非标准 IP 表示处理：在 URL 解析阶段检测并标准化十进制、十六进制、八进制 IP 格式（正则 + `int()` 转换）
- [x] 1.3 添加 IPv4-mapped IPv6 处理：将 `::ffff:x.x.x.x` 格式提取 IPv4 地址后检查，并将 `::ffff:127.0.0.1` 等加入 `_PRIVATE_NETWORKS`
- [x] 1.4 修复 hostname 匹配：`_BLOCKED_HOSTS` 匹配前 strip trailing dot，添加域名子字符串精确匹配（避免 `evil.com` 匹配 `notevil.com`）
- [x] 1.5 为 SSRF 修复添加单元测试：覆盖 DNS rebinding、非标准 IP、IPv4-mapped、trailing dot 场景

## 2. 沙箱命令注入修复 (P0)

- [x] 2.1 修复 `DockerSandbox.exec()`：使用 `shlex.quote()` 转义 command 参数，替换 f-string 拼接
- [x] 2.2 修复 `DockerSandbox.write_file()`：使用 `shlex.quote()` 转义 path，改用 Python one-liner + stdin pipe 传输 content 替代 heredoc
- [x] 2.3 修复 `SubprocessSandbox`：添加 workspace 路径校验（`Path.resolve()` + `is_relative_to()`），改用 `shlex.split()` + `create_subprocess_exec`
- [x] 2.4 为沙箱修复添加测试：覆盖单引号注入、heredoc 终止符、路径遍历场景

## 3. MCP STDIO 竞态修复 (P0)

- [x] 3.1 为 STDIO 传输添加 `asyncio.Lock` 序列化 stdin 写入
- [x] 3.2 创建 `_pending_requests: dict[str, asyncio.Future]` 映射，请求时注册 Future，响应时按 ID 分发
- [x] 3.3 实现后台 reader task：持续读取 stdout，按响应 ID 设置对应 Future 结果
- [x] 3.4 添加超时清理：请求超时时 cancel Future 并从 _pending_requests 移除
- [x] 3.5 为 MCP 并发修复添加测试：覆盖并发请求、响应错位、超时场景

## 4. 统一错误处理 (P1)

- [x] 4.1 定义 `ToolResult` dataclass（`success: bool`, `content: str`, `error: Exception | None`），实现 `__str__` 返回 content
- [x] 4.2 修改 `ToolRegistry.execute()`：捕获异常并包装为 `ToolResult(success=False)`，透传已有 ToolResult
- [x] 4.3 修改 `ReActLoop._execute_action()`：使用 `result.success` 替代 `content.startswith("Error:")` 判断成败
- [x] 4.4 更新所有工具的 `execute` 方法返回 `ToolResult`（逐步迁移，`str()` 兼容）
- [x] 4.5 重命名 `errors.MemoryError` 为 `AgentMemoryError`，添加兼容别名和 deprecation warning
- [x] 4.6 修复 `retrieval.py` 中 `hash()` 不稳定问题：改用 `hashlib.md5` 或 `hashlib.sha256` 生成 TF-IDF 向量 ID

## 5. 路径遍历修复 (P1)

- [x] 5.1 修改 `tools/filesystem.py` 的路径验证：`Path.resolve()` + `is_relative_to()` 替代 `os.path.abspath` + `startswith`
- [x] 5.2 为路径遍历修复添加测试：覆盖符号链接、相似前缀路径、正常路径场景

## 6. 事件循环阻塞修复 (P1)

- [x] 6.1 修改 `tools/web.py` DuckDuckGo 调用：将 `ddgs.text()` 包裹在 `asyncio.to_thread()` 中
- [x] 6.2 验证 web_search 工具异步行为：确认不阻塞事件循环

## 7. 资源生命周期管理 (P1)

- [x] 7.1 `AgentRuntime` 实现 `__aenter__`/`__aexit__`：`__aenter__` 调用 `on_start()`，`__aexit__` 保证清理
- [x] 7.2 `TraceManager._traces` 添加 LRU 淘汰：限制最大 1000 条 + TTL 1 小时
- [x] 7.3 `SubagentManager._results` 添加大小限制：默认 500 条，FIFO 淘汰
- [x] 7.4 `MCPServerManager` 改用共享 `httpx.AsyncClient`，在 `stop()` 中关闭
- [x] 7.5 `tools/shell.py` 添加 `await proc.wait()` 防僵尸进程

## 8. 并发安全修复 (P1)

- [x] 8.1 `ProfileMemory` 添加 `asyncio.Lock`：保护 SQLite 写入和 read-modify-write 操作
- [x] 8.2 为 ProfileMemory 并发安全添加测试：覆盖并发写入、读写并发场景

## 9. 集成验证

- [x] 9.1 运行全量测试套件确认无回归
- [x] 9.2 手动验证 SSRF 防护：测试 DNS rebinding、非标准 IP 绕过场景
- [x] 9.3 手动验证沙箱安全：测试命令注入、路径遍历场景
