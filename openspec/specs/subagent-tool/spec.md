## ADDED Requirements

### Requirement: SubagentTool 工具定义
SubagentTool SHALL 继承 Tool ABC，以名称 `task` 注册到 ToolRegistry。其 `parameters` SHALL 定义以下 JSON Schema：
- `prompt` (string, required): 传递给子代理的完整任务指令
- `subagent_type` (string, optional, default="explore"): 子代理预设类型名称
- `description` (string, optional): 3-5 词的简短任务描述，用于 UI 展示
- `run_in_background` (boolean, optional, default=false): 是否异步执行
- `max_turns` (integer, optional, default=10): 子代理独立迭代预算

#### Scenario: SubagentTool 注册到 ToolRegistry
- **WHEN** AgentRuntime 启动并初始化 SubagentManager
- **THEN** ToolRegistry 中 SHALL 存在名为 `task` 的工具，其 description 包含 "Spawn a sub-agent"
- **THEN** 该工具的 parameters SHALL 包含 prompt（required）、subagent_type、description、run_in_background、max_turns

#### Scenario: SubagentTool 不在子代理的工具集中
- **WHEN** 子代理启动并构建受限工具集
- **THEN** 子代理的 ToolRegistry 中 SHALL 不包含 `task` 工具，防止嵌套 spawn

### Requirement: SubagentTool 同步执行
SubagentTool.execute() SHALL 同步执行子代理：创建隔离的 ReActLoop 实例，运行完整循环，返回子代理的最终回答文本。

#### Scenario: 同步执行返回摘要
- **WHEN** 父代理调用 `task` 工具，参数 prompt="查找所有API端点", subagent_type="explore", run_in_background=false
- **THEN** SubagentTool SHALL 创建新的 ReActLoop 实例（使用受限工具集和预设系统提示）
- **THEN** ReActLoop SHALL 以 prompt 作为 user_input 运行
- **THEN** execute() SHALL 返回子代理 AgentResponse.answer 字符串作为工具结果

#### Scenario: 同步执行受并发限制
- **WHEN** 活跃子代理数量已达到 max_concurrent 上限
- **THEN** 新的同步调用 SHALL 等待直到有空闲槽位，而非直接失败

### Requirement: SubagentTool 异步执行
当 `run_in_background=true` 时，SubagentTool.execute() SHALL 立即返回一个后台任务标识符，子代理在后台异步运行。

#### Scenario: 后台执行立即返回
- **WHEN** 父代理调用 `task` 工具，参数 run_in_background=true
- **THEN** execute() SHALL 立即返回格式为 "[Started subagent: <agent_id>]" 的字符串
- **THEN** 子代理 SHALL 在后台 asyncio.Task 中运行

#### Scenario: 后台任务结果收集
- **WHEN** 后台子代理完成执行
- **THEN** 结果 SHALL 存储在 SubagentManager 中，父代理后续可通过 agent_id 获取
- **THEN** 结果格式 SHALL 为子代理 AgentResponse.answer 文本

### Requirement: SubagentTool 执行追踪
SubagentTool.execute() SHALL 在父代理的 Trace 中创建嵌套 Span，记录子代理调用的元数据。

#### Scenario: 子代理调用产生追踪 Span
- **WHEN** SubagentTool 执行子代理调用
- **THEN** SHALL 在父代理 Trace 中创建 Span，kind=SUBAGENT
- **THEN** Span SHALL 包含属性：subagent_type, prompt（截断到200字符）, max_turns, background
- **THEN** Span SHALL 在子代理完成后结束，包含属性：success, result_length

## MODIFIED Requirements

### Requirement: SubagentTool 工具描述
SubagentTool 的 description 属性 SHALL 提供每个内置 preset 的适用场景提示，帮助 LLM 准确选择 subagent_type。

#### Scenario: 工具描述包含所有 preset 类型
- **WHEN** SubagentTool 注册到 ToolRegistry
- **THEN** description 属性 SHALL 列出所有内置 preset（explore, plan, code-reviewer, code-writer, researcher）及其适用场景
- **THEN** description SHALL 不包含 "general" preset

#### Scenario: 参数描述反映 preset 选项
- **WHEN** LLM 获取 task 工具的参数 schema
- **THEN** subagent_type 参数的 description SHALL 包含所有内置 preset 名称（explore, plan, code-reviewer, code-writer, researcher）
- **THEN** subagent_type 参数的 default SHALL 为 "explore"
