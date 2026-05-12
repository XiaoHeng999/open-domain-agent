## Why

全量代码审查发现多个运行时崩溃级缺陷（类型混淆、重复拼接、属性不存在）、安全漏洞（命令注入绕过、pickle 反序列化）和架构问题（单 tool call 限制、recovery 绕过安全管道、God Object）。这些问题影响 agent loop 的正确性、安全性和可维护性，需要在投入更多功能开发前修复。

## What Changes

### P0 — 运行时崩溃修复
- 修复 `runtime.py` 中 `_tool_messages` 类型混淆：dict 元素被当作对象属性访问，导致 `AttributeError` 并掩盖原始异常
- 修复 `react.py` 中 domain system prompt 重复拼接：当 `_domain_system_prompt` 和 `_session_welcome` 同时非空时 prompt 开头重复
- 修复 `base.py` 中 `BaseComponent` 类变量共享 `_registered`/`_started` 状态，导致所有子类实例互相干扰
- 修复 `mcp_integration.py` 中 `entry.server_id` 属性不存在：`Tool` ABC 无此属性，仅 `FunctionTool` 动态添加

### P1 — 功能正确性修复
- 支持多 tool_use 并行执行：当前仅取 `tool_calls[0]`，丢弃其余调用
- 增强命令注入防御：白名单模式可被 `git; rm -rf /` 绕过，需改用 shell 感知的解析
- 修复 Recovery 策略绕过安全管道：recovery 重试直接调用 `tool_handler`，不经 safety/permission 检查
- 使用 `shlex.split()` 替代 `str.split()` 解析 MCP stdio 命令参数

### P2 — 架构改进
- 将 `AgentRuntime` 拆分为子系统 builder，消除 God Object 和 15+ 组件的 `__init__` 手动装配
- 执行管道改为 middleware chain 模式，解耦 safety/permission/truncation 横切关注点
- 引入依赖注入替代直接赋值私有属性（`react_loop._runtime_memory = ...` 等）
- 添加 ReAct loop 全局超时（当前仅有 `max_iterations` 无时间限制）

## Capabilities

### New Capabilities
- `parallel-tool-execution`: 支持 LLM 返回多个 tool_use 时的并行执行能力
- `execution-middleware-chain`: 将 ToolRegistry 执行管道重构为可组合的 middleware chain

### Modified Capabilities
- `tool-registry-v2`: 修复 execute pipeline 中的安全检查集成，确保 recovery 路径也经过完整管道
- `tool-native-calling`: 修复单 tool call 限制，支持多 tool_use 响应
- `mcp-integration`: 修复 server_id 属性访问、命令参数解析、HTTP 连接池复用
- `security-sandbox`: 增强命令注入防御，修复白名单绕过问题
- `permission-guard`: 确保 recovery 重试路径经过 permission 检查
- `tool-error-recovery`: recovery 策略需通过完整的安全管道执行重试
- `runtime-memory`: 修复 BaseComponent 共享状态导致的多实例互相干扰
- `sandbox-execution-path`: 修复 sandbox.on_start() 异步竞态问题

## Impact

- **核心文件**: `react.py`, `runtime.py`, `base.py`, `mcp_integration.py`, `registry.py`, `recovery/strategies.py`, `safety/command.py`
- **架构影响**: `AgentRuntime.__init__` 和 `on_start()` 需要重构组件装配方式
- **向后兼容**: `BaseComponent` 改为实例变量是 **BREAKING** 变更，所有子类可能需要适配
- **测试**: 所有修复都需要对应的测试覆盖，特别是并行 tool execution 和安全管道绕过的回归测试
- **依赖**: 无新外部依赖
