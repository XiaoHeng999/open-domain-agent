## ADDED Requirements

### Requirement: ToolResult structured return type
工具执行 SHALL 返回 `ToolResult` dataclass 而非裸字符串。`ToolResult` SHALL 包含 `success: bool`、`content: str`、`error: Exception | None` 三个字段。`ToolResult.__str__()` SHALL 返回 `content` 字段值以兼容现有 `str(result)` 用法。

#### Scenario: Tool executes successfully
- **WHEN** 工具正常执行并返回结果
- **THEN** ToolResult.success 为 True，content 包含结果文本，error 为 None

#### Scenario: Tool raises exception
- **WHEN** 工具执行过程中抛出异常
- **THEN** ToolResult.success 为 False，content 包含用户可读错误信息，error 保留原始异常对象

#### Scenario: Backward compatibility with str()
- **WHEN** 调用方使用 `str(result)` 获取工具结果文本
- **THEN** 返回 ToolResult.content 的值，与现有行为一致

### Requirement: Registry wraps exceptions into ToolResult
`ToolRegistry.execute()` SHALL 捕获工具执行过程中的所有异常，将其包装为 `ToolResult(success=False, content=f"Error: {exc}", error=exc)`。SHALL 不再向调用方传播裸异常。

#### Scenario: Registry catches tool exception
- **WHEN** 工具执行抛出 ValueError
- **THEN** Registry 返回 ToolResult(success=False)，error 字段包含原始 ValueError

#### Scenario: Registry preserves tool ToolResult
- **WHEN** 工具已返回 ToolResult
- **THEN** Registry 直接透传该 ToolResult，不做二次包装

### Requirement: ReActLoop uses ToolResult.success for judgment
`ReActLoop._execute_action()` SHALL 使用 `result.success` 判断工具执行成败，而非 `content.startswith("Error:")` 字符串匹配。

#### Scenario: Tool reports failure via ToolResult
- **WHEN** 工具返回 ToolResult(success=False)
- **THEN** ReActLoop 将该 action 标记为失败，触发退化检测

#### Scenario: Tool returns content starting with "Error:"
- **WHEN** 工具返回 ToolResult(success=True) 但 content 以 "Error:" 开头
- **THEN** ReActLoop 将该 action 标记为成功（这是合法的工具输出）

### Requirement: Rename MemoryError to AgentMemoryError
`errors.py` 中的 `MemoryError` SHALL 重命名为 `AgentMemoryError`。SHALL 保留 `MemoryError = AgentMemoryError` 兼容别名并标记为 deprecated。

#### Scenario: New code uses AgentMemoryError
- **WHEN** 代码 `from open_agent.errors import AgentMemoryError` 并抛出该异常
- **THEN** 异常类型正确，不影响 Python 内置 MemoryError 的捕获

#### Scenario: Legacy code uses MemoryError alias
- **WHEN** 代码 `from open_agent.errors import MemoryError` 并使用该异常
- **THEN** 行为与 AgentMemoryError 一致，但触发 DeprecationWarning
