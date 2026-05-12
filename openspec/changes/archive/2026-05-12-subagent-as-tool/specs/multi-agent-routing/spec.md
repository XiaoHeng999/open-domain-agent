## MODIFIED Requirements

### Requirement: 简单任务直通模式
系统 SHALL 支持简单任务跳过 planning step，直接进入 ReAct 循环。直通模式下 SHALL 使用默认全量工具集而非过滤后的子集。Planning 控制 SHALL 在 runtime 中实际生效：skip_planning=False 时调用 PlanGenerator。当 RoutingPipeline 输出的 RoutingDecision 包含建议的 subagent_type 时，AgentRuntime SHALL 将此信息传递给 ReActLoop 的 prompt context，供 LLM 决定是否调用 `task` 工具。

#### Scenario: 简单任务快速路径（现有行为保持）
- **WHEN** Complexity Judge 判定为 simple 且 confidence > 0.9
- **THEN** 跳过 planning step，直接进入 ReAct 循环，使用全量工具集

#### Scenario: 复杂任务触发规划（现有行为保持）
- **WHEN** routing_decision.skip_planning == False
- **THEN** AgentRuntime 调用 plan_generator.generate()，生成计划注入 ReAct context

#### Scenario: 路由建议子代理类型（新增行为）
- **WHEN** RoutingDecision.metadata 中包含 suggested_subagent_type 字段
- **THEN** AgentRuntime SHALL 将 suggested_subagent_type 注入 prompt_context
- **THEN** 父代理 LLM 可在系统提示中看到建议，自主决定是否使用 `task` 工具委派
