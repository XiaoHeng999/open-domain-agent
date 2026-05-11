## ADDED Requirements

### Requirement: RetrievalMemory 向量存储后端
系统 SHALL 实现基于 numpy 的向量存储，支持 write（写入向量+文本+metadata）、query（余弦相似度检索 top_k）、delete 操作。数据持久化为本地文件。

#### Scenario: 写入向量记录
- **WHEN** 存储一条记忆（episodic 或 semantic）
- **THEN** 系统生成文本 embedding，将 (id, embedding, text, metadata) 写入向量存储，持久化到磁盘

#### Scenario: 向量检索
- **WHEN** 给定 query 文本和 top_k 参数
- **THEN** 系统生成 query embedding，计算与所有存储向量的余弦相似度，返回 top_k 条最相似记录及其 score

#### Scenario: Metadata 过滤
- **WHEN** 检索时指定 metadata 过滤条件（如 layer="episodic"）
- **THEN** 系统仅返回满足过滤条件的记录

#### Scenario: 持久化与加载
- **WHEN** 系统启动且 retrieval 存储目录存在已有数据
- **THEN** 自动从磁盘加载向量数据和 metadata

### Requirement: RetrievalMemory Episodic 子层
系统 SHALL 实现 Episodic 子层，存储任务经历的结构化摘要，包含任务意图、步骤摘要、结果、成功/失败标志、关键决策、用户反馈。Metadata 标记为 `layer: "episodic"`。

#### Scenario: 任务完成后写入 episodic 记录
- **WHEN** 一个任务完成（成功或失败）
- **THEN** 系统提取任务意图、步骤摘要、结果、成功/失败标志，生成 embedding，写入向量存储，metadata 包含 layer="episodic", task_type, success, timestamp

#### Scenario: 反思后写入 episodic 记录
- **WHEN** Agent 执行反思步骤
- **THEN** 反思内容作为 episodic 记录写入，包含关键决策和反思总结

#### Scenario: Episodic 记录检索
- **WHEN** 用户查询与历史任务相关（如"上次那个方法"）
- **THEN** 系统检索 episodic 记录，返回最相关的 top_k 条摘要

### Requirement: RetrievalMemory Semantic 子层
系统 SHALL 实现 Semantic 子层，存储抽象知识、总结规则、经验性知识。Metadata 标记为 `layer: "semantic"`。

#### Scenario: 写入语义知识
- **WHEN** Agent 从经验中总结出通用规则（如"该项目的配置文件使用 YAML 格式"）
- **THEN** 系统将知识文本和 metadata（含 layer="semantic", category, confidence）写入向量存储

#### Scenario: 语义知识检索
- **WHEN** 当前任务需要领域知识
- **THEN** 系统检索 semantic 记录，返回最相关的 top_k 条知识

### Requirement: RetrievalMemory Token 管理
系统 SHALL 限制注入 prompt 的检索结果 token 总量。参数 max_inject_tokens（默认 1500）控制上限。

#### Scenario: 检索结果未超限
- **WHEN** 检索结果的总 tokens <= max_inject_tokens
- **THEN** 全部结果注入 MemorySegment 的 retrieval 部分

#### Scenario: 检索结果超限截断
- **WHEN** 检索结果的总 tokens > max_inject_tokens
- **THEN** 按 relevance score 从高到低保留结果，超出 max_inject_tokens 的部分截断，不注入

#### Scenario: Top-K 限制
- **WHEN** 进行向量检索
- **THEN** 默认 top_k=5，可通过配置调整，最大不超过 20

### Requirement: RetrievalMemory 仅命中时注入
系统 SHALL 仅在向量检索命中相关结果时注入 prompt，未命中时不注入任何 retrieval 内容。

#### Scenario: 有相关结果
- **WHEN** query 的最高相似度 score > threshold（默认 0.5）
- **THEN** 将满足条件的检索结果注入 prompt

#### Scenario: 无相关结果
- **WHEN** 所有检索结果的 score <= threshold
- **THEN** 不注入任何 retrieval 内容，prompt 中无 retrieval 部分

### Requirement: RetrievalMemory Embedding 生成
系统 SHALL 支持文本 embedding 生成。优先使用 sentence-transformers 预训练模型；若无可用模型，回退到 TF-IDF 向量化。

#### Scenario: 使用 sentence-transformers
- **WHEN** 系统检测到 sentence-transformers 已安装
- **THEN** 使用预训练模型（如 all-MiniLM-L6-v2）生成 embedding

#### Scenario: 回退到 TF-IDF
- **WHEN** sentence-transformers 不可用
- **THEN** 使用 sklearn TF-IDF 向量化器生成 embedding，并在日志中提示建议安装 sentence-transformers
