## ADDED Requirements

### Requirement: Anthropic 原生 tool_use 调用
系统 SHALL 在 ReAct 循环中使用 Anthropic Messages API 的 `tools` 参数和 `tool_use` content block 进行工具调用，废弃 structured JSON 模拟机制。

#### Scenario: 工具定义传入 API
- **WHEN** ReAct 循环调用 LLM
- **THEN** 使用 `client.messages.create(tools=registry.get_definitions(), ...)` 传入工具定义

#### Scenario: LLM 返回 tool_use block
- **WHEN** LLM 响应的 `stop_reason` 为 `"tool_use"` 且包含 `tool_use` content block
- **THEN** ReAct 循环提取 `tool_name` 和 `input`，调用 `registry.execute(tool_name, input)`

#### Scenario: LLM 返回纯文本
- **WHEN** LLM 响应的 `stop_reason` 为 `"end_turn"` 且只包含 `text` content block
- **THEN** ReAct 循环停止，将文本作为最终答案

### Requirement: tool_result 回传机制
系统 SHALL 将工具执行结果通过 `tool_result` content block 回传给 LLM，遵循 Anthropic message format。

#### Scenario: 成功结果回传
- **WHEN** 工具执行成功返回结果字符串
- **THEN** 构造 `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "...", "content": result}]}` 加入消息列表

#### Scenario: 错误结果回传
- **WHEN** 工具执行失败返回错误字符串
- **THEN** 构造 `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "...", "content": error_msg, "is_error": true}]}` 加入消息列表

#### Scenario: 多轮 tool_use 对话
- **WHEN** LLM 连续多次返回 tool_use（调用不同工具）
- **THEN** 每次的 assistant message（含 tool_use block）和 user message（含 tool_result block）都加入消息列表

### Requirement: ModelProvider 接口扩展
系统 SHALL 在 `ModelProvider` ABC 中新增 `complete_with_tools(messages, tool_definitions)` 方法，返回结构化的 `ToolCallResponse`。

#### Scenario: Anthropic provider 实现
- **WHEN** 调用 `AnthropicProvider.complete_with_tools(messages, tools)`
- **THEN** 使用 `client.messages.create(tools=tools, messages=messages)` 调用 API，解析返回的 content blocks

#### Scenario: OpenAI/DeepSeek provider 兼容
- **WHEN** 调用 `OpenAIProvider.complete_with_tools(messages, tools)`
- **THEN** 将 Anthropic 格式 tools 转换为 OpenAI function-calling 格式，调用 API，统一返回 `ToolCallResponse`

### Requirement: ToolCallResponse 数据结构
系统 SHALL 定义 `ToolCallResponse` 数据结构，包含 `text: str`（LLM 文本输出）、`tool_calls: list[ToolCall]`（工具调用列表）、`stop_reason: str`（"tool_use" | "end_turn"）、`raw_response: Any`（原始 API 响应）。

#### Scenario: 纯文本响应
- **WHEN** LLM 未调用任何工具
- **THEN** `ToolCallResponse.text` 包含 LLM 文本，`tool_calls` 为空列表，`stop_reason` 为 `"end_turn"`

#### Scenario: 工具调用响应
- **WHEN** LLM 调用 `read_file` 工具
- **THEN** `ToolCallResponse.tool_calls[0]` 包含 `ToolCall(id="...", name="read_file", input={"path": "..."})`，`stop_reason` 为 `"tool_use"`

#### Scenario: 混合响应
- **WHEN** LLM 同时返回文本和工具调用（Claude 支持多 content block）
- **THEN** `text` 包含文本部分，`tool_calls` 包含工具调用部分

### Requirement: 消息列表构建适配
系统 SHALL 修改 `_build_messages()` 方法，不再在 system prompt 中注入工具定义和 JSON 格式指令。工具定义通过 API 参数传递，消息列表仅包含系统提示、对话历史和 tool_use/tool_result 交互。

#### Scenario: 消息列表不包含工具描述
- **WHEN** 调用 `_build_messages()`
- **THEN** 消息列表包含 system prompt（来自 PromptBuilder）、对话历史、user input、以及之前的 tool_use/tool_result 消息，不包含 `_tool_schema()` 生成的工具描述文本

#### Scenario: 保留 ReAct 步骤追踪
- **WHEN** ReAct 循环执行了多个步骤
- **THEN** 之前的 assistant tool_use 和 user tool_result 消息保留在列表中，LLM 可看到完整交互历史

### Requirement: 废弃 complete_structured 和 _tool_schema
系统 SHALL 废弃 `ModelProvider.complete_structured()` 方法和 `ReActLoop._tool_schema()` 方法。`complete_structured` 保留但标记为 deprecated，`_tool_schema` 直接移除。

#### Scenario: complete_structured deprecated
- **WHEN** 调用 `provider.complete_structured()`
- **THEN** 方法仍可执行但触发 `DeprecationWarning`

#### Scenario: _tool_schema 移除
- **WHEN** 尝试调用 `react_loop._tool_schema()`
- **THEN** 抛出 `AttributeError`
