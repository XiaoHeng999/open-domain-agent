## ADDED Requirements

### Requirement: 预设类型定义结构
每个子代理预设类型 SHALL 包含以下字段：
- `name` (string): 预设类型标识符（kebab-case）
- `system_prompt` (string): 注入子代理的系统提示文本
- `allowed_tools` (list[string]): 允许使用的工具名列表（空列表=所有工具）
- `max_turns` (integer): 默认迭代上限
- `description` (string): 简短描述，用于工具描述文本

#### Scenario: 预设类型字段完整性
- **WHEN** 定义一个名为 "explore" 的预设类型
- **THEN** SHALL 包含 system_prompt 明确声明只读角色
- **THEN** SHALL 包含 allowed_tools 仅列出 Glob、Grep、Read 等只读工具
- **THEN** SHALL 包含 max_turns <= 20
- **THEN** SHALL 包含 description 简述用途

### Requirement: 内置预设类型 - Explore
系统 SHALL 提供内置的 "explore" 预设类型，用于代码库探索和信息检索。

#### Scenario: Explore 预设只读工具集
- **WHEN** 使用 subagent_type="explore" 创建子代理
- **THEN** 子代理的工具集 SHALL 仅包含：read_file, list_dir, web_search, web_fetch
- **THEN** 子代理 SHALL 不包含：write_file, edit_file, exec, task

#### Scenario: Explore 预设系统提示
- **WHEN** 使用 subagent_type="explore" 创建子代理
- **THEN** 系统提示 SHALL 包含 "you are a read-only explorer" 语义
- **THEN** 系统提示 SHALL 明确禁止修改文件或执行命令

### Requirement: 内置预设类型 - Plan
系统 SHALL 提供内置的 "plan" 预设类型，用于任务规划和方案设计。

#### Scenario: Plan 预设规划工具集
- **WHEN** 使用 subagent_type="plan" 创建子代理
- **THEN** 子代理的工具集 SHALL 包含：read_file, list_dir, web_search, web_fetch
- **THEN** 子代理 SHALL 不包含：write_file, edit_file, exec, task

#### Scenario: Plan 预设系统提示
- **WHEN** 使用 subagent_type="plan" 创建子代理
- **THEN** 系统提示 SHALL 指示子代理专注于分析和规划，不执行修改操作
- **THEN** 系统提示 SHALL 要求输出结构化的步骤计划

### Requirement: 内置预设类型 - General
系统 SHALL 提供内置的 "general" 预设类型，作为默认的通用子代理。

#### Scenario: General 预设全量工具集
- **WHEN** 使用 subagent_type="general" 创建子代理
- **THEN** 子代理的工具集 SHALL 包含 ToolRegistry 中除 `task` 外的所有工具
- **THEN** 子代理 SHALL 不包含 `task` 工具

#### Scenario: General 预设默认系统提示
- **WHEN** 使用 subagent_type="general" 创建子代理
- **THEN** 系统提示 SHALL 为通用的 agent 角色描述

### Requirement: 预设类型配置扩展
用户 SHALL 能通过 config.yaml 的 subagent.presets 字段覆盖内置预设或添加新预设。

#### Scenario: 配置覆盖内置预设
- **WHEN** config.yaml 中 subagent.presets 包含 name="explore" 的自定义预设
- **THEN** SHALL 使用用户配置的 system_prompt 和 allowed_tools 覆盖内置 explore 预设

#### Scenario: 配置添加新预设
- **WHEN** config.yaml 中 subagent.presets 包含 name="code-review" 的新预设
- **THEN** 该预设 SHALL 可通过 subagent_type="code-review" 使用

### Requirement: SubagentConfig 配置模型
AgentConfig SHALL 新增 `subagent: SubagentConfig` 字段，包含全局子代理配置。

#### Scenario: SubagentConfig 默认值
- **WHEN** AgentConfig 未配置 subagent 字段
- **THEN** SHALL 使用默认值：enabled=true, max_concurrent=5, max_children=3, default_max_turns=10, presets=[]

#### Scenario: SubagentConfig 从 YAML 加载
- **WHEN** config.yaml 包含 `subagent: {max_concurrent: 3, max_children: 2}`
- **THEN** SHALL 解析为 SubagentConfig(max_concurrent=3, max_children=2)
