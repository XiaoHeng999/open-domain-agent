## 1. ReActLoop Checkpoint 注入

- [x] 1.1 ReActLoop.__init__ 新增 `checkpoint_manager: CheckpointManager | None = None` 参数，存储为 `self._checkpoint_manager`
- [x] 1.2 ReActLoop.run() 循环内，在 `state.add_step(step)` 之后、进入下次迭代前，调用 `self._checkpoint_manager.should_checkpoint(iteration)` 判断是否保存
- [x] 1.3 实现保存逻辑：收集当前 context（steps 摘要）、tool_calls_so_far（从 _tool_messages 提取）、memory_state（从 _runtime_memory 获取快照），调用 `save_checkpoint()`
- [x] 1.4 在保存 checkpoint 时创建 `SpanKind.CHECKPOINT` trace span，记录 step_number 和 checkpoint_id

## 2. ReActLoop Resume 支持

- [x] 2.1 ReActLoop.run() 新增 `resume_state: ExecutionState | None = None` 可选参数
- [x] 2.2 当 resume_state 非空时：跳过前 N 步迭代（for loop 从 resume_state.next_step 开始）
- [x] 2.3 从 resume_state.tool_calls_completed 重建 `_tool_messages`（tool_use/tool_result 消息对）
- [x] 2.4 在 system prompt 中注入 `<resumed_from_step=N>` 标记（通过 _build_messages 或 _domain_system_prompt）

## 3. AgentRuntime Resume 入口

- [x] 3.1 AgentRuntime 新增 `async def resume(self, checkpoint_id: str, user_input: str) -> AgentResponse` 方法
- [x] 3.2 方法内调用 `self.checkpoint_manager.resume_from_checkpoint(checkpoint_id)`，若返回 None 则抛出 AgentError
- [x] 3.3 重建 routing_decision（走 routing_pipeline.route），传入 react_loop.run(..., resume_state=execution_state)
- [x] 3.4 在 AgentRuntime.on_start() 中将 self.checkpoint_manager 传入 self.react_loop（补全已有的创建但未注入）

## 4. 失败驱动记忆强化

- [x] 4.1 AgentRuntime.run() 的 try/except 中捕获 AgentError，若 checkpoint_manager 存在且有已保存的 checkpoint，调用 `_retrieval_memory.write_episodic()` 记录失败模式
- [x] 4.2 记录内容包含：失败步骤、错误类型、使用的工具、失败原因摘要

## 5. 测试

- [x] 5.1 单元测试：ReActLoop 注入 CheckpointManager 后循环内 checkpoint 按间隔保存
- [x] 5.2 单元测试：ReActLoop checkpoint_interval=2 时仅在第 2、4 步保存
- [x] 5.3 单元测试：ReActLoop resume_state 跳过已完成步骤，从 next_step 开始
- [x] 5.4 单元测试：ReActLoop resume_state 重建 _tool_messages
- [x] 5.5 单元测试：AgentRuntime.resume() 正确恢复并继续执行
- [x] 5.6 单元测试：AgentRuntime.resume() checkpoint 不存在时抛出 AgentError
- [x] 5.7 集成测试：checkpoint 保存 → 模拟失败 → resume → 成功完成 → 验证最终结果正确
- [x] 5.8 集成测试：恢复后仍失败时 avoidance hint 被记录到 episodic memory
