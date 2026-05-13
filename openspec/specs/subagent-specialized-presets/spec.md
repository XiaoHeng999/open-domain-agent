## ADDED Requirements

### Requirement: 内置预设类型 - Code Reviewer
系统 SHALL 提供内置的 "code-reviewer" 预设类型，专注于代码审查任务。

#### Scenario: Code Reviewer 只读工具集
- **WHEN** 使用 subagent_type="code-reviewer" 创建子代理
- **THEN** 子代理的工具集 SHALL 仅包含：read_file, list_dir, search, web_search, web_fetch
- **THEN** 子代理 SHALL 不包含：write_file, edit_file, exec, task

#### Scenario: Code Reviewer 系统提示
- **WHEN** 使用 subagent_type="code-reviewer" 创建子代理
- **THEN** 系统提示 SHALL 指示子代理从以下维度审查代码：正确性、安全性、性能、可读性、最佳实践
- **THEN** 系统提示 SHALL 要求输出结构化的审查报告（问题列表 + 严重程度 + 建议）

#### Scenario: Code Reviewer 最大轮次
- **WHEN** 使用 subagent_type="code-reviewer" 创建子代理
- **THEN** max_turns SHALL 为 15

### Requirement: 内置预设类型 - Code Writer
系统 SHALL 提供内置的 "code-writer" 预设类型，专注于代码编写和修改任务。

#### Scenario: Code Writer 写入工具集
- **WHEN** 使用 subagent_type="code-writer" 创建子代理
- **THEN** 子代理的工具集 SHALL 包含：read_file, write_file, edit_file, list_dir, search, exec
- **THEN** 子代理 SHALL 不包含：task

#### Scenario: Code Writer 系统提示
- **WHEN** 使用 subagent_type="code-writer" 创建子代理
- **THEN** 系统提示 SHALL 指导子代理遵循最小改动原则、编写安全代码、保持代码风格一致
- **THEN** 系统提示 SHALL 要求子代理在修改后验证变更（如运行测试）

#### Scenario: Code Writer 最大轮次
- **WHEN** 使用 subagent_type="code-writer" 创建子代理
- **THEN** max_turns SHALL 为 20

## MODIFIED Requirements

### Requirement: 预设类型配置扩展
用户 SHALL 能通过 config.yaml 的 subagent.presets 字段覆盖内置预设或添加新预设。

#### Scenario: 配置覆盖内置预设
- **WHEN** config.yaml 中 subagent.presets 包含 name="code-reviewer" 的自定义预设
- **THEN** SHALL 使用用户配置的 system_prompt 和 allowed_tools 覆盖内置 code-reviewer 预设

#### Scenario: 配置添加新预设
- **WHEN** config.yaml 中 subagent.presets 包含 name="security-scanner" 的新预设
- **THEN** 该预设 SHALL 可通过 subagent_type="security-scanner" 使用
