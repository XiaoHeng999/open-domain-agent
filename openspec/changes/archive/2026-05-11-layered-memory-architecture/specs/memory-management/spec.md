## MODIFIED Requirements

### Requirement: Working Memory（当前 Context Window）
系统 SHALL 使用 RuntimeMemory 统一管理 Agent 当前对话的完整上下文窗口，包含对话历史、rolling summary、执行状态（TaskState）。计划管理由 `todo` tool 负责（独立于 RuntimeMemory）。当 token 接近上限时按三级策略自动压缩（Normal/Compressing/Aggressive）。

#### Scenario: 上下文自动压缩
- **WHEN** 对话轮次增加导致 context 接近 token 上限（>=70% budget）
- **THEN** 系统自动将最早的 2 轮 raw 对话压缩为 rolling summary，保留最近 N 轮完整对话 + summary 标记

#### Scenario: 激进压缩
- **WHEN** context 达到 90% budget
- **THEN** 系统额外限制 retrieval 注入量和工具结果缓存，确保不超出 token 上限

#### Scenario: 压缩后上下文保留
- **WHEN** 上下文被压缩
- **THEN** 最近的 3 轮对话完整保留，TaskState（执行状态）始终保留，之前的对话替换为 rolling summary 标记

### Requirement: Plan（任务规划）
系统 SHALL 将 PlanGenerator 保留为可选的预处理步骤（一次性初始规划），同时新增 `todo` tool 作为会话级持续计划管理机制。LLM 通过 tool call 主动更新计划，计划状态通过 MemorySegment 注入 prompt，连续 3 轮未更新时自动提醒。

#### Scenario: 初始规划（PlanGenerator）
- **WHEN** 复杂任务且 routing_decision.skip_planning=False
- **THEN** PlanGenerator 生成初始步骤列表，可作为 LLM 首次调用 todo tool 的参考

#### Scenario: 持续计划更新（todo tool）
- **WHEN** LLM 在 ReAct 循环中需要更新任务计划
- **THEN** LLM 调用 `todo` tool 传入完整 items 列表，替换当前计划，计划渲染文本注入后续 prompt

### Requirement: Episodic Summary Store
系统 SHALL 将 Episodic Summary Store 合并到 RetrievalMemory 的 Episodic 子层，使用向量存储实现持久化和语义检索。

#### Scenario: 任务完成后写入摘要
- **WHEN** 一个任务成功完成
- **THEN** 系统提取任务意图、执行步骤摘要、最终结果、用户反馈（如有），生成 embedding，写入 RetrievalMemory episodic 子层

#### Scenario: 相关历史检索
- **WHEN** 用户提到 "用上次那个方法"
- **THEN** 系统从 RetrievalMemory episodic 子层进行向量检索，top-K 结果在 max_inject_tokens 限制内注入 prompt

### Requirement: User Profile State
系统 SHALL 将 User Profile State 迁移到 ProfileMemory，使用 SQLite 持久化，存储偏好、约束、风格、技术栈、风险偏好、avoidance hints。每次对话开始时自动加载并注入 system prompt。

#### Scenario: 偏好自动更新
- **WHEN** 用户在对话中明确表示 "我喜欢表格形式的输出"
- **THEN** 系统将此偏好写入 ProfileMemory 的 preferences 字段，后续对话默认使用表格输出格式

#### Scenario: Profile 加载
- **WHEN** 新对话开始且用户已有 profile
- **THEN** 系统从 SQLite 加载用户画像，将结构化文本注入 system prompt

### Requirement: 失败驱动记忆强化
系统 SHALL 记录工具错误模式、幻觉模式、用户纠正，形成 "avoidance hints" 写入 ProfileMemory，并可通过 RetrievalMemory 的 episodic 子层检索历史失败模式。

#### Scenario: 工具错误模式记录
- **WHEN** Agent 在某类工具调用上反复出错
- **THEN** 系统记录错误模式到 ProfileMemory 的 avoidance_hints，并在 episodic 子层记录详细失败经历

#### Scenario: 用户纠正记忆
- **WHEN** 用户纠正 Agent 的输出
- **THEN** 系统将纠正内容写入 ProfileMemory 的 avoidance_hints

### Requirement: 记忆操作 Trace
系统 SHALL 为每次记忆读写操作生成 trace，包含操作类型、目标层（runtime/profile/retrieval/archive）、内容摘要、耗时。

#### Scenario: 记忆操作 trace
- **WHEN** 执行一次 RetrievalMemory 检索
- **THEN** trace 包含 memory_layer="retrieval"、query、results（含相关性分数）、latency_ms

### Requirement: Semantic KB / RAG 接口预留
系统 SHALL 将 Semantic KB 替换为 RetrievalMemory 的 Semantic 子层，支持向量检索和 metadata 过滤。提供 write / query / delete 完整实现，不再仅是 stub。

#### Scenario: 语义知识写入与检索
- **WHEN** 开发者调用 retrieval_memory.write(layer="semantic", text="...", metadata={...})
- **THEN** 系统生成 embedding，持久化存储，后续 query 可按语义相似度检索

## REMOVED Requirements

### Requirement: Semantic KB / RAG 接口预留（stub 版本）
**Reason**: SemanticKB 的 stub 实现被 RetrievalMemory 的 Semantic 子层完整替换，不再需要仅返回空结果的 stub。
**Migration**: 所有调用 `SemanticKB.query()` 的代码改为调用 `RetrievalMemory.query(layer="semantic")`
