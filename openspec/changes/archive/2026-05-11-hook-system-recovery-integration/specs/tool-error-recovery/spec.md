## MODIFIED Requirements

### Requirement: 确定性恢复策略
系统 SHALL 为每种工具错误类型提供确定性的恢复策略链。恢复策略 SHALL 在 ReAct 循环的 `_execute_action()` 方法中自动触发：当 `ToolError` 被捕获时，调用 `execute_recovery_chain()` 进行恢复。若恢复成功，使用恢复结果替代原始错误；若恢复失败，将恢复 trace 摘要附加到错误信息中返回给 LLM。恢复过程对 LLM 透明（LLM 仅看到最终结果）。

#### Scenario: 策略链顺序执行并恢复成功
- **WHEN** 一次工具调用触发 RetrievalError
- **THEN** 系统调用 `execute_recovery_chain()`，按预设策略链依次执行：expand_query → relax_filters → use_cache → report_to_agent，第一个成功的策略结果作为 Observation 的 content 返回

#### Scenario: 策略链耗尽上报
- **WHEN** 所有恢复策略均失败
- **THEN** Observation 的 content 为原始错误信息 + 恢复 trace 摘要（已尝试的策略名和结果），success 为 False，由 LLM 在下一轮决定下一步

#### Scenario: 恢复成功替代原始错误
- **WHEN** ServiceError 触发后 ServiceRecoveryStrategy 重试成功
- **THEN** Observation 的 content 为重试成功的工具结果，success 为 True，不包含任何错误信息

#### Scenario: 非 ToolError 异常不触发恢复
- **WHEN** 工具执行抛出非 ToolError 的通用 Exception
- **THEN** 直接转为 "Execution error: ..." 字符串，不调用恢复链
