## ADDED Requirements

### Requirement: ReAct loop SHALL execute all tool_use calls from a single LLM response
When the LLM returns multiple tool_use blocks in a single response, the ReAct loop SHALL execute all of them sequentially and collect all observations before making the next LLM call.

#### Scenario: LLM returns two tool_use calls
- **WHEN** the LLM returns a response with `stop_reason="tool_use"` containing two tool_use blocks (e.g., `read_file` and `list_dir`)
- **THEN** the ReAct loop SHALL execute both tools, build two assistant+user message pairs in `_tool_messages`, and proceed to the next LLM call with both results

#### Scenario: LLM returns one tool_use call
- **WHEN** the LLM returns a response with a single tool_use block
- **THEN** behavior SHALL be identical to the current single-tool execution (backward compatible)

#### Scenario: One of multiple tool calls fails
- **WHEN** the LLM returns two tool_use calls and one fails with a ToolError
- **THEN** the failed tool SHALL produce an error observation, the successful tool SHALL produce a normal observation, and both SHALL be included in the next LLM call
