## ADDED Requirements

### Requirement: Tool 抽象基类
系统 SHALL 定义 `Tool` 抽象基类，所有内置工具 MUST 继承此类。基类定义以下抽象接口：`name: str`（工具标识符）、`description: str`（工具描述）、`parameters: dict`（JSON Schema 格式的参数定义）。提供具体方法：`to_schema()`（输出 Anthropic tool_use 格式）、`cast_params(params)`（类型强转）、`validate_params(params)`（JSON Schema 校验）。

#### Scenario: 具体工具实现
- **WHEN** 开发者创建 `class ReadFileTool(Tool)` 并实现 `name`、`description`、`parameters`、`execute()`
- **THEN** 工具可通过 `to_schema()` 输出合法的 Anthropic tool definition 格式

#### Scenario: 缺少抽象方法
- **WHEN** 开发者创建 Tool 子类但未实现 `execute()` 方法
- **THEN** Python 在实例化时抛出 `TypeError`（ABC 强制）

### Requirement: 参数类型强转 cast_params
系统 SHALL 在执行工具前对 LLM 产出的参数进行类型强转，处理常见 LLM 输出怪癖：string→int（"10" → 10）、string→bool（"true"/"1"/"yes" → True）、null→空字符串。

#### Scenario: 字符串转整数
- **WHEN** LLM 产出 `{"limit": "10"}` 但 schema 定义 `limit` 为 `integer`
- **THEN** `cast_params()` 将 `"10"` 转为 `10`，执行不报错

#### Scenario: 字符串转布尔值
- **WHEN** LLM 产出 `{"force": "true"}` 但 schema 定义 `force` 为 `boolean`
- **THEN** `cast_params()` 将 `"true"` 转为 `True`

#### Scenario: 嵌套对象类型强转
- **WHEN** LLM 产出 `{"config": {"retries": "3"}}` 且 schema 定义嵌套对象的 `retries` 为 `integer`
- **THEN** `cast_params()` 递归强转为 `{"config": {"retries": 3}}`

### Requirement: 参数 JSON Schema 校验 validate_params
系统 SHALL 在 cast_params 之后、execute 之前对参数执行 JSON Schema 校验，返回错误列表。支持：type 检查、enum 约束、required 字段、minimum/maximum、minLength/maxLength、minItems/maxItems、嵌套对象/数组。

#### Scenario: 缺少必填字段
- **WHEN** LLM 产出 `{"path": "file.txt"}` 但 schema 定义 `content` 为 required
- **THEN** `validate_params()` 返回 `["Missing required field: content"]`

#### Scenario: 枚举值校验
- **WHEN** LLM 产出 `{"status": "unknown"}` 但 schema 定义 `status` enum 为 `["pending", "in_progress", "completed"]`
- **THEN** `validate_params()` 返回包含枚举不匹配的错误

#### Scenario: 校验通过
- **WHEN** LLM 产出 `{"path": "/workspace/file.txt"}` 且 schema 定义 `path` 为 string + required
- **THEN** `validate_params()` 返回空列表 `[]`

### Requirement: to_schema 输出 Anthropic 格式
系统 SHALL 通过 `to_schema()` 方法将工具定义转换为 Anthropic `tool_use` API 所需格式：`{"name": str, "description": str, "input_schema": dict}`。

#### Scenario: 格式输出
- **WHEN** 调用 `ReadFileTool().to_schema()`
- **THEN** 返回 `{"name": "read_file", "description": "...", "input_schema": {"type": "object", "properties": {...}, "required": [...]}}`

#### Scenario: 全部工具导出
- **WHEN** 调用 `ToolRegistry.get_definitions()`
- **THEN** 返回所有已注册工具的 `to_schema()` 输出列表，可直接传入 Anthropic API 的 `tools` 参数

### Requirement: read_only 属性
系统 SHALL 为每个 Tool 提供 `read_only: bool` 属性（默认 False），标识工具是否无副作用。read-only 工具可被安全地并行调用（为未来优化预留）。

#### Scenario: 文件读取标记为 read_only
- **WHEN** `ReadFileTool` 实例化
- **THEN** `tool.read_only` 返回 `True`

#### Scenario: 文件写入标记为非 read_only
- **WHEN** `WriteFileTool` 实例化
- **THEN** `tool.read_only` 返回 `False`

### Requirement: 工具异步执行
系统 SHALL 要求所有 Tool 的 `execute()` 方法为 `async def`，ToolRegistry 调用时使用 `await`。

#### Scenario: 异步工具执行
- **WHEN** `ToolRegistry.execute("read_file", {"path": "file.txt"})` 被调用
- **THEN** 执行通过 `await tool.execute(**params)` 完成

#### Scenario: 同步工具兼容
- **WHEN** 工具的 `execute()` 实际上是同步方法（未用 async）
- **THEN** `ToolRegistry.execute()` 检测到协程未被 await，自动包装为可等待对象
