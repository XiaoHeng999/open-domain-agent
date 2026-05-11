## Why

Checkpoint/Resume 底层库（CheckpointManager、CheckpointStorage、ExecutionState）已完整实现并有充分测试，但未接入 ReAct agent 循环和 AgentRuntime。当前 checkpoint manager 在 runtime 启动时被创建后从未被调用，导致：无法在执行中断后恢复、无法利用 idempotency key 避免副作用重复、无法触发失败驱动的记忆强化。需要将已有基础设施接入执行管道，使 checkpoint/resume 真正可用。

## What Changes

- 在 ReActLoop 每轮迭代（thought → action → observation）结束后，根据 interval 配置调用 `CheckpointManager.save_checkpoint()`
- 在 ReActLoop.run() 支持接收恢复状态（ExecutionState），从指定 step 继续执行而非从头开始
- 在 AgentRuntime 上暴露 `resume(checkpoint_id)` 方法，加载 checkpoint 后重建 ReActLoop 状态并继续执行
- 失败恢复后调用 `EpisodicStore.write_after_checkpoint()` 记录失败模式为 avoidance hints
- 在 checkpoint 保存/恢复时创建 `SpanKind.CHECKPOINT` trace span

## Capabilities

### New Capabilities

（无新 capability，所有需求已在 long-horizon-execution spec 中定义）

### Modified Capabilities

- `long-horizon-execution`: 补全 Step-Level Checkpoint、Resume from Checkpoint、失败驱动记忆强制的实际接入代码，当前 spec 仅定义了需求但 ReAct 循环未调用

## Impact

- `src/open_agent/agent/react.py` — ReActLoop.run() 需要新增 checkpoint 保存逻辑和 resume 入口
- `src/open_agent/runtime.py` — AgentRuntime 需要暴露 resume() 方法，连接 CheckpointManager 和 EpisodicStore
- `src/open_agent/checkpoint/manager.py` — 可能需要微调 API 以适配循环上下文（如接受 AgentState）
- `src/open_agent/memory/episodic.py` — write_after_checkpoint() 需要被实际调用
- `src/open_agent/trace.py` — CHECKPOINT span 需要在保存/恢复时创建
- `tests/` — 需要新增 ReAct 循环内 checkpoint 保存和恢复的集成测试
