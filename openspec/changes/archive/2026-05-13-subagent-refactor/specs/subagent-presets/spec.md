## MODIFIED Requirements

### Requirement: 内置预设类型 - Explore
系统 SHALL 提供内置的 "explore" 预设类型，用于代码库探索和信息检索。

#### Scenario: Explore 预设只读工具集
- **WHEN** 使用 subagent_type="explore" 创建子代理
- **THEN** 子代理的工具集 SHALL 包含：read_file, list_dir, search, web_search, web_fetch
- **THEN** 子代理 SHALL 不包含：write_file, edit_file, exec, task

#### Scenario: Explore 预设系统提示
- **WHEN** 使用 subagent_type="explore" 创建子代理
- **THEN** 系统提示 SHALL 包含角色定义（代码库探索专家）
- **THEN** 系统提示 SHALL 明确禁止修改文件或执行命令
- **THEN** 系统提示 SHALL 指导子代理按以下步骤工作：
  1. 使用 search 快速定位相关代码
  2. 使用 read_file 阅读关键文件
  3. 使用 list_dir 了解项目结构
  4. 整合发现，输出简洁准确的总结
- **THEN** 系统提示 SHALL 要求输出结构化摘要（关键发现、文件路径、代码结构）

### Requirement: 内置预设类型 - Plan
系统 SHALL 提供内置的 "plan" 预设类型，用于任务规划和方案设计。

#### Scenario: Plan 预设规划工具集
- **WHEN** 使用 subagent_type="plan" 创建子代理
- **THEN** 子代理的工具集 SHALL 包含：read_file, list_dir, search, web_search, web_fetch
- **THEN** 子代理 SHALL 不包含：write_file, edit_file, exec, task

#### Scenario: Plan 预设系统提示
- **WHEN** 使用 subagent_type="plan" 创建子代理
- **THEN** 系统提示 SHALL 包含角色定义（任务规划专家）
- **THEN** 系统提示 SHALL 明确禁止修改文件或执行命令
- **THEN** 系统提示 SHALL 要求输出结构化的执行计划，包含：
  1. 问题理解与上下文分析
  2. 实现步骤（编号列表，每步包含具体操作和涉及文件）
  3. 依赖关系和风险标注
  4. 验证方案

## REMOVED Requirements

### Requirement: 内置预设类型 - General
**Reason**: general 预设职责模糊，与 subagent 专业分工原则冲突。主 agent 本身已是 general-purpose，subagent 的价值在于专业化。
**Migration**: 使用 `explore` 作为默认 subagent_type（只读安全）。需要写入能力时使用 `code-writer`。未知 subagent_type 将 fallback 到 `explore`。
