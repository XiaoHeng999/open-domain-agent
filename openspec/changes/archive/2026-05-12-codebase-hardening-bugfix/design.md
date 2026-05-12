## Context

Open Agent 是一个基于 ReAct 模式的 agentic framework，包含 Tool Registry、Safety Pipeline、Recovery Engine、MCP Integration、Memory 等子系统。全量代码审查发现了 4 类崩溃级 bug、3 类安全漏洞和若干架构问题。当前代码在正常路径下基本可工作，但在 LLM 返回多 tool call、MCP 工具调用、recovery 重试等边界路径上会崩溃或绕过安全检查。

当前核心约束：
- ReAct loop (`react.py`) 是执行主循环，通过 native tool_use API 与 LLM 交互
- ToolRegistry (`registry.py`) 承载安全管道（safety → permission → execute → truncate）
- AgentRuntime (`runtime.py`) 是顶层编排器，手动装配 15+ 子系统
- BaseComponent (`base.py`) 是所有组件的基类

## Goals / Non-Goals

**Goals:**
- 修复所有 P0 崩溃级缺陷，确保 agent loop 在所有路径下不会因内部错误崩溃
- 修复 P1 安全和正确性问题，消除安全管道绕过
- 支持多 tool_use 并行执行，与 Claude Code / OpenAI Codex 行为对齐
- 将执行管道重构为 middleware chain，使横切关注点可组合、可测试
- 消除 BaseComponent 共享状态问题

**Non-Goals:**
- 不重构整体目录结构或包布局
- 不添加流式响应支持（独立 change）
- 不实现 MCP 协议的完整 initialize 握手（独立 change）
- 不引入外部 DI 框架
- 不修改 ProviderFactory 的全局注册机制

## Decisions

### Decision 1: BaseComponent 状态改为实例变量

**选择**: 在 `__init__` 中初始化 `_registered` / `_started` 为实例变量

**替代方案**: 使用 dataclass 或 Pydantic model 管理状态 — 过度工程化，当前仅两个 bool 字段

**理由**: 当前类变量导致所有子类实例共享同一状态。改为实例变量是最小改动，保持向后兼容的 API（属性名不变），但创建子类时需确保调用 `super().__init__()`。

### Decision 2: 多 tool_use 执行策略 — 顺序而非真正并行

**选择**: 在 ReAct loop 中顺序执行所有 tool_calls，收集所有 observation 后再进入下一次 LLM 调用

**替代方案**: 使用 `asyncio.gather` 并行执行 — 更高效但增加了安全检查的并发复杂度和错误处理难度

**理由**: 顺序执行保证安全检查和 hook 的执行顺序确定性。并行化可作为后续优化。当前 Claude Code 也是逐个处理 tool_use 并立即构建 tool_result 消息。

**实现**: `_think_and_act` 返回 `list[Action]` 而非单个 `Action`，循环内 for-each 执行。

### Decision 3: Middleware Chain 模式

**选择**: 定义 `ExecutionMiddleware` 协议（`async def process(name, params, context, next)`），内置实现：SafetyMiddleware → PermissionMiddleware → ExecuteMiddleware → TruncateMiddleware

**替代方案**: 保留当前嵌入式管道 — 无法测试、无法扩展

**理由**: middleware chain 是成熟的模式（Express.js, Django middleware），允许：
- 每个中间件独立测试
- RecoveryMiddleware 可在 execute 外层确保重试也经过安全检查
- 未来添加日志/审计中间件无需修改核心代码

### Decision 4: 修复方式 — 最小侵入

**选择**: P0/P1 修复以最小改动为原则，不借机重构周边代码

**理由**: 修复类 change 应保持小范围，降低引入新 bug 的风险。架构改进（P2）作为独立任务，在 P0/P1 修复验证通过后再进行。

### Decision 5: AgentRuntime 拆分策略 — Builder 模式

**选择**: 引入 `RuntimeBuilder` 类封装组件创建和装配逻辑，`AgentRuntime.__init__` 委托给 builder

**替代方案**: 直接拆分 AgentRuntime 为多个小类 — 改动太大，破坏现有 API

**理由**: Builder 模式将 `__init__` 和 `on_start()` 中的 120+ 行装配逻辑提取到独立类，不改变 AgentRuntime 的公共 API。

## Risks / Trade-offs

- **[BaseComponent 改实例变量]** → 部分 subclass 可能没调用 `super().__init__()`，状态可能仍为未初始化。缓解：添加 `__init_subclass__` 检查或文档约束。
- **[多 tool_use 顺序执行]** → 延迟增加，多个独立工具调用无法并行。缓解：后续引入并行执行选项。
- **[Middleware chain]** → 增加了调用栈深度和间接层。缓解：中间件数量有限（4-5 个），性能影响可忽略。
- **[RuntimeBuilder]** → 引入新类但不改变行为，有过渡期。缓解：保持 AgentRuntime 作为 facade。
- **[Recovery 经过安全管道]** → recovery 重试可能被安全策略阻止，降低自动恢复成功率。缓解：这是正确行为——如果安全策略阻止了某个操作，recovery 也不应绕过它。
