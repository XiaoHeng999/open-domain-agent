## ADDED Requirements

### Requirement: Trace 级别行为采集
系统 SHALL 采集每次 Agent 执行的完整 trace，贯穿所有模块：路由决策、工具调用、记忆读写。

#### Scenario: 完整 trace 采集
- **WHEN** 一次 Agent 执行完成
- **THEN** trace 包含：routing spans（complexity/domain/intent）、tool_call spans（每次调用）、memory spans（每次读写）、agent_loop spans（每轮迭代）

#### Scenario: 实时 trace 可查
- **WHEN** Agent 正在执行中
- **THEN** 监控端可以查询当前已生成的 spans，查看执行进度

### Requirement: 异常行为检测
系统 SHALL 自动检测 Agent 执行中的异常模式：工具调用循环、重复相同错误、token 消耗异常、执行超时。

#### Scenario: 工具调用循环检测
- **WHEN** Agent 连续 3 次调用同一工具且参数基本相同
- **THEN** 系统触发 "tool_loop" 告警，标记该 trace 为异常

#### Scenario: 重复错误检测
- **WHEN** Agent 在不同步骤中犯相同类型的错误（如同一个参数格式错误出现 2 次）
- **THEN** 系统记录错误模式，触发 "repeated_error" 告警

### Requirement: 在线质量评分
系统 SHALL 对每次 Agent 执行计算质量分数。

#### Scenario: 质量评分计算
- **WHEN** 一次 Agent 执行完成
- **THEN** 计算 quality_score（0-100），基于：task_completed(40%) + tool_efficiency(30%) + token_efficiency(20%) + no_errors(10%)

### Requirement: 自动反馈回路
系统 SHALL 支持将监控发现的问题自动反馈到后续执行中。

#### Scenario: 错误模式 → Avoidance Hint
- **WHEN** 监控检测到 Agent 在某类任务上反复犯相同错误
- **THEN** 系统自动生成 avoidance hint 写入 user profile，下次执行同类任务时注入

#### Scenario: 高质量 Trace → Eval 建议
- **WHEN** 监控发现一条高质量 trace（高完成度、高效率、无错误）
- **THEN** 系统建议将此 trace 转化为评测用例，可一键确认
