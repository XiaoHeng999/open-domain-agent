## MODIFIED Requirements

### Requirement: Step-Level Checkpoint
系统 SHALL 在 ReAct 循环的每一步保存 checkpoint，包含当前 step number、累积 context、tool call history、memory snapshot。CheckpointManager SHALL 通过 ReActLoop 构造函数注入，在每步 observation 完成后由循环内部调用。

#### Scenario: 每步自动 checkpoint
- **WHEN** ReAct 循环完成一步（thought → action → observation）且 checkpoint_interval=1
- **THEN** 循环调用 `CheckpointManager.save_checkpoint()`，传入 step_number、当前 context、已执行 tool_calls、memory 快照

#### Scenario: Checkpoint 粒度可配置
- **WHEN** 配置 checkpoint_interval=5
- **THEN** 循环仅在 step 5、10、15... 时调用 `save_checkpoint()`，其他步骤跳过

#### Scenario: Checkpoint 未启用
- **WHEN** config.checkpoint.enabled=False 或 checkpoint_manager=None
- **THEN** 循环正常运行，不调用任何 checkpoint 方法

#### Scenario: Checkpoint 保存产生 trace span
- **WHEN** 一个 checkpoint 被保存且 trace 可用
- **THEN** 系统创建一个 `SpanKind.CHECKPOINT` 类型的 span，记录 step_number 和 checkpoint_id

### Requirement: Resume from Checkpoint
系统 SHALL 支持从任意 checkpoint 恢复执行。恢复时 SHALL 跳过已完成步骤，从 next_step 开始继续循环。AgentRuntime SHALL 暴露 `resume(checkpoint_id, user_input)` 方法作为外部恢复入口。

#### Scenario: 失败后恢复
- **WHEN** 任务在第 7 步失败，checkpoint 存在于第 5 步，调用者调用 `runtime.resume(checkpoint_id, original_input)`
- **THEN** AgentRuntime 通过 CheckpointManager 获取 ExecutionState，传入 ReActLoop.run(resume_state=...)，循环从第 6 步开始执行

#### Scenario: 恢复后重建 tool messages
- **WHEN** 从 checkpoint 恢复且 ExecutionState 包含 tool_calls_completed
- **THEN** 循环将已完成的 tool_use/tool_result 消息对注入 `_tool_messages`，使后续 LLM 调用具备历史上下文

#### Scenario: 恢复后系统提示注入
- **WHEN** 循环从 checkpoint 恢复执行
- **THEN** 系统在 system prompt 中注入 `<resumed_from_step=N>` 标记，告知 LLM 当前是恢复执行

#### Scenario: 恢复后 idempotent
- **WHEN** 从 checkpoint 恢复后重新执行某步
- **THEN** 若该步有副作用（如发送消息），系统通过 idempotency key 确保不重复执行

#### Scenario: Checkpoint 不存在
- **WHEN** 调用 `runtime.resume()` 时 checkpoint_id 不存在
- **THEN** 系统抛出 `AgentError` 并给出明确的 "checkpoint not found" 错误信息

### Requirement: 失败驱动记忆强化
系统 SHALL 在 checkpoint 恢复后且任务仍失败时，记录失败模式到 episodic memory，形成 avoidance hints。

#### Scenario: 恢复后仍失败触发记忆记录
- **WHEN** 任务因工具调用超时失败，从 checkpoint 恢复后再次失败
- **THEN** AgentRuntime 调用 `EpisodicStore.write_after_checkpoint()`，记录包含 "该工具在此类任务上可能超时" 的 hint，后续执行时 retrieval_memory 可检索到该 hint

#### Scenario: 恢复后成功不记录失败
- **WHEN** 任务失败后从 checkpoint 恢复，且恢复后执行成功
- **THEN** 系统不记录 avoidance hint（失败已自愈）
