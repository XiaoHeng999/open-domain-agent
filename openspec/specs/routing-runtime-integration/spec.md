## ADDED Requirements

### Requirement: Domain system prompt 注入 ReAct prompt
系统 SHALL 将 `routing_decision.domain.system_prompt` 注入到 ReAct loop 的 system prompt 中，使不同 domain 的 agent 使用不同的 system prompt。

#### Scenario: coding domain 使用 coding system prompt
- **WHEN** 路由结果 domain="coding"，system_prompt="You are an expert coding assistant..."
- **THEN** ReAct loop 的 system prompt 以 coding system prompt 开头，而非默认通用 prompt

#### Scenario: general domain 使用默认 system prompt
- **WHEN** 路由结果 domain="general"，system_prompt 为通用 prompt
- **THEN** ReAct loop 使用通用 system prompt

### Requirement: skip_planning 控制 PlanGenerator 调用
系统 SHALL 根据 `routing_decision.skip_planning` 决定是否调用 `PlanGenerator.generate()`。skip_planning=True 时跳过规划直接进入 ReAct 循环；skip_planning=False 时先调用 PlanGenerator 生成计划，再将计划注入 ReAct context。

#### Scenario: 复杂任务触发规划
- **WHEN** routing_decision.complexity="complex" 且 confidence < fast_path_confidence
- **THEN** AgentRuntime 调用 plan_generator.generate()，生成的 Plan 注入 ReAct loop 的 context

#### Scenario: 简单任务跳过规划
- **WHEN** routing_decision.complexity="simple" 且 confidence >= fast_path_confidence
- **THEN** 跳过 PlanGenerator，直接进入 ReAct 循环

### Requirement: Missing slots 澄清流程
系统 SHALL 在 routing 结果的 `missing_slots` 非空时，生成澄清问题直接返回给用户，不进入 ReAct loop。澄清问题 SHALL 针对缺失的槽位逐个询问。

#### Scenario: 槽位缺失触发澄清
- **WHEN** 用户输入 "帮我搜索数据" 且路由提取 intent="search_data"、missing_slots=["data_source","time_range"]
- **THEN** AgentRuntime 返回澄清问题 "请提供以下信息：data_source, time_range"，不执行 ReAct loop

#### Scenario: 槽位完整正常执行
- **WHEN** 用户输入 "搜索2024年财报数据" 且 missing_slots=[]
- **THEN** 正常进入 ReAct loop 执行

### Requirement: Routing config domains 传递
系统 SHALL 将 `RoutingConfig.domains` 传递到 `DomainRouter` 和 `UnifiedLLMRouter`，使 YAML/ENV 中配置的 domains 列表实际生效。

#### Scenario: 自定义 domains 配置
- **WHEN** YAML 配置 routing.domains=["coding", "search", "finance"]
- **THEN** DomainRouter 和 UnifiedLLMRouter 仅使用这 3 个 domains（不含 web、general）

#### Scenario: 默认 domains 配置
- **WHEN** 未配置 routing.domains
- **THEN** 使用默认 domains=["coding", "search", "web", "general"]
