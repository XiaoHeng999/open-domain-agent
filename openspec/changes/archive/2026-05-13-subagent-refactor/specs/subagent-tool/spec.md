## MODIFIED Requirements

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
