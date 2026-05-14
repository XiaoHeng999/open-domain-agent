## MODIFIED Requirements

### Requirement: All tools degraded SHALL produce explicit failure answer
当所有在当前循环中被调用的工具都已标记为 degraded 时，ReAct 循环 SHALL 在下一个迭代中强制终止，返回结构化失败消息，包含每个失败工具的失败原因摘要。

#### Scenario: All tools degraded triggers early termination
- **WHEN** `web_search` 和 `exec` 都已连续失败 ≥ 3 次被标记为 degraded，且当前迭代 LLM 仍尝试调用这两个工具之一
- **THEN** 循环 SHALL 终止，final_answer SHALL 为结构化失败消息，包含工具名称和最后一条错误原因

## ADDED Requirements

### Requirement: 异常检测 SHALL 主动终止执行
ReAct 循环 SHALL 在每轮迭代末尾检查异常模式。当检测到工具循环（同一工具在同一任务中被调用 ≥ 4 次）或重复错误（同一错误消息出现 ≥ 3 次）时，SHALL 设置 `should_terminate=True`，在下一迭代开始时强制终止循环并返回结构化失败消息。

#### Scenario: 工具循环触发主动终止
- **WHEN** `web_search` 工具在同一任务中已被调用 4 次
- **THEN** ReAct 循环 SHALL 终止，返回结构化失败消息 "Agent terminated: tool loop detected (web_search called 4+ times)"

#### Scenario: 重复错误触发主动终止
- **WHEN** 同一错误消息 "Connection refused" 在执行过程中出现 3 次
- **THEN** ReAct 循环 SHALL 终止，返回结构化失败消息 "Agent terminated: repeated error detected (Connection refused occurred 3+ times)"

#### Scenario: 工具循环次数低于阈值不触发终止
- **WHEN** `web_search` 工具在同一任务中被调用 3 次（低于 4 次阈值）
- **THEN** 循环正常继续执行

#### Scenario: 异常终止消息包含建议
- **WHEN** 异常检测触发主动终止
- **THEN** 失败消息 SHALL 包含建议信息，如 "Consider simplifying the task or checking tool availability"
