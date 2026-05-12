## MODIFIED Requirements

### Requirement: Anthropic 原生 tool_use 调用
ReAct loop 的 `_think_and_act` 方法 SHALL 处理 LLM 返回的所有 tool_use 调用（而非仅第一个），返回 `list[Action]` 而非单个 `Action`。循环内 SHALL 对每个 Action 生成对应的 Observation，并在 `_tool_messages` 中构建完整的 tool_use/tool_result 消息对。

#### Scenario: LLM 返回两个并行 tool_use
- **WHEN** LLM 返回包含两个 tool_use block 的响应
- **THEN** SHALL 返回包含两个 Action 的列表，每个 Action 依次执行并生成 Observation

#### Scenario: LLM 返回零个 tool_use（纯文本回复）
- **WHEN** LLM 返回 `stop_reason="end_turn"` 且无 tool_use block
- **THEN** SHALL 返回空 tool_calls 列表，action 为空 tool_name 直接回答

### Requirement: tool_result 回传机制
`_tool_messages` SHALL 为每个 tool_use 构建独立的消息对（assistant tool_use + user tool_result），多个 tool call 的消息对 SHALL 按执行顺序追加。

#### Scenario: 两个 tool call 的消息历史
- **WHEN** LLM 返回 read_file 和 list_dir 两个 tool_use
- **THEN** `_tool_messages` SHALL 包含 4 条消息：assistant(read_file) → user(read_file result) → assistant(list_dir) → user(list_dir result)

### Requirement: 消息列表构建适配
`_build_messages` SHALL 正确构建 system prompt，不重复拼接 domain system prompt。当 `_domain_system_prompt` 和 `_session_welcome` 同时存在时，domain prompt SHALL 仅出现一次。

#### Scenario: domain 和 session_welcome 同时存在
- **WHEN** routing_decision 设置了 domain.system_prompt 且 hook 产生了 session_welcome
- **THEN** 最终 system_content 中 domain system_prompt SHALL 仅在最前面出现一次，session_welcome SHALL 在末尾出现一次
