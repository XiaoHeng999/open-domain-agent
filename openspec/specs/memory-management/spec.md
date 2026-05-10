## ADDED Requirements

### Requirement: Working Memory（当前 Context Window）
系统 SHALL 管理 Agent 当前对话的完整上下文窗口，包含系统 prompt、对话历史、检索到的记忆、当前任务状态。当 token 接近上限时自动压缩。

#### Scenario: 上下文自动压缩
- **WHEN** 对话轮次增加导致 context 接近 token 上限（如 >80%）
- **THEN** 系统自动压缩早期对话为摘要，保留最近 N 轮完整对话 + 关键摘要，确保不超出限制

#### Scenario: 压缩后上下文保留
- **WHEN** 上下文被压缩
- **THEN** 最近的 3 轮对话完整保留，之前的对话保留意图 + 结果摘要

### Requirement: Episodic Summary Store
系统 SHALL 存储历史对话的结构化摘要，包含意图、结果、关键决策点。摘要写入触发时机：after task / after reflection / after checkpoint。

#### Scenario: 任务完成后写入摘要
- **WHEN** 一个任务成功完成
- **THEN** 系统提取任务意图、执行步骤摘要、最终结果、用户反馈（如有），写入 episodic store

#### Scenario: 相关历史检索
- **WHEN** 用户提到 "用上次那个方法"
- **THEN** 系统从 episodic store 检索与当前意图相关的历史摘要，top-K 结果注入 working memory

### Requirement: User Profile State
系统 SHALL 维护长期用户状态画像，包含用户偏好、习惯、历史模式。在每次对话开始时加载，对话结束时更新。

#### Scenario: 偏好自动更新
- **WHEN** 用户在对话中明确表示 "我喜欢表格形式的输出"
- **THEN** 系统将此偏好写入 user profile，后续对话默认使用表格输出格式

#### Scenario: Profile 加载
- **WHEN** 新对话开始且用户已有 profile
- **THEN** 系统将用户偏好摘要注入 system prompt 或 context 头部

### Requirement: 失败驱动记忆强化
系统 SHALL 记录工具错误模式、幻觉模式、用户纠正，形成 "avoidance hints" 写入记忆。

#### Scenario: 工具错误模式记录
- **WHEN** Agent 在某类工具调用上反复出错（如搜索参数格式错误）
- **THEN** 系统记录错误模式到 user profile，下次执行时注入 avoidance hint

#### Scenario: 用户纠正记忆
- **WHEN** 用户纠正 Agent 的输出（如 "不对，我要的是 X 不是 Y"）
- **THEN** 系统将纠正内容写入 user profile，避免后续重复犯错

### Requirement: 记忆操作 Trace
系统 SHALL 为每次记忆读写操作生成 trace，包含操作类型、目标层、内容摘要、耗时。

#### Scenario: 记忆操作 trace
- **WHEN** 执行一次 episodic memory 检索
- **THEN** trace 包含 memory_layer="episodic"、query、results（含相关性分数）、latency_ms

### Requirement: Semantic KB / RAG 接口预留
系统 SHALL 定义 Semantic KB 的标准接口（write / query / delete），本期仅提供接口定义和 in-memory stub 实现。

#### Scenario: 接口可调用
- **WHEN** 开发者调用 semantic_kb.query("用户偏好")
- **THEN** stub 实现返回空结果，不报错，接口可正常调用
