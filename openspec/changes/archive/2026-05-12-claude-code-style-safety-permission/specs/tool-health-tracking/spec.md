## ADDED Requirements

### Requirement: ReAct loop SHALL track tool consecutive failure counts
ReAct 循环 SHALL 维护 `tool_failure_counts: dict[str, int]` 字典，跟踪每个工具的连续失败次数。当工具执行成功时 SHALL 将其计数重置为 0。当工具执行失败时 SHALL 递增其计数。

#### Scenario: Tool failure increments count
- **WHEN** `web_search` 工具执行失败（Observation.success=False）
- **THEN** `tool_failure_counts["web_search"]` SHALL 递增 1

#### Scenario: Tool success resets count
- **WHEN** `web_search` 工具之前失败 2 次（count=2），当前执行成功
- **THEN** `tool_failure_counts["web_search"]` SHALL 重置为 0

#### Scenario: First failure sets count to 1
- **WHEN** `exec` 工具首次执行失败
- **THEN** `tool_failure_counts["exec"]` SHALL 为 1

### Requirement: Degraded tools SHALL have warning appended to Observation
当某工具的连续失败次数 ≥ 3 时，该工具 SHALL 被标记为 `degraded`。后续对该工具的 Observation（无论成功或失败）SHALL 在 content 末尾追加提示：`"\n[Warning: Tool '{tool_name}' has been failing repeatedly. Consider using an alternative approach.]"`

#### Scenario: Third consecutive failure triggers degraded warning
- **WHEN** `web_search` 连续第 3 次失败（count=3）
- **THEN** Observation content SHALL 追加 `"[Warning: Tool 'web_search' has been failing repeatedly. Consider using an alternative approach.]"`

#### Scenario: Degraded tool succeeds but still shows warning
- **WHEN** `web_search` 之前连续失败 3 次已被标记为 degraded，当前执行成功
- **THEN** Observation content SHALL 仍然追加 degraded 警告，但计数重置为 0，下次成功不再追加

#### Scenario: Tool recovers after success
- **WHEN** `web_search` 之前连续失败 3 次被标记为 degraded，然后成功执行 1 次
- **THEN** 计数重置为 0，degraded 标记清除，后续执行不再追加警告

### Requirement: All tools degraded SHALL produce explicit failure answer
当所有在当前循环中被调用的工具都已标记为 degraded 时，ReAct 循环 SHALL 在下一个迭代中强制终止，返回结构化失败消息，包含每个失败工具的失败原因摘要。

#### Scenario: All tools degraded triggers early termination
- **WHEN** `web_search` 和 `exec` 都已连续失败 ≥ 3 次被标记为 degraded，且当前迭代 LLM 仍尝试调用这两个工具之一
- **THEN** 循环 SHALL 终止，final_answer SHALL 为结构化失败消息，包含工具名称和最后一条错误原因
