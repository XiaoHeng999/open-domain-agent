## Why

代码审查（review0513）揭示了 5 个 P0 安全漏洞（SSRF 绕过、沙箱命令注入、MCP STDIO 竞态条件）和 13 个 P1 正确性/资源泄漏问题。这些问题中 SSRF 防护形同虚设、沙箱可直接被逃逸、并发请求会响应错位，属于必须立即修复的生产安全风险。

## What Changes

- **修复 SSRF 防护**：启用 DNS 解析后 IP 检查、处理非标准 IP 表示（十六进制/十进制/八进制/IPv4-mapped IPv6）、末尾加点域名匹配
- **修复沙箱命令注入**：Docker 沙箱参数化 shell 命令、转义单引号；SubprocessSandbox 添加路径校验和命令白名单
- **修复 MCP STDIO 竞态**：添加请求-响应 ID 关联机制，确保并发调用响应不错位
- **修复路径遍历**：`Path.resolve()` + `is_relative_to()` 替代 `abspath` + `startswith`
- **统一错误处理**：工具执行返回结构化 `ToolResult` 而非 `"Error: ..."` 字符串，ReActLoop 使用异常类型判断成败
- **修复资源泄漏**：Runtime 添加 async context manager、无界集合添加清理策略
- **修复并发安全**：DuckDuckGo 同步调用改 `asyncio.to_thread()`、SQLite 添加互斥锁
- **重命名 `MemoryError`** → `AgentMemoryError`，避免遮蔽内置异常

## Capabilities

### New Capabilities

- `unified-error-handling`: 统一错误处理策略——工具执行返回结构化结果，框架使用自定义异常层次，ReActLoop 基于异常类型判断成败
- `resource-lifecycle`: Runtime 及各模块资源生命周期管理——async context manager、无界集合清理策略、临时客户端关闭

### Modified Capabilities

- `security-sandbox`: SSRF 防护修复（DNS rebinding、非标准 IP 表示、IPv4-mapped IPv6）、沙箱命令注入修复（参数化命令、路径校验）
- `tool-filesystem`: 路径遍历防护修复——`Path.resolve()` + `is_relative_to()` 替代当前实现
- `mcp-integration`: STDIO 传输请求-响应关联机制，修复并发竞态条件
- `tool-web`: DuckDuckGo 同步调用改为 `asyncio.to_thread()` 避免阻塞事件循环
- `profile-memory`: SQLite 添加互斥锁保证并发安全

## Impact

- **核心文件**：`safety/ssrf.py`, `sandbox/docker.py`, `sandbox/factory.py`, `mcp_integration.py`, `tools/filesystem.py`, `tools/web.py`, `errors.py`, `runtime.py`, `memory/profile.py`
- **接口变更**：**BREAKING** — `errors.MemoryError` → `errors.AgentMemoryError`；工具执行返回类型从 `str` 变为 `ToolResult`（需更新所有工具和 ReActLoop）
- **依赖**：无新外部依赖
- **风险**：错误处理重构涉及全局改动，需分阶段推进并确保回归测试通过
