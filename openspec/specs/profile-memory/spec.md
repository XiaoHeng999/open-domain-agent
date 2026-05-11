## ADDED Requirements

### Requirement: ProfileMemory 持久化存储
系统 SHALL 使用 SQLite 持久化存储用户画像数据，包含 preferences（JSON dict）、constraints（JSON list）、tech_stack（JSON list）、risk_tolerance、style、avoidance_hints（JSON list）。单用户场景使用固定 id=1 的单行记录。

#### Scenario: 首次创建 profile
- **WHEN** 系统启动且 profile.sqlite 不存在
- **THEN** 自动创建数据库和表，插入默认空行（preferences={}, constraints=[], tech_stack=[]）

#### Scenario: 加载已有 profile
- **WHEN** 系统启动且 profile.sqlite 存在
- **THEN** 从 SQLite 读取 profile 数据，加载到内存

#### Scenario: 更新 profile 字段
- **WHEN** 用户在对话中明确表达偏好（如"我喜欢表格输出"）
- **THEN** 系统将偏好合并写入 preferences JSON 字段，更新 updated_at timestamp

### Requirement: ProfileMemory 自动注入 System Prompt
系统 SHALL 每次 PromptBuilder.build() 时自动将 ProfileMemory 内容注入 system prompt。注入内容为结构化文本，非原始 JSON。

#### Scenario: Profile 注入格式
- **WHEN** PromptBuilder 构建系统 prompt
- **THEN** ProfileMemory 返回格式化文本，如："用户偏好：表格输出, 中文回复 | 约束：不使用外部API | 技术栈：Python, React"

#### Scenario: Profile 为空时的行为
- **WHEN** 用户 profile 尚无任何偏好记录
- **THEN** 不注入任何 profile 内容，不占用 prompt token

#### Scenario: Profile 信息量控制
- **WHEN** profile 内容超过 500 tokens
- **THEN** 系统自动精简低优先级条目，确保注入内容在 200-500 tokens 范围内

### Requirement: ProfileMemory 不存储对话历史
系统 SHALL 确保 ProfileMemory 只存储用户建模信息（偏好、约束、风格、技术栈、风险偏好、avoidance hints），不存储任何对话历史或任务轨迹。

#### Scenario: 拒绝写入对话内容
- **WHEN** 尝试将对话原文或任务步骤写入 ProfileMemory
- **THEN** 系统拒绝写入，仅允许写入结构化的用户建模字段

### Requirement: ProfileMemory Avoidance Hints
系统 SHALL 维护 avoidance hints 列表，记录错误模式和用户纠正。hints 在每次对话开始时加载，注入 system prompt 以避免重复犯错。

#### Scenario: 记录错误模式
- **WHEN** Agent 在某类操作上反复出错
- **THEN** 系统将错误描述作为 avoidance hint 写入 ProfileMemory

#### Scenario: 记录用户纠正
- **WHEN** 用户纠正 Agent 的输出（如"不对，应该是 X"）
- **THEN** 系统将纠正内容写入 avoidance hints

#### Scenario: Avoidance hints 去重
- **WHEN** 新 hint 与已有 hint 语义重复
- **THEN** 系统合并为一条，不重复存储
