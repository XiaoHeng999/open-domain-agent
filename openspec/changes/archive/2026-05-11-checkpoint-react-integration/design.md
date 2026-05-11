## Context

Checkpoint/Resume 底层库已完整实现（`CheckpointManager`、`CheckpointStorage`、`ExecutionState`），有 JSON 和 SQLite 两种存储后端，并有 337 行单元测试覆盖。但该库完全独立于 agent 执行管道：

- `AgentRuntime.on_start()` 创建了 `CheckpointManager` 实例但 `run()` 中从未调用
- `ReActLoop.run()` 无任何 checkpoint 引用
- `EpisodicStore.write_after_checkpoint()` 未被任何代码路径调用
- `SpanKind.CHECKPOINT` 枚举存在但未使用

当前 ReAct 循环是"无状态"的——一旦中途失败，所有执行进度丢失。

## Goals / Non-Goals

**Goals:**
- ReAct 每轮迭代后根据 interval 配置自动保存 checkpoint
- ReActLoop 支持从 ExecutionState 恢复，跳过已完成步骤
- AgentRuntime 暴露 `resume()` 方法作为外部恢复入口
- 恢复失败后记录 avoidance hints 到记忆系统
- Checkpoint 操作产生 trace span

**Non-Goals:**
- 不改变 CheckpointManager 已有 API（仅扩展调用方）
- 不实现分布式 checkpoint 或跨进程恢复
- 不实现 Redis 等远程存储后端（已有扩展点足够）
- 不实现用户可见的 checkpoint 管理 UI

## Decisions

### D1: Checkpoint 保存点位于每步迭代完成后

**选择**: 在 `state.add_step(step)` 之后、进入下一次迭代之前调用 `should_checkpoint()` + `save_checkpoint()`。

**备选方案**:
- (a) 在 observation 执行后立即保存（每步必保存，由 interval 过滤） — ✅ 选择
- (b) 在 thought 生成后保存（太早，还没执行 action）
- (c) 在循环结束后批量保存（失败时来不及）

**理由**: observation 完成代表一个完整 step 结束，此时状态最完整且一致。

### D2: ReActLoop 通过构造函数参数接收 CheckpointManager

**选择**: 在 `ReActLoop.__init__` 新增 `checkpoint_manager: CheckpointManager | None = None` 参数，循环内部直接调用。

**备选方案**:
- (a) 通过构造函数注入 — ✅ 选择
- (b) 通过 callback/event 通知外部保存 — 增加复杂度，且循环需要知道是否应该保存
- (c) 在 AgentRuntime 层面 hook 进循环 — 循环内部状态不好从外部获取

**理由**: CheckpointManager 是轻量级组件，直接注入最简洁。循环内部拥有 step_number、context、tool_calls 等全部所需信息。

### D3: Resume 通过 ExecutionState 重建 AgentState

**选择**: ReActLoop.run() 新增可选参数 `resume_state: ExecutionState | None = None`。当提供时：
1. 跳过前 N 步（`next_step` 之前的迭代直接跳过）
2. 恢复 `_tool_messages` 从 `tool_calls_completed`
3. 用 `restored_context` 作为上下文起点

**备选方案**:
- (a) 参数注入 resume_state — ✅ 选择
- (b) 从 checkpoint 文件自动检测恢复 — 需要额外的会话标识，增加复杂度
- (c) 新增 `run_from_checkpoint()` 方法 — 与 `run()` 代码高度重复

**理由**: 单一方法加可选参数，代码路径统一，且 `resume_state=None` 保持向后兼容。

### D4: AgentRuntime.resume() 作为外部入口

**选择**: `AgentRuntime` 新增 `async def resume(checkpoint_id: str, user_input: str) -> AgentResponse`，内部流程：
1. `checkpoint_manager.resume_from_checkpoint(checkpoint_id)` 获取 ExecutionState
2. 重建 routing_decision（使用原始 user_input）
3. 调用 `react_loop.run(user_input, routing_decision, trace, resume_state=execution_state)`

**理由**: 外部调用者只需一个 checkpoint_id，不需要理解内部状态重建逻辑。

### D5: 失败恢复记忆强化在 AgentRuntime 层完成

**选择**: 在 `AgentRuntime.run()` 的异常处理中，若 checkpoint 可用且 recovery 也失败，则调用 `EpisodicStore.write_after_checkpoint()` 记录失败模式。

**理由**: AgentRuntime 拥有 `retrieval_memory` 和 `checkpoint_manager` 两个依赖，是唯一能协调两者的组件。

## Risks / Trade-offs

- **[性能开销]** 每步 checkpoint 序列化可能影响循环延迟 → interval 配置默认为 1（每步），但可调大；JSON 序列化很快，只在 interval 命中时触发
- **[状态一致性]** 恢复后的 tool_messages 与 LLM 上下文可能不完全一致 → 恢复时在 system prompt 中注入 `<resumed_from_step=N>` 提示，让 LLM 知道上下文被截断
- **[存储增长]** 长时间运行的 agent 可能产生大量 checkpoint → 由调用方负责 delete_checkpoint 清理；可后续添加 auto-prune 策略
