## ADDED Requirements

### Requirement: Todo Tool 定义与注册
系统 SHALL 在 ToolRegistry 中注册一个名为 `todo` 的工具，允许 LLM 通过标准的 tool call 机制管理当前 session 的多步任务计划。工具 schema 包含 items 数组，每项含 content（string）、status（pending|in_progress|completed）、activeForm（可选 string）。

#### Scenario: 工具注册
- **WHEN** AgentRuntime 初始化
- **THEN** `todo` 工具注册到 ToolRegistry，schema 包含 `items` 参数（array of objects），LLM 可在 `_tool_schema()` 中看到该工具

#### Scenario: 工具调用
- **WHEN** LLM 在 ReAct 循环中决定更新任务计划
- **THEN** LLM 返回 `tool_name: "todo"`, `args: {"items": [...]}`，ReActLoop 通过 `_execute_action()` 调用 todo tool handler

### Requirement: TodoManager 整份重写模式
系统 SHALL 采用整份重写模式管理计划——每次调用 todo tool 时，LLM 传入完整的 items 列表替换当前计划，而非增量增删改。

#### Scenario: 首次创建计划
- **WHEN** LLM 面对多步任务，首次调用 todo tool
- **THEN** TodoManager 用传入的 items 列表初始化计划，所有 status 为 pending 或 in_progress（最多一项）

#### Scenario: 更新计划
- **WHEN** LLM 再次调用 todo tool 传入新的 items 列表
- **THEN** TodoManager 完全替换旧计划为新列表

#### Scenario: in_progress 唯一性约束
- **WHEN** LLM 传入的 items 中有多于一项 status 为 in_progress
- **THEN** 系统拒绝更新并返回错误提示 "Only one item can be in_progress"

### Requirement: TodoManager 状态渲染
系统 SHALL 将当前计划渲染为可读文本，格式为每行一项：`[ ]` pending、`[>]` in_progress、`[x]` completed。渲染结果通过 MemorySegment 注入后续 LLM 调用的 prompt。

#### Scenario: 渲染格式
- **WHEN** TodoManager 包含 items
- **THEN** `render()` 返回格式化文本，如：
  ```
  [>] 分析用户需求
  [ ] 设计数据模型
  [ ] 实现核心逻辑
  [ ] 编写测试
  ```

#### Scenario: 空计划不注入
- **WHEN** TodoManager 无任何 items
- **THEN** `render()` 返回空字符串，不注入 prompt

#### Scenario: activeForm 显示
- **WHEN** 某项 in_progress 的 item 有 activeForm 字段
- **THEN** 渲染时显示 activeForm 而非 content，如 `[>] 正在分析用户需求...`

### Requirement: Todo 计划注入 Prompt
系统 SHALL 通过 MemorySegment 将 TodoManager 渲染的计划文本注入每轮 LLM 调用的 prompt，确保 LLM 始终能看到当前任务进度。

#### Scenario: 计划注入位置
- **WHEN** PromptBuilder 构建消息列表
- **THEN** 计划文本作为 `<todo_plan>` 标签包裹的内容注入，位于 system prompt 的 MemorySegment 中

#### Scenario: Tool 返回确认
- **WHEN** LLM 调用 todo tool 成功
- **THEN** tool 返回渲染后的计划文本作为 Observation content，LLM 可在下轮看到更新后的计划

### Requirement: Todo 过期提醒
系统 SHALL 在 ReAct 循环中检测计划更新新鲜度。当连续 3 轮（可配置）迭代未调用 todo tool 更新计划时，自动注入提醒。

#### Scenario: 触发提醒
- **WHEN** TaskState.rounds_since_todo_update >= 3 且 TodoManager 有未完成项
- **THEN** ReActLoop 在 observation 前插入 `<reminder>Refresh your plan before continuing.</reminder>`

#### Scenario: 不触发提醒
- **WHEN** TaskState.rounds_since_todo_update < 3 或 TodoManager 无计划（空 items）
- **THEN** 不插入提醒

#### Scenario: 提醒后重置
- **WHEN** LLM 调用 todo tool 更新计划
- **THEN** TaskState.rounds_since_todo_update 重置为 0

### Requirement: Todo 工具调用结果可追溯
系统 SHALL 将每次 todo tool 的调用记录在 ReAct step history 中，与其他工具调用享有相同的可追溯性。

#### Scenario: Trace 记录
- **WHEN** LLM 调用 todo tool
- **THEN** 该调用作为标准 ReActStep 记录，包含 thought（LLM 决定更新计划的理由）、action（tool_name="todo", args=items）、observation（渲染后的计划文本）
