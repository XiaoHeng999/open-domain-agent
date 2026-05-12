## MODIFIED Requirements

### Requirement: Missing slots 澄清流程
系统 SHALL 在 routing 结果的 `missing_slots` 非空时，生成澄清问题直接返回给用户，不进入 ReAct loop。澄清问题 SHALL 针对缺失的槽位逐个询问。RoutingPipeline.route() SHALL 接受可选的 `history` 参数并透传给 UnifiedLLMRouter，使 missing_slots 的判定能基于对话上下文而非仅当前输入。

#### Scenario: 槽位缺失触发澄清
- **WHEN** 用户输入 "帮我搜索数据" 且 history 为空，路由提取 intent="search_data"、missing_slots=["data_source","time_range"]
- **THEN** AgentRuntime 返回澄清问题 "请提供以下信息：data_source, time_range"，不执行 ReAct loop

#### Scenario: 槽位完整正常执行
- **WHEN** 用户输入 "搜索2024年财报数据" 且 missing_slots=[]
- **THEN** 正常进入 ReAct loop 执行

#### Scenario: 多轮对话从历史推断槽位避免误澄清
- **WHEN** history 包含上一轮 `user:"2+2等于几？"` 和 `assistant:"2+2=4"`，当前用户输入 "再加100等于几？" 且路由从历史推断出 base_number=4
- **THEN** missing_slots=[]，正常进入 ReAct loop 执行，不触发澄清

#### Scenario: RoutingPipeline 透传 history 到 UnifiedLLMRouter
- **WHEN** runtime 调用 `routing_pipeline.route(user_input, history=[...])` 且使用 unified LLM 路径
- **THEN** RoutingPipeline 将 history 透传给 `UnifiedLLMRouter.route(user_input, history=history)`

#### Scenario: Keyword fallback 不使用 history
- **WHEN** UnifiedLLMRouter 调用失败 fallback 到 keyword 管线
- **THEN** keyword 管线不使用 history，仍按原有 keyword 匹配逻辑执行

### Requirement: skip_planning 控制 PlanGenerator 调用
系统 SHALL 根据 `routing_decision.skip_planning` 决定是否调用 `PlanGenerator.generate()`。skip_planning=True 时跳过规划直接进入 ReAct 循环；skip_planning=False 时先调用 PlanGenerator 生成计划，再将计划注入 ReAct context。

#### Scenario: 复杂任务触发规划
- **WHEN** routing_decision.complexity="complex" 且 confidence < fast_path_confidence
- **THEN** AgentRuntime 调用 plan_generator.generate()，生成的 Plan 注入 ReAct loop 的 context

#### Scenario: 简单任务跳过规划
- **WHEN** routing_decision.complexity="simple" 且 confidence >= fast_path_confidence
- **THEN** 跳过 PlanGenerator，直接进入 ReAct 循环
