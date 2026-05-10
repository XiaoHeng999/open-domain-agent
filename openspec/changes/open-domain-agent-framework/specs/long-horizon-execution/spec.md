## ADDED Requirements

### Requirement: Optional Planning Step
系统 SHALL 在 ReAct 循环前提供 optional planning step，仅当 Complexity Judge 判定为 complex 时触发。Planning step 生成有序步骤列表（非 DAG），作为 ReAct 循环的 guidance。

#### Scenario: 复杂任务触发规划
- **WHEN** Complexity Judge 判定任务为 complex
- **THEN** 系统调用 Plan Generator 生成有序步骤列表，如 [1. "搜索竞品A数据", 2. "搜索竞品B数据", 3. "对比分析", 4. "生成报告"]

#### Scenario: Planning step 作为 guidance
- **WHEN** ReAct 循环执行中偏离 plan
- **THEN** ReAct 可以偏离（plan 不是 constraint），但 trace 中记录偏离情况

#### Scenario: 简单任务跳过规划
- **WHEN** Complexity Judge 判定任务为 simple
- **THEN** 跳过 planning step，直接进入 ReAct 循环

### Requirement: Step-Level Checkpoint
系统 SHALL 在 ReAct 循环的每一步保存 checkpoint，包含当前 step number、累积 context、tool call history、memory snapshot。

#### Scenario: 每步自动 checkpoint
- **WHEN** ReAct 循环完成一步（thought → action → observation）
- **THEN** 系统保存当前 step 的 checkpoint，包含 step_number、context_snapshot、tool_calls_so_far、memory_state

#### Scenario: Checkpoint 粒度可配置
- **WHEN** 配置 checkpoint_interval=5
- **THEN** 系统每 5 步保存一次 checkpoint，而非每步

### Requirement: Resume from Checkpoint
系统 SHALL 支持从任意 checkpoint 恢复执行，恢复 context 和 memory 状态。

#### Scenario: 失败后恢复
- **WHEN** 任务在第 7 步失败，checkpoint 存在于第 5 步
- **THEN** 系统从第 5 步的 checkpoint 恢复 context 和 memory，重新执行第 6 步起

#### Scenario: 恢复后 idempotent
- **WHEN** 从 checkpoint 恢复后重新执行某步
- **THEN** 若该步有副作用（如发送消息），系统通过 idempotency key 确保不重复执行

### Requirement: 状态持久化
系统 SHALL 将 checkpoint 持久化到本地存储（JSON 文件或 SQLite），支持外部存储扩展。

#### Scenario: Checkpoint 存储
- **WHEN** 一个 checkpoint 被保存
- **THEN** 数据写入配置的存储后端，包含完整的执行状态快照

#### Scenario: 存储后端可扩展
- **WHEN** 开发者实现 CheckpointStorage 接口并注册 Redis 实现
- **THEN** 框架使用 Redis 存储 checkpoint，无需修改框架代码

### Requirement: 失败驱动记忆强化
系统 SHALL 在 checkpoint 恢复后记录失败模式到记忆，形成 avoidance hints。

#### Scenario: 失败模式记录
- **WHEN** 任务因工具调用超时失败并从 checkpoint 恢复
- **THEN** 系统记录 "该工具在此类任务上可能超时" 的 hint，后续执行时考虑增加超时时间或使用 fallback
