## ADDED Requirements

### Requirement: RuntimeMemory 对话缓冲管理
系统 SHALL 维护当前 session 的完整对话缓冲，包含 user、assistant、tool 消息，所有消息按时间顺序排列并带有 timestamp。

#### Scenario: 添加对话消息
- **WHEN** 一轮对话完成（用户输入 → Agent 思考 → 工具调用 → 观察结果）
- **THEN** RuntimeMemory 按顺序记录所有角色消息（user/assistant/tool），每条消息包含 role、content、timestamp

#### Scenario: 获取当前上下文
- **WHEN** PromptBuilder 需要 RuntimeMemory 的上下文
- **THEN** RuntimeMemory 返回 rolling_summary（如有）+ 最近 N 轮 raw 消息，格式为 list[dict]，可直接拼入 LLM messages

### Requirement: RuntimeMemory Token Budget 管理
系统 SHALL 实现 token budget 管理，当对话缓冲接近 token 上限时自动触发压缩。压缩策略为三级：Normal（<70%）、Compressing（70%-90%）、Aggressive（>=90%）。

#### Scenario: 正常阶段——不压缩
- **WHEN** total_tokens < budget * 0.7
- **THEN** 保留全部 raw messages，不触发压缩

#### Scenario: 压缩阶段——rolling summary
- **WHEN** total_tokens >= budget * 0.7
- **THEN** 系统将最早的 2 轮 raw 对话压缩为 summary 文本，追加到 rolling_summary，删除原始消息，在消息列表中插入 `[Summary of turns N-M]` 标记

#### Scenario: 激进压缩阶段——限制注入
- **WHEN** total_tokens >= budget * 0.9
- **THEN** 除 rolling summary 压缩外，额外限制 retrieval 注入量（减半 top_k），截断工具结果缓存至 max_tool_result_tokens

#### Scenario: 压缩后 summary 标记保留
- **WHEN** 消息被压缩为 summary
- **THEN** 消息列表中对应位置出现 `[Earlier conversation summary: ...]` 标记，明确标识哪些内容是压缩后的摘要

### Requirement: RuntimeMemory 执行状态管理
系统 SHALL 维护当前 ReAct 循环的执行状态，包含迭代计数、完成标志、终止条件、距上次 todo 更新的轮次。执行状态不参与压缩，始终保留在 RuntimeMemory 中。

#### Scenario: 执行状态初始化
- **WHEN** 新 ReAct 循环开始
- **THEN** RuntimeMemory 初始化 TaskState：current_step=0, finished=False, termination_flags=[], rounds_since_todo_update=0

#### Scenario: 迭代计数递增
- **WHEN** ReAct 循环执行一步
- **THEN** TaskState 的 current_step 递增，rounds_since_todo_update 递增

#### Scenario: 任务完成
- **WHEN** ReAct 循环检测到终止条件（direct_answer / 重复动作 / max_iterations）
- **THEN** TaskState 的 finished 设为 True，记录 termination_flag

#### Scenario: Todo 更新轮次重置
- **WHEN** LLM 调用 todo tool 更新计划
- **THEN** TaskState 的 rounds_since_todo_update 重置为 0

### Requirement: RuntimeMemory Rolling Summary
系统 SHALL 维护一个 rolling summary，存储早期对话的压缩摘要。当 rolling summary 自身超出 token 预算的 30% 时，对其进行二次压缩。

#### Scenario: Rolling summary 累积
- **WHEN** 多次压缩后 rolling summary 持续增长
- **THEN** 当 rolling summary tokens > budget * 0.3 时，将整个 summary 再次压缩为更短的摘要

#### Scenario: Rolling summary 为空
- **WHEN** session 刚开始且无历史压缩
- **THEN** rolling summary 为空字符串，不注入 prompt

### Requirement: RuntimeMemory 工具调用结果缓存
系统 SHALL 缓存当前 session 的工具调用结果，避免重复调用。缓存以 (tool_name, args_hash) 为 key。

#### Scenario: 缓存命中
- **WHEN** 同一 session 内对相同工具和参数发起第二次调用
- **THEN** RuntimeMemory 返回缓存结果，不执行实际工具调用

#### Scenario: 缓存清理
- **WHEN** 工具结果缓存超出 token 预算
- **THEN** 按 LRU 策略清除最早的缓存条目
