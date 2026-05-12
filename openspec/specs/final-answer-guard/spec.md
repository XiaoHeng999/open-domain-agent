## ADDED Requirements

### Requirement: _compose_final_answer SHALL detect total failure
`_compose_final_answer` SHALL 在查找成功步骤之前，先检查是否存在任何成功的步骤。如果没有成功的步骤，SHALL 返回结构化失败消息而非 `"Processed: {user_input}"`。

#### Scenario: All steps failed returns structured failure message
- **WHEN** 所有步骤的 Observation.success 均为 False
- **THEN** SHALL 返回包含失败工具列表和错误原因的消息，格式为：`"未能完成任务。以下工具在执行中遇到问题：\n- {tool_name}: {last_error_reason}\n建议检查工具配置或使用替代方案。"`

#### Scenario: Some steps succeeded returns successful content
- **WHEN** 存在至少一个 Observation.success 为 True 的步骤
- **THEN** SHALL 按现有逻辑返回最后一步成功的内容，不触发失败守卫

### Requirement: _compose_final_answer SHALL detect irrelevant success
当唯一成功的步骤与用户意图明显无关时（如用户要求搜索但只有 `ls` 命令成功），`_compose_final_answer` SHALL 返回包含失败信息和附带说明的消息，而非直接返回无关内容。

#### Scenario: Only irrelevant tool succeeded
- **WHEN** 用户请求 "搜索 harnessagent"，但唯一成功的步骤是 `exec` 执行 `ls` 命令
- **THEN** SHALL 返回：`"未能完成搜索任务。搜索工具在执行中遇到问题：{error_summary}。部分操作结果：{ls_output}"`

#### Scenario: Relevant tool succeeded
- **WHEN** 用户请求 "搜索 harnessagent"，`web_search` 成功返回搜索结果
- **THEN** SHALL 返回搜索结果内容，不触发无关性守卫

### Requirement: Failure message SHALL summarize tool errors
失败消息 SHALL 包含每个失败工具的最后一条错误原因，且错误原因 SHALL 截断到 200 字符以内。

#### Scenario: Error summary with truncation
- **WHEN** `web_search` 失败原因为 "URL blocked by safety policy: No hostname in URL"，且超过 200 字符
- **THEN** 失败消息中的错误摘要 SHALL 截断到 200 字符并追加 `"..."`
