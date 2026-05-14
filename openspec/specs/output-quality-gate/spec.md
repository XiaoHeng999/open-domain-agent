## ADDED Requirements

### Requirement: 工具可声明 output_schema
`Tool` ABC SHALL 新增 `output_schema` 类属性，类型为可选的 JSON Schema 字典（默认 None）。当 `output_schema` 不为 None 时，工具执行后 SHALL 自动校验返回值是否符合该 Schema。

#### Scenario: 工具声明 output_schema 并返回合规结果
- **WHEN** 工具声明 `output_schema={"type": "object", "required": ["items"], "properties": {"items": {"type": "array"}}}`，且 execute() 返回 `{"items": [1, 2, 3]}`
- **THEN** 校验通过，工具结果正常返回

#### Scenario: 工具声明 output_schema 但返回值不合规
- **WHEN** 工具声明 `output_schema={"type": "object", "required": ["items"]}`，且 execute() 返回 `{"data": "something"}`
- **THEN** 校验失败，返回错误 `"Error: Output validation failed: missing required field 'items'"`

#### Scenario: 工具未声明 output_schema
- **WHEN** 工具的 output_schema 为 None
- **THEN** 跳过输出校验，工具结果正常返回

### Requirement: 工具可实现 validate_output 做语义校验
`Tool` ABC SHALL 新增 `validate_output(result) -> list[str]` 方法（默认返回空列表）。当 `output_schema` 校验通过后，SHALL 调用 `validate_output(result)` 做语义级检查。返回的错误列表非空时，SHALL 将错误拼接为失败消息。

#### Scenario: 语义校验检测到空结果
- **WHEN** SearchTool 的 `validate_output(result)` 检测到结果列表为空，返回 `["Search returned no results"]`
- **THEN** 工具结果为 `"Error: Output semantic validation failed: Search returned no results"`

#### Scenario: 语义校验通过
- **WHEN** FileWriteTool 的 `validate_output(result)` 检查到文件确实存在，返回空列表
- **THEN** 校验通过，工具结果正常返回

### Requirement: OutputValidationMiddleware 在中间件链中执行输出校验
SHALL 新增 `OutputValidationMiddleware`，位于 `ExecuteMiddleware` 之后、`TruncateMiddleware` 之前。该中间件 SHALL 对工具执行结果依次执行 `output_schema` 校验和 `validate_output()` 语义校验。

#### Scenario: 中间件链顺序
- **WHEN** 默认中间件链构建
- **THEN** 执行顺序为 Safety → Permission → Execute → **OutputValidation** → Truncate

#### Scenario: OutputValidation 拦截不合格输出
- **WHEN** 工具返回值不符合 output_schema
- **THEN** OutputValidationMiddleware 将结果替换为校验错误消息，后续 TruncateMiddleware 正常处理

#### Scenario: OutputValidation 对字符串结果跳过 schema 校验
- **WHEN** 工具 execute() 返回纯字符串（非 dict/object），且声明了 output_schema
- **THEN** 跳过 schema 校验（字符串无法校验 object schema），但仍调用 validate_output

### Requirement: TOOL_AFTER 阻断后触发 recovery
当 `TOOL_AFTER` Hook 返回 `blocked=True` 时，ReAct 循环 SHALL 将该工具结果视为失败（`success=False`），并走 recovery 路径。HookResult.content SHALL 作为失败原因传递给 recovery engine。

#### Scenario: TOOL_AFTER Hook 阻断空结果
- **WHEN** 搜索工具返回空字符串，TOOL_AFTER 的 output-guard Hook 返回 `blocked=True, content="Blocked: empty search result"`
- **THEN** Observation.success 为 False，content 为 "Blocked: empty search result"
- **THEN** ReAct 循环对该工具调用 `_try_recover()` 尝试恢复

#### Scenario: TOOL_AFTER Hook 未阻断
- **WHEN** TOOL_AFTER Hook 返回 `blocked=False`
- **THEN** 工具结果正常返回，success 保持原值
