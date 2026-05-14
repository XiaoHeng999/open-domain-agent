## 1. Tool ABC 输出校验基础设施

- [x] 1.1 在 `Tool` ABC 中新增 `output_schema` 类属性（默认 None）和 `validate_output(result) -> list[str]` 方法（默认返回空列表）
- [x] 1.2 实现 `OutputValidationMiddleware`：对 `ExecuteMiddleware` 的结果依次执行 `output_schema` JSON Schema 校验和 `validate_output()` 语义校验
- [x] 1.3 将 `OutputValidationMiddleware` 插入默认中间件链，顺序为 Safety → Permission → Execute → OutputValidation → Truncate
- [x] 1.4 为 `SearchTool`、`ExecTool`、`FileReadTool`、`WebFetchTool` 补充 `output_schema` 和 `validate_output()` 实现
- [x] 1.5 编写 OutputValidationMiddleware 单元测试：覆盖合规/不合规/无 schema 三种场景

## 2. TOOL_AFTER Hook 阻断能力

- [x] 2.1 扩展 `HookResult` 的 `blocked` 字段文档和语义，使其在 `TOOL_AFTER` 事件中有效
- [x] 2.2 修改 `HookManager.fire()` 中 `TOOL_AFTER` 的执行逻辑，支持 `blocked=True` 中断后续 Hook 并返回阻断信号
- [x] 2.3 修改 ReAct 循环 `_execute_action()`，处理 `TOOL_AFTER` 返回 `blocked=True` 时将 Observation 标记为 `success=False`，content 使用 HookResult.content
- [x] 2.4 确保 `TOOL_AFTER` 阻断后走 `_try_recover()` recovery 路径
- [x] 2.5 编写测试：TOOL_AFTER blocked=True 阻断结果、中断链、触发 recovery

## 3. 子 Agent max_children 深度限制执行

- [x] 3.1 在 `SubagentManager` 中新增 `children_by_parent: dict[str, set]` 映射，跟踪每个父代理的活跃子代理集合
- [x] 3.2 在 `create_subagent()` 中接收 `parent_id` 参数，创建前检查 `len(children_by_parent[parent_id]) >= max_children`，超限时返回结构化错误
- [x] 3.3 子代理完成/失败时从 `children_by_parent` 中移除对应 agent_id
- [x] 3.4 `stop_all()` 中清空整个 `children_by_parent` 字典
- [x] 3.5 修改 `SubagentTool.execute()` 传递当前 agent_id 作为 parent_id
- [x] 3.6 编写测试：max_children 达到上限时拒绝创建、完成后释放配额、stop_all 清理

## 4. 沙箱 auto_timeout 执行

- [x] 4.1 在 `SubprocessSandbox.exec()` 中用 `asyncio.wait_for(coro, timeout=config.auto_timeout)` 包装
- [x] 4.2 在 `DockerSandbox.exec()` 中用 `asyncio.wait_for(coro, timeout=config.auto_timeout)` 包装
- [x] 4.3 在 `DaytonaSandbox.exec()` 中用 `asyncio.wait_for(coro, timeout=config.auto_timeout)` 包装
- [x] 4.4 超时后抛出 `asyncio.TimeoutError`，错误消息包含 "Sandbox execution timed out after {timeout}s"
- [x] 4.5 编写测试：超时触发、正常执行不受影响

## 5. Docker 沙箱 restore 实现

- [x] 5.1 实现 `DockerSandbox.restore(snapshot_id)`：停止当前容器 → 从 snapshot 镜像创建新容器 → 验证可用性
- [x] 5.2 restore 后验证新容器可执行 `echo ok`，返回 True/False
- [x] 5.3 处理 snapshot 不存在的情况，返回 False 并记录错误
- [x] 5.4 确保 restore 后工作目录与 snapshot 时一致
- [x] 5.5 编写测试：成功恢复、snapshot 不存在、恢复后可执行命令

## 6. 异常检测主动终止

- [x] 6.1 在 ReAct 循环中新增 `tool_call_history: list[str]` 和 `error_message_history: list[str]` 跟踪
- [x] 6.2 每轮迭代末尾检查：同工具调用 ≥4 次 或 同错误消息 ≥3 次时设置 `should_terminate=True`
- [x] 6.3 下一迭代开始时检查 `should_terminate`，为 True 时终止循环并返回结构化失败消息
- [x] 6.4 失败消息包含工具名/错误原因和 "Consider simplifying the task or checking tool availability" 建议
- [x] 6.5 编写测试：工具循环终止、重复错误终止、低于阈值不终止
