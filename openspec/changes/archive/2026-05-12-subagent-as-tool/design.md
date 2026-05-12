## Context

Open Agent 当前是单代理架构：`AgentRuntime → RoutingPipeline → PlanGenerator → ReActLoop → ToolRegistry`。所有任务在同一个 ReActLoop 中执行，共享同一个 transcript 和工具集。对于复杂场景（并行探索、规划与执行解耦），缺乏子任务委派机制。

本设计采用 Claude Code 验证过的 **Agent-as-a-Tool** 模式：将子代理注册为 `task` 工具，父代理像调用普通工具一样调用子代理，子代理在隔离的上下文中运行并返回摘要结果。

## Goals / Non-Goals

**Goals:**

- 将子代理暴露为可调用的 `task` 工具，父代理通过工具调用语法触发子代理
- 子代理在独立 transcript 中运行，仅通过 prompt 参数接收上下文，返回摘要文本
- 支持并发子代理执行（`run_in_background`），父代理可并行发起多个子任务
- 按角色限制子代理工具集（explore=只读, plan=不执行, general=全量）
- 全局并发控制：限制同时运行的子代理数量和每个父代理的子代理数量
- 级联终止：父代理停止时所有子代理跟随停止
- 与现有中间件链（安全/权限/截断）无缝集成

**Non-Goals:**

- 不实现嵌套层级 > 2 的子代理（子代理不可再 spawn 孙代理）
- 不实现子代理间的共享内存或消息传递
- 不实现可恢复的子代理（resume via agentId），留作后续迭代
- 不实现子代理间的图协调（DAG/Graph 模式）
- 不改变现有的 RoutingPipeline 流程

## Decisions

### D1: SubagentTool 继承 Tool ABC，注册到 ToolRegistry

**选择**: SubagentTool 继承 `Tool` ABC，作为名为 `task` 的工具注册到 `ToolRegistry`。

**替代方案**: 创建独立的 `SubagentRegistry`，不与 ToolRegistry 统一。被否决——这会导致两套发现/执行机制，增加维护复杂度。统一到 ToolRegistry 让子代理自然获得中间件链支持。

**理由**: 复用现有 Tool ABC 和 ToolRegistry 机制。父代理 LLM 看到的工具列表中自然包含 `task` 工具，无需特殊的发现逻辑。中间件链（安全 → 权限 → 截断 → 执行）自动应用于子代理工具调用。

### D2: SubagentManager 管理生命周期和并发

**选择**: 引入独立的 `SubagentManager` 类，负责预设类型注册、并发控制、级联终止。

**替代方案**: 将管理逻辑内联到 SubagentTool.execute() 中。被否决——execute() 应该只关注执行，生命周期管理需要全局视角（跨多个子代理实例的并发计数）。

**理由**: 分离关注点。SubagentTool 只负责"执行一次子代理调用"，SubagentManager 负责"管理所有活跃子代理"。

### D3: 子代理复用 ReActLoop，注入隔离的上下文

**选择**: 子代理执行时创建新的 `ReActLoop` 实例，注入预设的系统提示和限制后的工具集。

**替代方案**: 复用父代理的 ReActLoop 实例，通过参数切换模式。被否决——ReActLoop 内部维护 `_tool_messages` 等状态，共享实例会导致状态污染。

**理由**: ReActLoop 的构造函数已经接受 `tool_registry`、`max_iterations`、`provider` 等参数，天然支持配置化实例化。子代理只需构造一个受限的 ReActLoop 即可。

### D4: 预设类型定义在配置中，不硬编码

**选择**: 子代理预设类型（explore, plan, general）定义在 `SubagentConfig.presets` 中，包含系统提示、允许工具列表、默认迭代上限。

**替代方案**: 在代码中硬编码预设类型。被否决——用户需要能自定义预设，甚至添加新类型。

**理由**: 配置驱动的预设更灵活。默认预设提供开箱即用的体验，用户可通过 `config.yaml` 覆盖或新增。

### D5: 结果返回摘要文本，不返回完整推理链

**选择**: 子代理完成后只返回最终的 `AgentResponse.answer` 作为工具结果字符串。

**替代方案**: 返回完整的步骤详情（JSON）。被否决——这会迅速消耗父代理的上下文窗口，与子代理模式的目的相悖。

**理由**: Claude Code、OpenClaw、Hermes 均采用摘要模式。父代理只需要子代理的结论，不需要其推理过程。

## Risks / Trade-offs

**[上下文丢失]** 子代理仅通过 prompt 参数接收上下文，可能缺少父代理对话中的隐含信息。→ 缓解：父代理在调用时负责序列化足够的上下文到 prompt 中。提示工程可引导 LLM 做好这件事。

**[延迟叠加]** 每个子代理调用至少需要一次 LLM 推理（系统提示 + 工具调用循环），延迟可能显著。→ 缓解：并发执行 + 独立迭代预算限制单次调用时长。

**[Token 消耗倍增]** 多个子代理同时运行会倍增 token 消耗。→ 缓解：全局并发限制 + 每个子代理独立的 `max_tokens` 上限。

**[工具循环风险]** 子代理可能在工具调用中陷入死循环。→ 缓解：继承 ReActLoop 的重复动作检测（3x 相同动作停止）+ 独立 `max_turns` 预算。

**[级联终止竞态]** 父代理在子代理执行中途停止，需要正确取消正在运行的异步任务。→ 缓解：使用 `asyncio.Task.cancel()` + `CancelledError` 处理，SubagentManager 维护活跃任务列表。
